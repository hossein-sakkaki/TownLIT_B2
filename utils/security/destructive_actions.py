from django.utils import timezone
from django.conf import settings
from django.db.models import Max
from apps.conversation.models import Dialogue, Message, UserDialogueMarker, DialogueParticipant
from apps.profiles.models import Fellowship, Member
from utils.security.security_manager import SecurityStateManager
from utils.email.email_tools import send_custom_email


def handle_destructive_pin_actions(user):
    """
    Central function for destructive PIN actions:
    - Cleans up dialogues
    - Hides confidants
    - Notifies confidants
    """
    cleanup_sensitive_private_dialogues(user)
    cleanup_sensitive_group_dialogues(user)
    SecurityStateManager.hide_confidants(user)
    notify_confidants_of_delete_pin(user)


# --- 1. Clean up private dialogues ---
def cleanup_sensitive_private_dialogues(user):
    markers = UserDialogueMarker.objects.filter(user=user, is_sensitive=True, dialogue__is_group=False).select_related("dialogue")
    for marker in markers:
        dialogue = marker.dialogue
        other = dialogue.participants.exclude(id=user.id).first()

        if other and dialogue.deleted_by_users.filter(id=other.id).exists():
            Message.objects.filter(dialogue=dialogue).delete()
            marker.delete()
            dialogue.delete()
        else:
            dialogue.deleted_by_users.add(user)
            for msg in dialogue.messages.all():
                msg.deleted_by_users.add(user)
            marker.delete()


# --- 2. Clean up group dialogues ---
def cleanup_sensitive_group_dialogues(user):
    markers = UserDialogueMarker.objects.filter(user=user, is_sensitive=True, dialogue__is_group=True).select_related("dialogue")

    for marker in markers:
        dialogue = marker.dialogue
        try:
            participant_obj = dialogue.participants_roles.get(user=user)
        except DialogueParticipant.DoesNotExist:
            continue  # Safety

        role = participant_obj.role

        if role in ["participant", "elder"]:
            participant_obj.delete()
            dialogue.participants.remove(user)
            for msg in dialogue.messages.all():
                msg.deleted_by_users.add(user)
            marker.delete()

        elif role == "founder":
            elders = dialogue.participants_roles.filter(role="elder").exclude(user=user)
            if elders.exists():
                new_founder_user = find_new_founder(dialogue, user)
                if new_founder_user:
                    new_founder = dialogue.participants_roles.get(user=new_founder_user)
                    participant_obj.role = "participant"
                    participant_obj.save()
                    new_founder.role = "founder"
                    new_founder.save()

                    dialogue.participants.remove(user)
                    for msg in dialogue.messages.all():
                        msg.deleted_by_users.add(user)
                    marker.delete()
                    continue

            # No other elders → delete group
            Message.objects.filter(dialogue=dialogue).delete()
            DialogueParticipant.objects.filter(dialogue=dialogue).delete()
            UserDialogueMarker.objects.filter(dialogue=dialogue).delete()
            dialogue.delete()



# --- 3. Notify confidants via email ---
def notify_confidants_of_delete_pin(user):
    confidants = Fellowship.objects.filter(
        from_user=user,
        fellowship_type="Confidant",
        status="Accepted"
    )

    for confidant in confidants:
        confidant_user = confidant.to_user

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


# --- 4. Helper: Find new founder in group ---
def find_new_founder(dialogue, current_user):
    eligible_elders = DialogueParticipant.objects.filter(
        dialogue=dialogue,
        role='elder'
    ).exclude(user=current_user)

    if eligible_elders.count() == 1:
        return eligible_elders.first().user

    if not eligible_elders.exists():
        return None

    elders_with_activity = eligible_elders.annotate(
        last_active=Max("user__marked_dialogues__last_typing_at")
    ).order_by("-last_active")

    top_choice = elders_with_activity.first()
    if top_choice and top_choice.last_active:
        return top_choice.user

    fallback = eligible_elders.order_by("joined_at").first()
    return fallback.user if fallback else None




