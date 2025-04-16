from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
import logging
from django.utils import timezone

from apps.sanctuary.models import SanctuaryRequest, SanctuaryReview, SanctuaryOutcome
from apps.posts.models import Moment, Testimony, Pray, Announcement, Lesson, Preach, Worship, Witness, Library
from apps.profiles.models import Member
from apps.profilesOrg.models import Organization
from apps.config.sanctuary_constants import SENSITIVE_CATEGORIES
from apps.notifications.models import Notification
from django.contrib.auth import get_user_model

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


# UPDATE REPORT Signal --------------------------------------------------
@receiver(post_save, sender=SanctuaryRequest)
def update_reports_count(sender, instance, created, **kwargs):
    if created:
        content_object = instance.content_object

        # Moment
        if isinstance(content_object, Moment):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Testimony
        elif isinstance(content_object, Testimony):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Pray
        elif isinstance(content_object, Pray):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Announcement
        elif isinstance(content_object, Announcement):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Lesson
        elif isinstance(content_object, Lesson):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Preach
        elif isinstance(content_object, Preach):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Worship
        elif isinstance(content_object, Worship):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Witness
        elif isinstance(content_object, Witness):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Library
        elif isinstance(content_object, Library):
            content_object.reports_count += 1
            if content_object.reports_count >= 3:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # CustomUser
        elif isinstance(content_object, CustomUser):
            content_object.reports_count += 1
            if content_object.reports_count >= 6:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

        # Organization
        elif isinstance(content_object, Organization):
            content_object.reports_count += 1
            if content_object.reports_count >= 12:
                content_object.is_suspended = True
            content_object.save()
            return content_object.is_suspended

            
# ASSIGNED ADMIN BY RANDOM Signal ------------------------------------------------------------      
def notify_admins(sanctuary_request):
    admins = CustomUser.objects.filter(is_staff=True).exclude(username=sanctuary_request.assigned_admin.username)
    if admins.exists():
        assigned_admin = admins.order_by('?').first()
        sanctuary_request.assigned_admin = assigned_admin
        sanctuary_request.admin_assigned_at = timezone.now()
        sanctuary_request.save()
        message = f"You have been assigned to review the Sanctuary request: {sanctuary_request}"
        Notification.objects.create(
            user=assigned_admin,
            message=message,
            notification_type='sanctuary_admin_assignment',
            content_object=sanctuary_request,
            link=f"/sanctuary/vote/{sanctuary_request.id}/"
        )
        print(f"Sanctuary request {sanctuary_request.id} assigned to admin {assigned_admin.username}")
        logger.info(f"Sanctuary request {sanctuary_request.id} assigned to admin {assigned_admin.username}")
        return assigned_admin  # Return the assigned admin for further use or logging
    else:
        logger.warning(f"No admin found for Sanctuary request {sanctuary_request.id}")
        return None  # No admin found


# ASSIGNED 12 MEMBERS BY RANDOM Signal -------------------------------------------------------      
def distribute_to_verified_members(sanctuary_request):
    verified_members = Member.objects.filter(
        is_verified_identity=True,
        is_sanctuary_participant=True
    ).exclude(
        Q(username=sanctuary_request.requester.username) | Q(username=sanctuary_request.assigned_admin.username)
    )  # Exclude the requester and the assigned admin by username

    selected_members = verified_members.order_by('?')[:12]
    if selected_members.count() > 0:  # Check if any members are available
        # Send notification to each selected verified member
        for member in selected_members:
            message = f"A new Sanctuary request requires your review: {sanctuary_request}"
            Notification.objects.create(
                user=member,
                message=message,
                notification_type='sanctuary_member_review_request',
                content_object=sanctuary_request,
                link=f"/sanctuary/vote/{sanctuary_request.id}/"
            )
        logger.info(f"Sanctuary request {sanctuary_request.id} sent to {len(selected_members)} verified members")
        return selected_members  # Return the list of selected members for further use or logging
    else:
        logger.warning(f"No verified members available for Sanctuary request {sanctuary_request.id}")
        return None  # No members found
    

# CHECK VOTE COMPLATION Signal ----------------------------------------------------------------
@receiver(post_save, sender=SanctuaryReview)
def check_vote_completion(sender, instance, **kwargs):
    sanctuary_request = instance.sanctuary_request
    reviews = sanctuary_request.reviews.all()

    accept_count = reviews.filter(review_status='violation_confirmed').count()
    reject_count = reviews.filter(review_status='violation_rejected').count()
    content_object = sanctuary_request.content_object  # Access the reported object (Moment, User, Organization)

    if accept_count >= 6:
        sanctuary_request.status = 'accepted'
        sanctuary_request.save()
        outcome = SanctuaryOutcome.objects.create(
            outcome_status='accepted',
            content_type=sanctuary_request.content_type,
            object_id=sanctuary_request.object_id,
        )
        outcome.sanctuary_requests.add(sanctuary_request)
        outcome.save()
        if hasattr(content_object, 'reports_count') and hasattr(content_object, 'is_suspended'):
            content_object.reports_count = 0  
            content_object.is_active = False  
            content_object.save()
        notify_requester_and_reported(sanctuary_request, 'accepted')

    elif reject_count >= 6:
        sanctuary_request.status = 'rejected'
        sanctuary_request.save()
        outcome = SanctuaryOutcome.objects.create(
            outcome_status='rejected',
            content_type=sanctuary_request.content_type,
            object_id=sanctuary_request.object_id,
        )
        outcome.sanctuary_requests.add(sanctuary_request)
        outcome.save()
        if hasattr(content_object, 'reports_count') and hasattr(content_object, 'is_suspended'):
            content_object.reports_count = 0  
            content_object.is_suspended = False 
            content_object.save()
        notify_requester_and_reported(sanctuary_request, 'rejected')
        

# HANDLE NO_OPINION CASE AND REASSIGN NEW MEMBER ---------------------------------------------------
@receiver(post_save, sender=SanctuaryReview)
def handle_no_opinion_and_reassign(sender, instance, **kwargs):
    # 'No Opinion' and reassigns
    if instance.review_status == 'no_opinion':
        sanctuary_request = instance.sanctuary_request
        existing_reviewers_usernames = sanctuary_request.reviews.values_list('reviewer__username', flat=True)  # Get usernames
        verified_members = Member.objects.filter(
            is_verified_identity=True,
            is_sanctuary_participant=True
        ).exclude(
            Q(username=sanctuary_request.requester.username) | Q(username=sanctuary_request.assigned_admin.username) | Q(username__in=existing_reviewers_usernames)
        )
        if verified_members.exists():
            new_member = verified_members.order_by('?').first()  # Select a new member randomly by username
            message = f"You have been selected to review a Sanctuary request: {sanctuary_request}"
            Notification.objects.create(
                user=new_member,
                message=message,
                notification_type='sanctuary_member_review_request',
                content_object=sanctuary_request,
                link=f"/sanctuary/vote/{sanctuary_request.id}/"
            )
            logger.info(f"New member {new_member.username} assigned to replace {instance.reviewer.username} for Sanctuary request {sanctuary_request.id}")
        else:
            logger.warning(f"No new verified members available for replacement in Sanctuary request {sanctuary_request.id}")


# NOTIFY TO REQUESTER AND REPORTER -------------------------------------------------------------      
def notify_requester_and_reported(sanctuary_request, outcome):
    requester = sanctuary_request.requester
    reported_user = sanctuary_request.content_object  # فرض بر این است که کاربر گزارش‌شده از content_object بدست می‌آید

    message_requester = f"The Sanctuary request you submitted has been {outcome}."
    message_reported = f"A Sanctuary request against you has been {outcome}."
    Notification.objects.create(
        user=requester,
        message=message_requester,
        notification_type='sanctuary_request_outcome',
        content_object=sanctuary_request,
        link=f"/sanctuary/vote/{sanctuary_request.id}/"
    )
    Notification.objects.create(
        user=reported_user,
        message=message_reported,
        notification_type='sanctuary_request_outcome',
        content_object=sanctuary_request,
        link=f"/sanctuary/vote/{sanctuary_request.id}/"
    )
    logger.info(f"Notification sent to requester {requester.username} for sanctuary request {sanctuary_request.id}")
    logger.info(f"Notification sent to reported user {reported_user.username} for sanctuary request {sanctuary_request.id}")
 
    
# ------------------------------------------ APPEAL ---------------------------------------------
# ASSIGNED ADMIN For APPEAL ---------------------------------------------------------------------
def notify_admins_of_appeal(sanctuary_outcome):
    admins = CustomUser.objects.filter(is_staff=True).exclude(username=sanctuary_outcome.assigned_admin.username)
    if admins.exists():
        assigned_admin = admins.order_by('?').first()
        sanctuary_outcome.assigned_admin = assigned_admin
        sanctuary_outcome.admin_assigned_at = timezone.now()
        sanctuary_outcome.save()
        message = f"An appeal has been submitted for Sanctuary outcome: {sanctuary_outcome}"
        Notification.objects.create(
            user=assigned_admin,
            message=message,
            notification_type='sanctuary_appeal',
            content_object=sanctuary_outcome,
            link=f"/sanctuary/outcome/{sanctuary_outcome.id}/appeal/"
        )
        print(f"Appeal notification sent to admin {assigned_admin.username} for Sanctuary outcome {sanctuary_outcome.id}")
        logger.info(f"Appeal notification sent to admin {assigned_admin.username} for Sanctuary outcome {sanctuary_outcome.id}")
        return assigned_admin
    else:
        logger.warning(f"No admin found for the appeal of Sanctuary outcome {sanctuary_outcome.id}")
        return None


# APPEAL BY ADMIN Signal --------------------------------------------------------------------------------------
@receiver(post_save, sender=SanctuaryOutcome)
def handle_appeal_by_admin(sender, instance, **kwargs):
    if instance.is_appealed and not instance.admin_reviewed:
        # Admin will review this outcome
        notify_admins_of_appeal(instance)  # Send notification to admins
        # Mark as under admin review
        instance.admin_reviewed = True
        instance.save()


# APPEAL OUTCOME Signal ----------------------------------------------------------------------------------------
def handle_appeal_outcome(sanctuary_outcome):
    content_object = sanctuary_outcome.content_object
    if sanctuary_outcome.outcome_status == 'rejected':
        if hasattr(content_object, 'is_suspended'):
            content_object.is_suspended = False
            content_object.reports_count = 0  # Reset the report count
            content_object.save()
    elif sanctuary_outcome.outcome_status == 'accepted':
        pass


# NOTIFY SANCTUARY TO PARTICIPATNS Signal -----------------------------------------------------------------------
def notify_sanctuary_participants(outcome_obj):
    sanctuary_request = outcome_obj.sanctuary_requests.first()  # Assuming each outcome is linked to one or more requests
    participants = list(sanctuary_request.reviews.values_list('reviewer', flat=True))  # Get the reviewers

    # Notify all participants about the outcome
    for user_id in participants:
        participant = CustomUser.objects.get(id=user_id)
        message = f"The Sanctuary outcome has been finalized as: {outcome_obj.outcome_status}"
        Notification.objects.create(
            user=participant,
            message=message,
            notification_type='sanctuary_outcome_finalized',
            content_object=sanctuary_request,
            link=f"/sanctuary/outcome/{outcome_obj.id}/"  # Link to the outcome
        )

    # Notify the requester
    requester = sanctuary_request.requester
    message_requester = f"The Sanctuary request you submitted has been finalized with the status: {outcome_obj.outcome_status}"
    Notification.objects.create(
        user=requester,
        message=message_requester,
        notification_type='sanctuary_outcome_finalized',
        content_object=sanctuary_request,
        link=f"/sanctuary/outcome/{outcome_obj.id}/"  # Link to the outcome
    )

    # Notify the reported user (content_object)
    reported_user = sanctuary_request.content_object
    if isinstance(reported_user, CustomUser):
        message_reported = f"A Sanctuary request against you has been finalized with the status: {outcome_obj.outcome_status}"
        Notification.objects.create(
            user=reported_user,
            message=message_reported,
            notification_type='sanctuary_outcome_finalized',
            content_object=sanctuary_request,
            link=f"/sanctuary/outcome/{outcome_obj.id}/"  # Link to the outcome
        )


# FINALIZE SANCTUARY OUTCOME ---------------------------------------------------------------------------------------
def finalize_sanctuary_outcome(sanctuary_outcome):
    sanctuary_requests = sanctuary_outcome.sanctuary_requests.all()
    for request in sanctuary_requests:
        content_object = request.content_object

        # If the outcome was accepted, disable the moment/account
        if sanctuary_outcome.outcome_status == 'accepted':
            if hasattr(content_object, 'is_active'):
                content_object.is_active = False 
                content_object.reports_count = 0
                content_object.save()
                logger.info(f"Content {content_object} was disabled after sanctuary outcome accepted.")
                
                # Check if the user is an organization owner/admin
                if isinstance(content_object, CustomUser):
                    user = content_object
                    organizations = Organization.objects.filter(org_owners=user)
                    for org in organizations:
                        if org.org_owners.count() == 1:  # The user is the only owner/admin
                            org.is_active = False  # Suspend the organization
                            org.save()
                            message = f"Your organization '{org.org_name}' has been suspended because your account has been deactivated. " \
                                      "Since you were the only owner/admin, the organization has been suspended."
                            Notification.objects.create(
                                user=user,
                                message=message,
                                notification_type='organization_suspended',
                                link=f"/organization/{org.slug}/"
                            )
                            logger.info(f"Organization {org.org_name} suspended due to single ownership by {user.username}")
                        else:
                            # Suspend the organization but notify the other owners to replace the admin
                            org.is_suspended = True
                            org.save()
                            for owner in org.org_owners.exclude(id=user.id):
                                message = f"Your organization '{org.org_name}' has been suspended because the full access admin's account was deactivated. " \
                                          "Please propose a new admin to reactivate the organization."
                                Notification.objects.create(
                                    user=owner,
                                    message=message,
                                    notification_type='organization_admin_replacement',
                                    link=f"/organization/{org.slug}/owners/"
                                )
                            logger.info(f"Organization {org.org_name} suspended and other owners notified for admin replacement.")
            message_reported = f"Your {content_object._meta.verbose_name} has been disabled following the Sanctuary review."
            Notification.objects.create(
                user=content_object,
                message=message_reported,
                notification_type='sanctuary_outcome',
                content_object=sanctuary_outcome,
                link=f"/sanctuary/outcome/{sanctuary_outcome.id}/"
            )

        # If the outcome was rejected, reactivate the moment/account if suspended
        elif sanctuary_outcome.outcome_status == 'rejected':
            if hasattr(content_object, 'is_suspended'):
                content_object.is_suspended = False
                content_object.reports_count = 0
                content_object.save()
                logger.info(f"Content {content_object} was reactivated after sanctuary outcome rejected.")
            message_reported = f"Your {content_object._meta.verbose_name} has been reactivated after the Sanctuary review."
            Notification.objects.create(
                user=content_object,
                message=message_reported,
                notification_type='sanctuary_outcome',
                content_object=sanctuary_outcome,
                link=f"/sanctuary/outcome/{sanctuary_outcome.id}/"
            )

        # Notify the requester of the outcome
        message_requester = f"The Sanctuary request you submitted has been {sanctuary_outcome.outcome_status}."
        Notification.objects.create(
            user=request.requester,
            message=message_requester,
            notification_type='sanctuary_outcome',
            content_object=sanctuary_outcome,
            link=f"/sanctuary/outcome/{sanctuary_outcome.id}/"
        )
        logger.info(f"Notification sent to requester {request.requester.username} for sanctuary outcome {sanctuary_outcome.id}")

    # Mark the outcome as reviewed and completed
    sanctuary_outcome.admin_reviewed = True
    sanctuary_outcome.completion_date = timezone.now()
    sanctuary_outcome.save()
    logger.info(f"Sanctuary outcome {sanctuary_outcome.id} finalized.")