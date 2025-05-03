from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def send_invite_email(email, full_name, code):
    context = {
        'full_name': full_name or "Friend",
        'invite_code': code,
        'email': email,
    }

    subject = f"🌟 Welcome to TownLIT, {full_name or 'Friend'}!"
    html_message = render_to_string("emails/invite/invite_email.html", context)

    send_mail(
        subject=subject,
        message='',  # plain text optional
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message
    )
