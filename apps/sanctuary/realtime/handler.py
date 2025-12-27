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
    Sanctuary WS handler (Unified Envelope)

    Client -> Server:
      - type="subscribe"             {request_id}
      - type="unsubscribe"           {request_id}

      - type="subscribe_target"      {request_type, content_type, object_id}
      - type="unsubscribe_target"    {request_type, content_type, object_id}

      - type="review.submit"         {request_id, review_status, comment?}

    Server -> Client (ALWAYS):
      { type:"event", app:"sanctuary", event:"...", data:{...} }

    Backend -> WS via CentralConsumer.dispatch_event():
      handler.handle_backend_event({app, event, data})
    """

    APP = "sanctuary"

    def __init__(self, socket):
        self.socket = socket
        self.user = socket.user
        self.groups = set()

    # ------------------------------------------------------------
    # Central consumer calls this after connect
    # ------------------------------------------------------------
    async def on_connect(self):
        # Join global sanctuary group
        await self.socket.join_feature_group("sanctuary_global")
        # Unified ready event
        await self._send_event("ready", {"status": "ok"})

    async def on_disconnect(self):
        for g in list(self.groups):
            try:
                await self.socket.leave_feature_group(g)
            except Exception:
                pass
        self.groups.clear()

    # ------------------------------------------------------------
    # Client -> Server dispatcher
    # ------------------------------------------------------------
    async def handle(self, data: dict):
        t = data.get("type")

        if t == "subscribe":
            return await self._subscribe(data)

        if t == "unsubscribe":
            return await self._unsubscribe(data)

        # 🔥 Target-level subscriptions (counter sync)
        if t == "subscribe_target":
            return await self._subscribe_target(data)

        if t == "unsubscribe_target":
            return await self._unsubscribe_target(data)

        if t == "review.submit":
            return await self._submit_review(data)

        logger.debug("[SanctuaryHandler] Unknown client type=%s", t)
        await self._send_event("error", {"message": f"Unknown type '{t}'"})

    # ------------------------------------------------------------
    # Backend -> Client dispatcher
    # ------------------------------------------------------------
    async def handle_backend_event(self, payload: dict):
        """
        payload expected:
          { "app":"sanctuary", "event":"...", "data":{...} }
        """
        try:
            evt = payload.get("event")
            data = payload.get("data") or {}
            await self._send_event(evt or "unknown", data)
        except Exception as e:
            logger.error(
                "[SanctuaryHandler] handle_backend_event failed: %s",
                e,
                exc_info=True,
            )

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    async def _send_event(self, event: str, data: dict):
        """Unified envelope to client."""
        await self.socket.safe_send_json({
            "type": "event",
            "app": self.APP,
            "event": event,
            "data": data or {},
        })

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
    # Subscribe / Unsubscribe (Request-level)
    # ------------------------------------------------------------
    async def _subscribe(self, data: dict):
        request_id = self._normalize_int(data.get("request_id"))
        if not request_id:
            return await self._send_event("error", {"message": "Missing request_id"})

        group = self._request_group_name(request_id)

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event("subscribed", {"request_id": request_id})

    async def _unsubscribe(self, data: dict):
        request_id = self._normalize_int(data.get("request_id"))
        if not request_id:
            return await self._send_event("error", {"message": "Missing request_id"})

        group = self._request_group_name(request_id)

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

        await self._send_event("unsubscribed", {"request_id": request_id})

    # ------------------------------------------------------------
    # Subscribe / Unsubscribe (Target-level, counter sync)
    # ------------------------------------------------------------
    async def _subscribe_target(self, data: dict):
        request_type = (data.get("request_type") or "").strip()
        content_type = (data.get("content_type") or "").strip()
        object_id = self._normalize_int(data.get("object_id"))

        if not request_type or not content_type or not object_id:
            return await self._send_event(
                "error",
                {"message": "Missing request_type/content_type/object_id"},
            )

        group = self._target_group_name(request_type, content_type, object_id)

        await self.socket.join_feature_group(group)
        self.groups.add(group)

        await self._send_event("subscribed_target", {
            "request_type": request_type,
            "content_type": content_type,
            "object_id": object_id,
            "group": group,
        })

    async def _unsubscribe_target(self, data: dict):
        request_type = (data.get("request_type") or "").strip()
        content_type = (data.get("content_type") or "").strip()
        object_id = self._normalize_int(data.get("object_id"))

        if not request_type or not content_type or not object_id:
            return await self._send_event(
                "error",
                {"message": "Missing request_type/content_type/object_id"},
            )

        group = self._target_group_name(request_type, content_type, object_id)

        if group in self.groups:
            await self.socket.leave_feature_group(group)
            self.groups.discard(group)

        await self._send_event("unsubscribed_target", {
            "request_type": request_type,
            "content_type": content_type,
            "object_id": object_id,
            "group": group,
        })

    # ------------------------------------------------------------
    # Review submit (immutable vote)
    # ------------------------------------------------------------
    async def _submit_review(self, data: dict):
        request_id = self._normalize_int(data.get("request_id"))
        new_status = (data.get("review_status") or "").strip()
        comment = (data.get("comment") or "").strip()

        if not request_id:
            return await self._send_event("error", {"message": "Missing request_id"})

        if new_status not in (NO_OPINION, VIOLATION_CONFIRMED, VIOLATION_REJECTED):
            return await self._send_event("error", {"message": "Invalid review_status"})

        # Vote must be final
        if new_status == NO_OPINION:
            return await self._send_event(
                "error",
                {"message": "NO_OPINION is not allowed to submit"},
            )

        # Fetch request
        req = await self._get_request(request_id)
        if not req:
            return await self._send_event("error", {"message": "Request not found"})

        # Must be assigned reviewer
        review = await self._get_review_slot(req.id, self.user.id)
        if not review:
            return await self._send_event(
                "error",
                {"message": "You are not assigned to this council review"},
            )

        # Immutable rule
        if review.review_status and review.review_status != NO_OPINION:
            return await self._send_event(
                "error",
                {"message": "Your vote is final and cannot be edited"},
            )

        # Save vote (atomic)
        ok, updated_review = await self._commit_review(
            review.id,
            new_status,
            comment,
        )
        if not ok:
            return await self._send_event(
                "error",
                {"message": "Failed to submit review"},
            )

        # ACK only (signals will broadcast updates)
        await self._send_event("review_submitted", {
            "request_id": req.id,
            "review_id": updated_review["id"],
            "review_status": updated_review["review_status"],
            "comment": updated_review["comment"],
            "reviewed_at": updated_review["reviewed_at"],
        })

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
                r = SanctuaryReview.objects.select_for_update().get(id=review_id)

                if r.review_status and r.review_status != NO_OPINION:
                    return False, None

                r.review_status = status
                r.comment = comment
                r.save(update_fields=["review_status", "comment", "reviewed_at"])

                return True, {
                    "id": r.id,
                    "review_status": r.review_status,
                    "comment": r.comment,
                    "reviewed_at": (
                        r.reviewed_at.isoformat()
                        if r.reviewed_at
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
