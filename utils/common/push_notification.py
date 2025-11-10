# utils/common/push_notification.py
from django.conf import settings


# Push Notification ---------------------------------------------------------
from pyfcm import FCMNotification
def send_push_notification(registration_id, message_title, message_body):
    push_service = FCMNotification(api_key=settings.FCM_API_KEY)
    result = push_service.notify_single_device(
        registration_id=registration_id,
        message_title=message_title,
        message_body=message_body
    )
    return result