# apps/conversation/tasks/pins.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from celery import shared_task

from apps.conversation.services.message_pins import (
    collect_due_pin_reminders,
    expire_due_message_pins,
)
from apps.conversation.services.pin_notification_adapter import send_message_pin_reminder_notification


@shared_task(name="apps.conversation.tasks.cleanup_expired_message_pins")
def cleanup_expired_message_pins():
    """
    Remove expired message pins and keep pin order compact.
    """
    result = expire_due_message_pins()
    if not result.get("ok"):
        return "Failed to expire message pins."
    payload = result["payload"]
    return f"Expired {payload['expired_count']} message pins."


@shared_task(name="apps.conversation.tasks.send_due_message_pin_reminders")
def send_due_message_pin_reminders():
    """
    Send reminder notifications for due message pins.
    """
    result = collect_due_pin_reminders()
    if not result.get("ok"):
        return "Failed to collect due pin reminders."
    pins = result["payload"]["pins"]
    for pin in pins:
        send_message_pin_reminder_notification(pin)
    return f"Sent {len(pins)} message pin reminders."
