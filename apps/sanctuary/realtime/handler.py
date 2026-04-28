# apps/sanctuary/realtime/handler.py

import logging
from typing import Optional

from django.db import transaction
from django.utils import timezone
from channels.db import database_sync_to_async

from apps.sanctuary.realtime.utils import (
    normalize_content_type,
    sanitize_group_part,
)
from apps.sanctuary.models import SanctuaryRequest, SanctuaryReview
from apps.sanctuary.constants.states import (
    NO_OPINION,
    VIOLATION_CONFIRMED,
    VIOLATION_REJECTED,
)

logger = logging.getLogger(__name__)


class SanctuaryHandler:
    """
    Canonical Sanctuary WS handler.

    Client -> Server:
      - type="subscribe"             data:{request_id}
      - type="unsubscribe"           data:{request_id}

      - type="subscribe_target"      data:{request_type, content_type, object_id}
      - type="unsubscribe_target"    data:{request_type, content_type, object_id}

      - type="review.submit"         data:{request_id, review_status, comment?}

    Server -> Client:
      { "type":"event", "app":"sanctuary", "event":"...", "data":{...} }
    """

    APP = "sanctuary"

    def __init__(self, socket):
        self.socket = socket
        self.user = socket.user
        self.groups = set()

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _message_data(self, message: dict) -> dict:
        data = message.get("data")
        if isinstance(data, dict):
            return data
        return {}

    async def _send_event(self, event: str, data: dict | None = None):
        await self.socket.send_app_event(
            app=self.APP,
            event=event,
            data=data or {},
        )

    async def _send_error(self, code: str, message: str, details: dict | None = None):
        """
        Keep emitting sanctuary:error for current client compatibility.
        """
        payload = {
            "code": code,
            "message": message,
        }
        if details:
            payload["details"] = details

        await self._send_event("error", payload)

    def _request_group_name(self, request_id: int) -> str:
        return f"sanctuary.request.{request_id}"

    def _target_group_name(
        self,
        request_type: str,
        content_type,
        object_id: int,
    ) -> str:
        """
        Safe group name for target-level sync.
        """
        rt = sanitize_group_part(request_type)
        ct = sanitize_group_part(normalize_content_type(content_type))
        return f"sanctuary.target.{rt}.{ct}.{int(object_id)}"

    @staticmethod
    def _normalize_int(v) -> Optional[int]:
        try:
            return int(v)
        except Exception:
            return None

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------
    async def on_connect(self):
        await self.socket.join_feature_group("sanctuary_global")
        await self._send_event("ready", {"status": "ok"})

    async def on_disconnect(self):
        for group_name in list(self.groups):
            try:
                await self.socket.leave_feature_group(group_name)
            except Exception as e:
                logger.error(
                    f"[SanctuaryHandler] leave_feature_group({group_name}) failed: {e}",
                    exc_info=True,
                )
        self.groups.clear()

    # ------------------------------------------------------------
    # Client -> Server dispatcher
    # ------------------------------------------------------------
    async def handle(self, message: dict):
        msg_type = message.get("type")
        data = self._message_data(message)

        if msg_type == "subscribe":
            await self._subscribe(data)
            return

        if msg_type == "unsubscribe":
            await self._unsubscribe(data)
            return

        if msg_type == "subscribe_target":
            await self._subscribe_target(data)
            return

        if msg_type == "unsubscribe_target":
            await self._unsubscribe_target(data)
            return

        if msg_type == "review.submit":
            await self._submit_review(data)
            return

        logger.debug("[SanctuaryHandler] Unknown client type=%s", msg_type)
        await self._send_error(
            code="UNSUPPORTED_MESSAGE_TYPE",
            message=f"Unknown type '{msg_type}'",
        )

    # ------------------------------------------------------------
    # Backend -> Client dispatcher
    # ------------------------------------------------------------
    async def handle_backend_event(self, payload: dict):
        """
        Expected backend shape:
          { "app":"sanctuary", "event":"...", "data":{...} }
        """
        try:
            event_type = payload.get("event")
            data = payload.get("data") or {}

            if not event_type:
                logger.warning("[SanctuaryHandler] Missing backend event type")
                return

            await self._send_event(event_type, data)

        except Exception as e:
            logger.error(
                "[SanctuaryHandler] handle_backend_event failed: %s",
                e,
                exc_info=True,
            )

    # ------------------------------------------------------------
    # Subscribe / Unsubscribe (Request-level)
    # ------------------------------------------------------------
    async def _subscribe(self, data: dict):
        request_id = self._normalize_int(data.get("request_id"))
        if not request_id:
            await self._send_error(
                code="MISSING_REQUEST_ID",
                message="Missing request_id",
            )
            return

        group = self._request_group_name(request_id)

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event("subscribed", {"request_id": request_id})

    async def _unsubscribe(self, data: dict):
        request_id = self._normalize_int(data.get("request_id"))
        if not request_id:
            await self._send_error(
                code="MISSING_REQUEST_ID",
                message="Missing request_id",
            )
            return

        group = self._request_group_name(request_id)

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

        await self._send_event("unsubscribed", {"request_id": request_id})

    # ------------------------------------------------------------
    # Subscribe / Unsubscribe (Target-level)
    # ------------------------------------------------------------
    async def _subscribe_target(self, data: dict):
        request_type = (data.get("request_type") or "").strip()
        content_type = (data.get("content_type") or "").strip()
        object_id = self._normalize_int(data.get("object_id"))

        if not request_type or not content_type or not object_id:
            await self._send_error(
                code="INVALID_SUBSCRIBE_TARGET_PAYLOAD",
                message="Missing request_type/content_type/object_id",
            )
            return

        group = self._target_group_name(request_type, content_type, object_id)

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event(
            "subscribed_target",
            {
                "request_type": request_type,
                "content_type": content_type,
                "object_id": object_id,
                "group": group,
            },
        )

    async def _unsubscribe_target(self, data: dict):
        request_type = (data.get("request_type") or "").strip()
        content_type = (data.get("content_type") or "").strip()
        object_id = self._normalize_int(data.get("object_id"))

        if not request_type or not content_type or not object_id:
            await self._send_error(
                code="INVALID_UNSUBSCRIBE_TARGET_PAYLOAD",
                message="Missing request_type/content_type/object_id",
            )
            return

        group = self._target_group_name(request_type, content_type, object_id)

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

        await self._send_event(
            "unsubscribed_target",
            {
                "request_type": request_type,
                "content_type": content_type,
                "object_id": object_id,
                "group": group,
            },
        )

    # ------------------------------------------------------------
    # Review submit (immutable vote)
    # ------------------------------------------------------------
    async def _submit_review(self, data: dict):
        request_id = self._normalize_int(data.get("request_id"))
        new_status = (data.get("review_status") or "").strip()
        comment = (data.get("comment") or "").strip()

        if not request_id:
            await self._send_error(
                code="MISSING_REQUEST_ID",
                message="Missing request_id",
            )
            return

        if new_status not in (NO_OPINION, VIOLATION_CONFIRMED, VIOLATION_REJECTED):
            await self._send_error(
                code="INVALID_REVIEW_STATUS",
                message="Invalid review_status",
            )
            return

        # Vote must be final
        if new_status == NO_OPINION:
            await self._send_error(
                code="NO_OPINION_NOT_ALLOWED",
                message="NO_OPINION is not allowed to submit",
            )
            return

        # Fetch request
        req = await self._get_request(request_id)
        if not req:
            await self._send_error(
                code="REQUEST_NOT_FOUND",
                message="Request not found",
            )
            return

        # Must be assigned reviewer
        review = await self._get_review_slot(req.id, self.user.id)
        if not review:
            await self._send_error(
                code="REVIEWER_NOT_ASSIGNED",
                message="You are not assigned to this council review",
            )
            return

        # Immutable rule
        if review.review_status and review.review_status != NO_OPINION:
            await self._send_error(
                code="REVIEW_IMMUTABLE",
                message="Your vote is final and cannot be edited",
            )
            return

        ok, updated_review = await self._commit_review(
            review.id,
            new_status,
            comment,
        )
        if not ok:
            await self._send_error(
                code="REVIEW_SUBMIT_FAILED",
                message="Failed to submit review",
            )
            return

        # ACK only; other updates should be broadcast by signals/services
        await self._send_event(
            "review_submitted",
            {
                "request_id": req.id,
                "review_id": updated_review["id"],
                "review_status": updated_review["review_status"],
                "comment": updated_review["comment"],
                "reviewed_at": updated_review["reviewed_at"],
            },
        )

    # ------------------------------------------------------------
    # DB ops (async-safe)
    # ------------------------------------------------------------
    @database_sync_to_async
    def _get_request(self, request_id: int):
        try:
            return SanctuaryRequest.objects.get(id=request_id)
        except SanctuaryRequest.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_review_slot(self, request_id: int, user_id: int):
        try:
            qs = SanctuaryReview.objects.select_related("reviewer").filter(
                sanctuary_request_id=request_id,
                reviewer_id=user_id,
            )

            if hasattr(SanctuaryReview, "is_active"):
                qs = qs.filter(is_active=True)

            return qs.get()
        except SanctuaryReview.DoesNotExist:
            return None

    @database_sync_to_async
    def _commit_review(self, review_id: int, status: str, comment: str):
        try:
            with transaction.atomic():
                review = SanctuaryReview.objects.select_for_update().get(id=review_id)

                if review.review_status and review.review_status != NO_OPINION:
                    return False, None

                review.review_status = status
                review.comment = comment
                review.save(update_fields=["review_status", "comment", "reviewed_at"])

                return True, {
                    "id": review.id,
                    "review_status": review.review_status,
                    "comment": review.comment,
                    "reviewed_at": (
                        review.reviewed_at.isoformat()
                        if review.reviewed_at
                        else timezone.now().isoformat()
                    ),
                }

        except Exception as e:
            logger.warning(
                "[SanctuaryHandler] _commit_review failed: %s",
                e,
                exc_info=True,
            )
            return False, None