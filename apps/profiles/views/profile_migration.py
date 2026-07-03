# apps/profiles/views/profile_migration.py

from datetime import timedelta
import logging

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.accounts.constants.user_labels import (
    BELIEVER,
    SEEKER,
    PREFER_NOT_TO_SAY,
)
from apps.accounts.models import CustomLabel
from apps.profiles.models.member import Member
from apps.profiles.models.guest import GuestUser

from apps.posts.models.moment import Moment
from apps.posts.models.testimony import Testimony
from apps.posts.models.pray import Prayer
# from apps.posts.models.journey import Journey
# from apps.posts.models.echolIT import EchoLIT

from apps.profiles.models.transitions import MigrationHistory
from apps.profiles.serializers.member import MemberSerializer
from apps.profiles.serializers.guest import GuestUserSerializer
from apps.profiles.services.active_profile import get_active_profile 
from apps.profiles.services.profile_migration_content_safety import (
    privatize_member_covenant_moments_before_guest_migration,
)

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


class ProfileMigrationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    MONTHLY_LIMIT = 2
    LIFETIME_LIMIT = 4

    # ---------------------------------------------------------------------
    # Utility
    # ---------------------------------------------------------------------
    def _resolve_target_type(self, user, explicit_target=None):
        if explicit_target in {"member", "guest"}:
            return explicit_target

        active = get_active_profile(user)
        if active.profile_type == "member":
            return "guest"
        if active.profile_type == "guest":
            return "member"

        return None

    # ---------------------------------------------------------------------
    def _get_label_obj(self, label_name: str):
        label = CustomLabel.objects.filter(name=label_name).first()
        return label

    # ---------------------------------------------------------------------
    def _sync_user_identity_fields(self, user, target_type: str, guest_label: str = SEEKER):
        """
        Sync CustomUser.is_member and CustomUser.label with the active profile type.
        """
        update_fields = []

        new_is_member = target_type == "member"
        if user.is_member != new_is_member:
            user.is_member = new_is_member
            update_fields.append("is_member")

        target_label_name = BELIEVER if target_type == "member" else guest_label
        target_label = self._get_label_obj(target_label_name)

        if target_label is None:
            logger.error(
                "Profile migration: missing CustomLabel '%s' for user_id=%s username=%s",
                target_label_name,
                user.id,
                user.username,
            )
            raise ValueError(f"CustomLabel '{target_label_name}' not found.")

        if user.label_id != target_label.id:
            user.label = target_label
            update_fields.append("label")

        if update_fields:
            user.save(update_fields=update_fields)

    # ---------------------------------------------------------------------
    def _can_migrate(self, user):
        now = timezone.now()

        monthly_qs = MigrationHistory.objects.filter(
            user=user,
            migration_date__gte=now - timedelta(days=30),
        ).order_by("migration_date")

        monthly_count = monthly_qs.count()
        lifetime_count = MigrationHistory.objects.filter(user=user).count()

        blocked_reason = None
        next_monthly_migration_at = None

        if lifetime_count >= self.LIFETIME_LIMIT:
            blocked_reason = "lifetime_limit_reached"
        elif monthly_count >= self.MONTHLY_LIMIT:
            blocked_reason = "monthly_limit_reached"

            oldest_in_window = monthly_qs.first()
            if oldest_in_window:
                next_monthly_migration_at = oldest_in_window.migration_date + timedelta(days=30)

        allowed = blocked_reason is None

        return {
            "allowed": allowed,
            "blocked_reason": blocked_reason,
            "monthly_count": monthly_count,
            "lifetime_count": lifetime_count,
            "monthly_limit": self.MONTHLY_LIMIT,
            "lifetime_limit": self.LIFETIME_LIMIT,
            "remaining_lifetime": max(self.LIFETIME_LIMIT - lifetime_count, 0),
            "next_monthly_migration_at": next_monthly_migration_at,
        }

    # ---------------------------------------------------------------------
    def _migrate_moment_ownership(self, from_profile, to_profile):
        """
        Move all Moment ownership from the old profile object
        to the new profile object during profile migration.
        """
        from_ct = ContentType.objects.get_for_model(
            from_profile.__class__,
            for_concrete_model=False,
        )
        to_ct = ContentType.objects.get_for_model(
            to_profile.__class__,
            for_concrete_model=False,
        )

        moved = Moment.objects.filter(
            content_type=from_ct,
            object_id=from_profile.id,
        ).update(
            content_type=to_ct,
            object_id=to_profile.id,
        )

        return moved

    # ---------------------------------------------------------------------
    def _set_member_only_content_active_state(self, member, *, is_active: bool):
        """
        Toggle member-only content visibility/availability without deleting it.
        Used when a user switches between member and guest.
        """

        member_ct = ContentType.objects.get_for_model(
            member.__class__,
            for_concrete_model=False,
        )

        testimony_updated = Testimony.objects.filter(
            content_type=member_ct,
            object_id=member.id,
        ).update(is_active=is_active)

        prayer_updated = Prayer.objects.filter(
            content_type=member_ct,
            object_id=member.id,
        ).update(is_active=is_active)

        # Future-ready placeholders
        journey_updated = 0
        echolit_updated = 0

        # Example when models are added later:
        # journey_updated = Journey.objects.filter(
        #     content_type=member_ct,
        #     object_id=member.id,
        # ).update(is_active=is_active)
        #
        # echolit_updated = EchoLIT.objects.filter(
        #     content_type=member_ct,
        #     object_id=member.id,
        # ).update(is_active=is_active)

        
    # ---------------------------------------------------------------------
    def _serialize_active_profile(self, user, request):
        active = get_active_profile(user)

        if active.profile_type == "member" and active.member:
            return {
                "profile_type": "member",
                "profile": MemberSerializer(active.member, context={"request": request}).data,
            }

        if active.profile_type == "guest" and active.guest:
            return {
                "profile_type": "guest",
                "profile": GuestUserSerializer(active.guest, context={"request": request}).data,
            }

        return {
            "profile_type": None,
            "profile": None,
        }

    # ---------------------------------------------------------------------
    def _activate_guest(self, user):

        member = getattr(user, "member_profile", None)

        if member and member.is_active:
            member.is_active = False
            member.is_migrated = True
            member.save(update_fields=["is_active", "is_migrated"])

        guest = getattr(user, "guest_profile", None)

        if guest:
            guest.is_active = True
            guest.is_migrated = False
            guest.save(update_fields=["is_active", "is_migrated"])
            return guest, False

        guest = GuestUser.objects.create(
            user=user,
            is_active=True,
            is_migrated=False,
        )

        return guest, True

    # ---------------------------------------------------------------------
    def _activate_member(self, user, request):

        guest = getattr(user, "guest_profile", None)

        if guest and guest.is_active:
            guest.is_active = False
            guest.is_migrated = True
            guest.save(update_fields=["is_active", "is_migrated"])

        member = getattr(user, "member_profile", None)

        if member:
            member.is_active = True
            member.is_migrated = False
            member.save(update_fields=["is_active", "is_migrated"])
            return member, False, None

        member_payload = (request.data.get("member_profile") or {}).copy()
        member_payload.pop("user", None)

        try:
            member = Member.objects.create(
                user=user,
                is_active=True,
                is_migrated=False,
            )
        except Exception:
            logger.exception(
                "Profile migration: Member.objects.create failed for user_id=%s username=%s",
                user.id,
                user.username,
            )
            raise

        if not member_payload:
            return member, True, None

        serializer = MemberSerializer(
            member,
            data=member_payload,
            partial=True,
            context={"request": request},
        )

        if not serializer.is_valid():
            logger.warning(
                "Profile migration: member serializer invalid for user_id=%s errors=%s",
                user.id,
                serializer.errors,
            )
            member.delete()
            return None, None, serializer.errors

        try:
            member = serializer.save()
        except Exception:
            logger.exception(
                "Profile migration: member serializer.save failed for user_id=%s username=%s",
                user.id,
                user.username,
            )
            member.delete()
            raise

        return member, True, None

    # ---------------------------------------------------------------------
    # Status
    # ---------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="status")
    def status(self, request):
        user = request.user

        limits = self._can_migrate(user)
        payload = self._serialize_active_profile(user, request)

        payload.update(
            {
                "can_migrate": limits["allowed"],
                "blocked_reason": limits["blocked_reason"],
                "monthly_count": limits["monthly_count"],
                "lifetime_count": limits["lifetime_count"],
                "monthly_limit": limits["monthly_limit"],
                "lifetime_limit": limits["lifetime_limit"],
                "remaining_lifetime_migrations": limits["remaining_lifetime"],
                "next_monthly_migration_at": limits["next_monthly_migration_at"],
            }
        )

        return Response(payload, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request):
        records = MigrationHistory.objects.filter(
            user=request.user
        ).order_by("-migration_date")

        data = [
            {
                "id": record.id,
                "migration_type": record.migration_type,
                "migration_date": record.migration_date,
            }
            for record in records
        ]

        return Response({"results": data}, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------------

    @action(detail=False, methods=["get"], url_path="current-profile")
    def current_profile(self, request):
        user = request.user
        label_value = getattr(user.label, "name", None)

        limits = self._can_migrate(user)
        payload = self._serialize_active_profile(user, request)

        payload.update(
            {
                "can_migrate": limits["allowed"],
                "blocked_reason": limits["blocked_reason"],
                "monthly_count": limits["monthly_count"],
                "lifetime_count": limits["lifetime_count"],
                "monthly_limit": limits["monthly_limit"],
                "lifetime_limit": limits["lifetime_limit"],
                "remaining_lifetime_migrations": limits["remaining_lifetime"],
                "next_monthly_migration_at": limits["next_monthly_migration_at"],
            }
        )

        return Response(payload, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------------
    # Migration
    # ---------------------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="migrate-profile")
    def migrate_profile(self, request):
        user = request.user
        target_profile_type = request.data.get("target_profile_type")
        guest_label = request.data.get("guest_label", SEEKER)

        try:
            limits = self._can_migrate(user)

            if not limits["allowed"]:
                return Response(
                    {
                        "error": "Migration limit reached.",
                        "details": limits,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            target_type = self._resolve_target_type(user, explicit_target=target_profile_type)

            if target_type is None:
                return Response(
                    {"error": "Unable to resolve target profile type."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if target_type == "guest" and guest_label not in {SEEKER, PREFER_NOT_TO_SAY}:
                return Response(
                    {"error": "guest_label must be either seeker or prefer_not_to_say."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            active = get_active_profile(user)

            if active.profile_type == target_type:
                return Response(
                    {"message": f"User already using {target_type} profile."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                if target_type == "guest":
                    previous_member = getattr(user, "member_profile", None)

                    guest, created = self._activate_guest(user)

                    covenant_moments_privatized = 0

                    if previous_member:
                        covenant_moments_privatized = (
                            privatize_member_covenant_moments_before_guest_migration(
                                previous_member
                            )
                        )

                        self._migrate_moment_ownership(
                            from_profile=previous_member,
                            to_profile=guest,
                        )

                        self._set_member_only_content_active_state(
                            previous_member,
                            is_active=False,
                        )

                    self._sync_user_identity_fields(
                        user=user,
                        target_type="guest",
                        guest_label=guest_label,
                    )

                    MigrationHistory.objects.create(
                        user=user,
                        migration_type="member_to_guest",
                    )

                    guest.refresh_from_db()

                    guest_data = GuestUserSerializer(
                        guest,
                        context={"request": request},
                    ).data

                    return Response(
                        {
                            "message": "Profile migrated to GuestUser successfully.",
                            "profile_type": "guest",
                            "created": created,
                            "label": guest_label,
                            "profile": guest_data,
                            "content_safety": {
                                "covenant_moments_privatized": covenant_moments_privatized,
                            },
                        },
                        status=status.HTTP_200_OK,
                    )

                previous_guest = getattr(user, "guest_profile", None)
                member, created, errors = self._activate_member(user, request)

                if errors:
                    logger.warning(
                        "Profile migration failed during member activation: user_id=%s errors=%s",
                        user.id,
                        errors,
                    )
                    transaction.set_rollback(True)
                    return Response(
                        {
                            "error": "Member profile creation failed.",
                            "details": errors,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if previous_guest:
                    self._migrate_moment_ownership(
                        from_profile=previous_guest,
                        to_profile=member,
                    )

                self._set_member_only_content_active_state(
                    member,
                    is_active=True,
                )

                self._sync_user_identity_fields(
                    user=user,
                    target_type="member",
                )

                MigrationHistory.objects.create(
                    user=user,
                    migration_type="guest_to_member",
                )

                member.refresh_from_db()

                member_data = MemberSerializer(
                    member,
                    context={"request": request},
                ).data

                return Response(
                    {
                        "message": "Profile migrated to Member successfully.",
                        "profile_type": "member",
                        "created": created,
                        "label": BELIEVER,
                        "profile": member_data,
                    },
                    status=status.HTTP_200_OK,
                )

        except ValueError as exc:
            logger.exception(
                "Profile migration value error: user_id=%s username=%s error=%s",
                user.id,
                user.username,
                str(exc),
            )
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:
            logger.exception(
                "Profile migration unexpected error: user_id=%s username=%s",
                user.id,
                user.username,
            )
            return Response(
                {"error": "An unexpected error occurred during profile migration."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )