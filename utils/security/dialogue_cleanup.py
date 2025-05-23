# utils/security/dialogue_cleanup.py

from apps.conversation.models import Dialogue, Message, UserDialogueMarker, DialogueParticipant
from apps.profiles.models import Fellowship
from utils.email.email_tools import send_custom_email
from django.utils import timezone
from django.conf import settings



def handle_sensitive_dialogue_cleanup(user):
    sensitive_markers = UserDialogueMarker.objects.filter(user=user, is_sensitive=True).select_related("dialogue")

    for marker in sensitive_markers:
        dialogue = marker.dialogue

        if not dialogue.is_group:
            # Private chat logic (قبلاً کامل نوشتی)
            other = dialogue.participants.exclude(id=user.id).first()
            if other and dialogue.deleted_by_users.filter(id=other.id).exists():
                Message.objects.filter(dialogue=dialogue).delete()
                UserDialogueMarker.objects.filter(user=user, dialogue=dialogue).delete()
                dialogue.delete()
            else:
                dialogue.deleted_by_users.add(user)
                for msg in dialogue.messages.all():
                    msg.deleted_by_users.add(user)
                marker.delete()
            continue

        # ✅ Group Logic
        try:
            participant_obj = dialogue.participants_roles.get(user=user)
        except DialogueParticipant.DoesNotExist:
            continue  # safety check

        role = participant_obj.role

        if role in ["participant", "elder"]:
            # Soft delete & leave group
            participant_obj.delete()
            dialogue.participants.remove(user)
            for msg in dialogue.messages.all():
                msg.deleted_by_users.add(user)
            marker.delete()
            continue

        elif role == "founder":
            elders = dialogue.participants_roles.filter(role="elder")
            if elders.exclude(user=user).exists():
                # ✅ Transfer founder role to another elder
                new_founder_user = find_new_founder(dialogue, user)
                new_founder = DialogueParticipant.objects.filter(dialogue=dialogue, user=new_founder_user).first()
                if new_founder:
                    participant_obj.role = "participant"
                    participant_obj.save()
                    new_founder.role = "founder"
                    new_founder.save()

                    # حذف نرم founder سابق
                    dialogue.participants.remove(user)
                    for msg in dialogue.messages.all():
                        msg.deleted_by_users.add(user)
                    marker.delete()
                    continue

            # 🟥 تنها founder و elder موجود → حذف کامل گروه
            Message.objects.filter(dialogue=dialogue).delete()
            DialogueParticipant.objects.filter(dialogue=dialogue).delete()
            UserDialogueMarker.objects.filter(dialogue=dialogue).delete()
            dialogue.delete()
            continue

    notify_confidants_of_delete_pin(user)





def notify_confidants_of_delete_pin(user):
    confidants = Fellowship.objects.filter(from_user=user, fellowship_type="Confidant", status="Accepted")
    for confidant in confidants:
        confidant_user = confidant.to_user
        
        # Alert Email to confidant
        subject = "Security Alert: Destructive PIN Used"
        context = {
            'confidant_user': confidant_user,
            'user': user,
            'profile_link': f'{settings.SITE_URL}/{user.username}/',
            "site_domain": settings.SITE_URL,
            "logo_base_url": settings.EMAIL_LOGO_URL,
            "current_year": timezone.now().year,
        }

        success = send_custom_email(
            to=confidant_user.email,
            subject=subject,
            template_path='emails/alert/security_alert.html',
            context=context,
            text_template_path=None
        )

        if not success:
            print(f"❌ Failed to send security alert to: {confidant_user.email}")
        
        
def find_new_founder(dialogue, current_user):
    eligible_elders = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        role='elder'
    ).exclude(user=current_user)

    # اگر فقط یک elder باقی مانده، همان را برگزین
    if eligible_elders.count() == 1:
        return eligible_elders.first().user

    # اگر هیچ elder وجود ندارد
    if not eligible_elders.exists():
        return None

    # اگر بیشتر از یکی بود، از طریق آخرین فعالیت انتخاب کن
    from django.db.models import Max
    elders_with_activity = eligible_elders.annotate(
        last_active=Max("user__marked_dialogues__last_typing_at")
    ).order_by("-last_active")

    top_choice = elders_with_activity.first()
    if top_choice and top_choice.last_active:
        return top_choice.user

    # اگر هیچ داده‌ای از فعالیت نبود، براساس joined_at انتخاب کن
    fallback = eligible_elders.order_by("joined_at").first()
    return fallback.user if fallback else None

