from apps.notifications.models import Notification




def send_sanctuary_request_to_member(instance, member):
    message = f"Dear {member.name},\n\n"
    message += f"A Sanctuary request has been submitted for {instance.content_object}.\n"
    message += f"Reason: {instance.reason}\n"
    message += "Please provide your feedback and vote on this request."

    Notification.objects.create(
        user=member,
        message=message,
        notification_type='sanctuary_request',
        content_object=instance,
        link=f"/sanctuary/vote/{instance.id}/"
    )


def notify_assigned_admin(admin, sanctuary_request):
    message = f"You have been assigned to review the Sanctuary request: {sanctuary_request}"
    Notification.objects.create(
        user=admin,
        message=message,
        notification_type='sanctuary_admin_assignment',
        content_object=sanctuary_request
    )
    

