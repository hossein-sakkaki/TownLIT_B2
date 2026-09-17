# apps/sanctuary/realtime/handler.py

import logging
from typing import Optional

from channels.db import database_sync_to_async
from django.db import transaction
from django.utils import timezone

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.accounts.permissions import (
    is_platform_admin,
)

from apps.sanctuary.constants.states import (
    NO_OPINION,
    VIOLATION_CONFIRMED,
    VIOLATION_REJECTED,
)

from apps.sanctuary.constants.target_models import (
    content_type_key,
)

from apps.sanctuary.models import (
    SanctuaryRequest,
    SanctuaryReview,
)

from apps.sanctuary.realtime.utils import (
    normalize_content_type,
    sanitize_group_part,
)

from apps.sanctuary.services.target_access import (
    assert_sanctuary_target_access,
    resolve_content_type_key,
)


logger = logging.getLogger(__name__)


class SanctuaryHandler:
    """
    Canonical Sanctuary WebSocket handler.

    Client -> Server:
      - type="subscribe"
        data:{request_id}

      - type="unsubscribe"
        data:{request_id}

      - type="subscribe_target"
        data:{
            request_type,
            content_type,
            object_id,
        }

      - type="unsubscribe_target"
        data:{
            request_type,
            content_type,
            object_id,
        }

      - type="review.submit"
        data:{
            request_id,
            review_status,
            comment?,
        }

    Server -> Client:
      {
        "type": "event",
        "app": "sanctuary",
        "event": "...",
        "data": {...},
      }

    Security:
      - sanctuary_global is platform-admin only.
      - request subscriptions require request-level access.
      - target subscriptions use the same canonical target-access
        policy as the REST Sanctuary API.
    """

    APP = "sanctuary"
    GLOBAL_GROUP = "sanctuary_global"

    def __init__(self, socket):
        self.socket = socket
        self.user = socket.user
        self.groups = set()

    # ------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------
    def _message_data(
        self,
        message: dict,
    ) -> dict:
        data = message.get("data")

        if isinstance(data, dict):
            return data

        return {}

    async def _send_event(
        self,
        event: str,
        data: dict | None = None,
    ):
        await self.socket.send_app_event(
            app=self.APP,
            event=event,
            data=data or {},
        )

    async def _send_error(
        self,
        code: str,
        message: str,
        details: dict | None = None,
    ):
        """
        Keep emitting sanctuary:error for current client compatibility.
        """
        payload = {
            "code": code,
            "message": message,
        }

        if details:
            payload["details"] = details

        await self._send_event(
            "error",
            payload,
        )

    @staticmethod
    def _normalize_positive_int(
        value,
    ) -> Optional[int]:
        try:
            normalized = int(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if normalized < 1:
            return None

        return normalized

    @staticmethod
    def _normalize_request_type(
        value,
    ) -> str:
        return str(
            value or ""
        ).strip().lower()

    def _request_group_name(
        self,
        request_id: int,
    ) -> str:
        return (
            f"sanctuary.request."
            f"{int(request_id)}"
        )

    def _target_group_name(
        self,
        request_type: str,
        content_type,
        object_id: int,
    ) -> str:
        """
        Safe canonical target group name.
        """
        rt = sanitize_group_part(
            request_type
        )

        ct = sanitize_group_part(
            normalize_content_type(
                content_type
            )
        )

        return (
            f"sanctuary.target."
            f"{rt}."
            f"{ct}."
            f"{int(object_id)}"
        )

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------
    async def on_connect(self):
        """
        Only platform admins join the global Sanctuary stream.

        Ordinary authenticated users receive Sanctuary realtime
        events only through explicitly authorized request/target
        subscriptions.
        """
        if await self._is_platform_admin_user():
            await self.socket.join_feature_group(
                self.GLOBAL_GROUP
            )

        await self._send_event(
            "ready",
            {
                "status": "ok",
            },
        )

    async def on_disconnect(self):
        for group_name in list(
            self.groups
        ):
            try:
                await (
                    self.socket
                    .leave_feature_group(
                        group_name
                    )
                )
            except Exception as exc:
                logger.error(
                    (
                        "[SanctuaryHandler] "
                        "leave_feature_group(%s) "
                        "failed: %s"
                    ),
                    group_name,
                    exc,
                    exc_info=True,
                )

        self.groups.clear()

    # ------------------------------------------------------------
    # Client -> Server dispatcher
    # ------------------------------------------------------------
    async def handle(
        self,
        message: dict,
    ):
        msg_type = message.get("type")
        data = self._message_data(
            message
        )

        if msg_type == "subscribe":
            await self._subscribe(
                data
            )
            return

        if msg_type == "unsubscribe":
            await self._unsubscribe(
                data
            )
            return

        if msg_type == "subscribe_target":
            await self._subscribe_target(
                data
            )
            return

        if msg_type == "unsubscribe_target":
            await self._unsubscribe_target(
                data
            )
            return

        if msg_type == "review.submit":
            await self._submit_review(
                data
            )
            return

        await self._send_error(
            code=(
                "UNSUPPORTED_MESSAGE_TYPE"
            ),
            message=(
                f"Unknown type "
                f"'{msg_type}'"
            ),
        )

    # ------------------------------------------------------------
    # Backend -> Client dispatcher
    # ------------------------------------------------------------
    async def handle_backend_event(
        self,
        payload: dict,
    ):
        """
        Expected backend shape:

        {
            "app": "sanctuary",
            "event": "...",
            "data": {...},
        }
        """
        try:
            event_type = payload.get(
                "event"
            )

            data = (
                payload.get("data")
                or {}
            )

            if not event_type:
                logger.warning(
                    (
                        "[SanctuaryHandler] "
                        "Missing backend event type"
                    )
                )
                return

            await self._send_event(
                event_type,
                data,
            )

        except Exception as exc:
            logger.error(
                (
                    "[SanctuaryHandler] "
                    "handle_backend_event "
                    "failed: %s"
                ),
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------
    # Request subscription
    # ------------------------------------------------------------
    async def _subscribe(
        self,
        data: dict,
    ):
        request_id = (
            self._normalize_positive_int(
                data.get("request_id")
            )
        )

        if request_id is None:
            await self._send_error(
                code="MISSING_REQUEST_ID",
                message=(
                    "Missing or invalid "
                    "request_id"
                ),
            )
            return

        allowed = (
            await
            self._can_subscribe_request(
                request_id
            )
        )

        if not allowed:
            # Deliberately do not distinguish
            # "not found" from "forbidden".
            await self._send_error(
                code=(
                    "REQUEST_SUBSCRIPTION_"
                    "FORBIDDEN"
                ),
                message=(
                    "You are not allowed "
                    "to subscribe to this "
                    "Sanctuary request."
                ),
            )
            return

        group = (
            self._request_group_name(
                request_id
            )
        )

        if group not in self.groups:
            await (
                self.socket
                .join_feature_group(
                    group
                )
            )

            self.groups.add(
                group
            )

        await self._send_event(
            "subscribed",
            {
                "request_id": request_id,
            },
        )

    async def _unsubscribe(
        self,
        data: dict,
    ):
        request_id = (
            self._normalize_positive_int(
                data.get("request_id")
            )
        )

        if request_id is None:
            await self._send_error(
                code="MISSING_REQUEST_ID",
                message=(
                    "Missing or invalid "
                    "request_id"
                ),
            )
            return

        group = (
            self._request_group_name(
                request_id
            )
        )

        if group in self.groups:
            await (
                self.socket
                .leave_feature_group(
                    group
                )
            )

            self.groups.discard(
                group
            )

        await self._send_event(
            "unsubscribed",
            {
                "request_id": request_id,
            },
        )

    # ------------------------------------------------------------
    # Target subscription
    # ------------------------------------------------------------
    async def _subscribe_target(
        self,
        data: dict,
    ):
        request_type = (
            self._normalize_request_type(
                data.get(
                    "request_type"
                )
            )
        )

        raw_content_type = str(
            data.get(
                "content_type"
            )
            or ""
        ).strip()

        object_id = (
            self._normalize_positive_int(
                data.get(
                    "object_id"
                )
            )
        )

        if (
            not request_type
            or not raw_content_type
            or object_id is None
        ):
            await self._send_error(
                code=(
                    "INVALID_SUBSCRIBE_"
                    "TARGET_PAYLOAD"
                ),
                message=(
                    "Missing or invalid "
                    "request_type/"
                    "content_type/"
                    "object_id"
                ),
            )
            return

        try:
            canonical_content_type = (
                await
                self._resolve_authorized_target(
                    request_type=(
                        request_type
                    ),
                    content_type=(
                        raw_content_type
                    ),
                    object_id=(
                        object_id
                    ),
                )
            )

        except PermissionDenied:
            await self._send_error(
                code=(
                    "TARGET_SUBSCRIPTION_"
                    "FORBIDDEN"
                ),
                message=(
                    "You are not allowed "
                    "to subscribe to this "
                    "Sanctuary target."
                ),
            )
            return

        except serializers.ValidationError:
            await self._send_error(
                code=(
                    "INVALID_SANCTUARY_"
                    "TARGET"
                ),
                message=(
                    "Invalid Sanctuary "
                    "target."
                ),
            )
            return

        except ValueError:
            await self._send_error(
                code=(
                    "INVALID_SANCTUARY_"
                    "TARGET"
                ),
                message=(
                    "Invalid Sanctuary "
                    "target."
                ),
            )
            return

        except Exception as exc:
            logger.error(
                (
                    "[SanctuaryHandler] "
                    "target authorization "
                    "failed user_id=%s "
                    "request_type=%s "
                    "content_type=%s "
                    "object_id=%s "
                    "error=%s"
                ),
                getattr(
                    self.user,
                    "id",
                    None,
                ),
                request_type,
                raw_content_type,
                object_id,
                exc,
                exc_info=True,
            )

            await self._send_error(
                code=(
                    "TARGET_SUBSCRIPTION_"
                    "FAILED"
                ),
                message=(
                    "Unable to subscribe "
                    "to Sanctuary target."
                ),
            )
            return

        group = (
            self._target_group_name(
                request_type,
                canonical_content_type,
                object_id,
            )
        )

        if group not in self.groups:
            await (
                self.socket
                .join_feature_group(
                    group
                )
            )

            self.groups.add(
                group
            )

        await self._send_event(
            "subscribed_target",
            {
                "request_type": (
                    request_type
                ),
                "content_type": (
                    canonical_content_type
                ),
                "object_id": (
                    object_id
                ),
                "group": group,
            },
        )

    async def _unsubscribe_target(
        self,
        data: dict,
    ):
        """
        Unsubscribe intentionally does not re-check access.

        A client must always be able to leave a group even if
        authorization changed after the original subscription.
        """
        request_type = (
            self._normalize_request_type(
                data.get(
                    "request_type"
                )
            )
        )

        content_type = (
            normalize_content_type(
                str(
                    data.get(
                        "content_type"
                    )
                    or ""
                )
            )
        )

        object_id = (
            self._normalize_positive_int(
                data.get(
                    "object_id"
                )
            )
        )

        if (
            not request_type
            or not content_type
            or object_id is None
        ):
            await self._send_error(
                code=(
                    "INVALID_UNSUBSCRIBE_"
                    "TARGET_PAYLOAD"
                ),
                message=(
                    "Missing or invalid "
                    "request_type/"
                    "content_type/"
                    "object_id"
                ),
            )
            return

        group = (
            self._target_group_name(
                request_type,
                content_type,
                object_id,
            )
        )

        if group in self.groups:
            await (
                self.socket
                .leave_feature_group(
                    group
                )
            )

            self.groups.discard(
                group
            )

        await self._send_event(
            "unsubscribed_target",
            {
                "request_type": (
                    request_type
                ),
                "content_type": (
                    content_type
                ),
                "object_id": (
                    object_id
                ),
                "group": group,
            },
        )

    # ------------------------------------------------------------
    # Review submit
    # ------------------------------------------------------------
    async def _submit_review(
        self,
        data: dict,
    ):
        """
        Legacy-compatible realtime review mutation.

        New Android implementation must use the canonical REST
        PATCH endpoint instead.

        This command remains temporarily available so the current
        iOS implementation is not broken before its KMP migration.
        """
        request_id = (
            self._normalize_positive_int(
                data.get(
                    "request_id"
                )
            )
        )

        new_status = str(
            data.get(
                "review_status"
            )
            or ""
        ).strip().lower()

        comment = str(
            data.get(
                "comment"
            )
            or ""
        ).strip()

        if request_id is None:
            await self._send_error(
                code=(
                    "MISSING_REQUEST_ID"
                ),
                message=(
                    "Missing or invalid "
                    "request_id"
                ),
            )
            return

        if new_status not in (
            NO_OPINION,
            VIOLATION_CONFIRMED,
            VIOLATION_REJECTED,
        ):
            await self._send_error(
                code=(
                    "INVALID_REVIEW_STATUS"
                ),
                message=(
                    "Invalid review_status"
                ),
            )
            return

        # A submitted vote must be final.
        if new_status == NO_OPINION:
            await self._send_error(
                code=(
                    "NO_OPINION_NOT_ALLOWED"
                ),
                message=(
                    "NO_OPINION is not "
                    "allowed to submit"
                ),
            )
            return

        request_exists = (
            await self._request_exists(
                request_id
            )
        )

        if not request_exists:
            await self._send_error(
                code=(
                    "REQUEST_NOT_FOUND"
                ),
                message=(
                    "Request not found"
                ),
            )
            return

        review = (
            await self._get_review_slot(
                request_id,
                self.user.id,
            )
        )

        if not review:
            await self._send_error(
                code=(
                    "REVIEWER_NOT_ASSIGNED"
                ),
                message=(
                    "You are not assigned "
                    "to this council review"
                ),
            )
            return

        if (
            review.review_status
            and review.review_status
            != NO_OPINION
        ):
            await self._send_error(
                code="REVIEW_IMMUTABLE",
                message=(
                    "Your vote is final "
                    "and cannot be edited"
                ),
            )
            return

        ok, updated_review = (
            await self._commit_review(
                review.id,
                new_status,
                comment,
            )
        )

        if not ok:
            await self._send_error(
                code=(
                    "REVIEW_SUBMIT_FAILED"
                ),
                message=(
                    "Failed to submit "
                    "review"
                ),
            )
            return

        # ACK for the submitting connection.
        #
        # Canonical domain synchronization is handled by the
        # backend workflow broadcasts / REST state.
        await self._send_event(
            "review_submitted",
            {
                "request_id": (
                    request_id
                ),
                "review_id": (
                    updated_review["id"]
                ),
                "review_status": (
                    updated_review[
                        "review_status"
                    ]
                ),
                "comment": (
                    updated_review[
                        "comment"
                    ]
                ),
                "reviewed_at": (
                    updated_review[
                        "reviewed_at"
                    ]
                ),
            },
        )

    # ------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------
    @database_sync_to_async
    def _is_platform_admin_user(
        self,
    ) -> bool:
        try:
            return bool(
                is_platform_admin(
                    self.user
                )
            )
        except Exception as exc:
            logger.error(
                (
                    "[SanctuaryHandler] "
                    "platform-admin check "
                    "failed user_id=%s "
                    "error=%s"
                ),
                getattr(
                    self.user,
                    "id",
                    None,
                ),
                exc,
                exc_info=True,
            )

            # Fail closed for privileged
            # global Sanctuary access.
            return False

    @database_sync_to_async
    def _can_subscribe_request(
        self,
        request_id: int,
    ) -> bool:
        """
        Request-level realtime access is allowed to:
          - platform admin
          - requester
          - assigned admin
          - active assigned council reviewer

        Nonexistent and unauthorized requests both return False so
        request IDs cannot be enumerated through the WebSocket API.
        """
        try:
            request_obj = (
                SanctuaryRequest.objects
                .get(
                    id=request_id
                )
            )
        except (
            SanctuaryRequest.DoesNotExist,
            ValueError,
            TypeError,
        ):
            return False

        try:
            if is_platform_admin(
                self.user
            ):
                return True

            user_id = getattr(
                self.user,
                "id",
                None,
            )

            if not user_id:
                return False

            if (
                request_obj.requester_id
                == user_id
            ):
                return True

            assigned_admin_id = getattr(
                request_obj,
                "assigned_admin_id",
                None,
            )

            if (
                assigned_admin_id
                and assigned_admin_id
                == user_id
            ):
                return True

            review_qs = (
                SanctuaryReview.objects
                .filter(
                    sanctuary_request_id=(
                        request_obj.id
                    ),
                    reviewer_id=user_id,
                )
            )

            if hasattr(
                SanctuaryReview,
                "is_active",
            ):
                review_qs = (
                    review_qs.filter(
                        is_active=True
                    )
                )

            return review_qs.exists()

        except Exception as exc:
            logger.error(
                (
                    "[SanctuaryHandler] "
                    "request subscription "
                    "authorization failed "
                    "request_id=%s "
                    "user_id=%s "
                    "error=%s"
                ),
                request_id,
                getattr(
                    self.user,
                    "id",
                    None,
                ),
                exc,
                exc_info=True,
            )

            # Fail closed.
            return False

    @database_sync_to_async
    def _resolve_authorized_target(
        self,
        *,
        request_type: str,
        content_type: str,
        object_id: int,
    ) -> str:
        """
        Resolve and authorize a Sanctuary target using the same
        domain access service used by the REST API.

        Returns the canonical 'app_label.model' key.
        """
        target_content_type = (
            resolve_content_type_key(
                content_type
            )
        )

        assert_sanctuary_target_access(
            user=self.user,
            request_type=request_type,
            content_type=(
                target_content_type
            ),
            object_id=object_id,
            allow_self_target=True,
        )

        return normalize_content_type(
            content_type_key(
                target_content_type
            )
        )

    # ------------------------------------------------------------
    # DB operations
    # ------------------------------------------------------------
    @database_sync_to_async
    def _request_exists(
        self,
        request_id: int,
    ) -> bool:
        return (
            SanctuaryRequest.objects
            .filter(
                id=request_id
            )
            .exists()
        )

    @database_sync_to_async
    def _get_review_slot(
        self,
        request_id: int,
        user_id: int,
    ):
        try:
            qs = (
                SanctuaryReview.objects
                .select_related(
                    "reviewer"
                )
                .filter(
                    sanctuary_request_id=(
                        request_id
                    ),
                    reviewer_id=(
                        user_id
                    ),
                )
            )

            if hasattr(
                SanctuaryReview,
                "is_active",
            ):
                qs = qs.filter(
                    is_active=True
                )

            return qs.get()

        except (
            SanctuaryReview.DoesNotExist
        ):
            return None

    @database_sync_to_async
    def _commit_review(
        self,
        review_id: int,
        status: str,
        comment: str,
    ):
        try:
            with transaction.atomic():
                review = (
                    SanctuaryReview.objects
                    .select_for_update()
                    .get(
                        id=review_id
                    )
                )

                if (
                    review.review_status
                    and review.review_status
                    != NO_OPINION
                ):
                    return (
                        False,
                        None,
                    )

                review.review_status = (
                    status
                )

                review.comment = (
                    comment
                )

                review.reviewed_at = (
                    timezone.now()
                )

                review.save(
                    update_fields=[
                        "review_status",
                        "comment",
                        "reviewed_at",
                    ]
                )

                return (
                    True,
                    {
                        "id": review.id,
                        "review_status": (
                            review.review_status
                        ),
                        "comment": (
                            review.comment
                        ),
                        "reviewed_at": (
                            review
                            .reviewed_at
                            .isoformat()
                            if review.reviewed_at
                            else (
                                timezone
                                .now()
                                .isoformat()
                            )
                        ),
                    },
                )

        except Exception as exc:
            logger.warning(
                (
                    "[SanctuaryHandler] "
                    "_commit_review "
                    "failed: %s"
                ),
                exc,
                exc_info=True,
            )

            return (
                False,
                None,
            )