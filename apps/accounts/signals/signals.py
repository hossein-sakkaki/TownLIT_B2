from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.timezone import now
from apps.accounts.models import CustomUser


@receiver(pre_save, sender=CustomUser)
def handle_email_change(sender, instance, **kwargs):
    # Fetch the original instance before save
    if not instance.pk:
        return  # Skip if the instance is being created

    original = sender.objects.get(pk=instance.pk)

    # Check if email has been changed
    if original.email != instance.email:
        # Email change detected

        # Send email to the old email address
        if original.email:
            subject_old = "Your Email Is Being Changed"
            email_body_old = render_to_string('emails/email_change_notification.html', {
                'username': instance.username,
                'new_email': instance.email,
                'timestamp': now()
            })
            send_mail(
                subject_old,
                '',  # Plain text email (if needed)
                'no-reply@townlit.com',
                [original.email],
                html_message=email_body_old
            )

        # Send email to the new email address
        subject_new = "Welcome to Your New Email"
        email_body_new = render_to_string('emails/email_change_new.html', {
            'username': instance.username,
            'old_email': original.email,
                'timestamp': now()
        })
        send_mail(
            subject_new,
            '',  # Plain text email (if needed)
            'no-reply@townlit.com',
            [instance.email],
            html_message=email_body_new
        )
