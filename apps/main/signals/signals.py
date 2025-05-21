from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.main.models import TermsAndPolicy, UserActionLog
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

# ADD LOG TERM AND POLICY UPDATE Signal ---------------------------------------
@receiver(post_save, sender=TermsAndPolicy)
def log_terms_and_policy_update(sender, instance, created, **kwargs):
    if not created:
        admin_user = CustomUser.objects.filter(is_superuser=True).first()
        if admin_user:
            UserActionLog.objects.create(
                user=admin_user,
                action_type='UPDATE',
                target_model='TermsAndPolicy',
                target_instance_id=instance.id
            )
            
 