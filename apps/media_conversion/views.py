# apps/media_conversion/views.py
import logging

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.media_conversion.models import MediaConversionJob
from apps.media_conversion.serializers import MediaConversionJobSerializer

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Permission gate (must NEVER raise)
# ------------------------------------------------------------
def _safe_can_view_target(request, target_obj) -> bool:
    """
    Best-effort permission gate:
    - Prefer VisibilityPolicy if available
    - Allow staff/superuser
    - Fallback to owner checks (TownLIT-style)
    """
    # 1) VisibilityPolicy (if exists)
    try:
        from apps.core.visibility.policy import VisibilityPolicy
        reason = VisibilityPolicy.gate_reason(viewer=request.user, obj=target_obj)
        return reason is None
    except Exception:
        pass

    # 2) staff/superuser always allowed
    try:
        if getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False):
            return True
    except Exception:
        pass

    # 3) owner checks (best-effort)
    try:
        owner_member = getattr(target_obj, "owner_member", None)
        if owner_member:
            u = getattr(owner_member, "name", None)
            if u and u.pk == getattr(request.user, "pk", None):
                return True

        owner_user = getattr(target_obj, "user", None)
        if owner_user and owner_user.pk == getattr(request.user, "pk", None):
            return True

        if hasattr(target_obj, "content_object"):
            owner = getattr(target_obj, "content_object", None)
            if owner and getattr(owner, "pk", None) == getattr(request.user, "pk", None):
                return True
            if owner and hasattr(owner, "name") and owner.name.pk == getattr(request.user, "pk", None):
                return True
    except Exception:
        pass

    return False


# ------------------------------------------------------------
# Target resolvers
# ------------------------------------------------------------
def _get_target_by_content_type(content_type_id: int, object_id: int):
    ct = ContentType.objects.get(id=content_type_id)
    Model = ct.model_class()
    if Model is None:
        raise ValueError("Invalid content_type_id.")
    return Model.objects.get(pk=object_id)


def _get_target_by_app_model(app_label: str, model: str, object_id: int):
    Model = apps.get_model(app_label, model)
    if Model is None:
        raise ValueError("Invalid app_label/model.")
    return Model.objects.get(pk=object_id)


def _get_target_by_slug(app_label: str, model: str, slug: str):
    Model = apps.get_model(app_label, model)
    if Model is None:
        raise ValueError("Invalid app_label/model.")

    try:
        Model._meta.get_field("slug")
    except FieldDoesNotExist:
        raise ValueError("Target model does not support slug lookup.")

    return Model.objects.get(slug=slug)


# ------------------------------------------------------------
# ViewSet
# ------------------------------------------------------------
class MediaConversionJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for polling media conversion jobs.

    Rules:
      - No global listing
      - Must be scoped to a target object
      - Permission gate enforced on target
    """
    serializer_class = MediaConversionJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Base queryset (no filtering here)
        return (
            MediaConversionJob.objects
            .select_related("content_type")
            .all()
            .order_by("-updated_at")
        )

    def list(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use /media-jobs/for-object/ or /media-jobs/for-slug/."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------------
    # Query by object
    # --------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="for-object")
    def for_object(self, request):
        qp = request.query_params
        field_name = (qp.get("field_name") or "").strip() or None

        try:
            # Resolve target
            if qp.get("content_type_id") and qp.get("object_id"):
                target = _get_target_by_content_type(
                    int(qp["content_type_id"]),
                    int(qp["object_id"]),
                )
            elif qp.get("app_label") and qp.get("model") and qp.get("object_id"):
                target = _get_target_by_app_model(
                    qp["app_label"].strip(),
                    qp["model"].strip(),
                    int(qp["object_id"]),
                )
            else:
                return Response(
                    {"detail": "Provide (content_type_id, object_id) OR (app_label, model, object_id)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Permission gate
            if not _safe_can_view_target(request, target):
                return Response({"detail": "Access restricted."}, status=status.HTTP_403_FORBIDDEN)

            ct = ContentType.objects.get_for_model(target.__class__)
            qs = self.get_queryset().filter(
                content_type=ct,
                object_id=target.pk,
            )

            if field_name:
                qs = qs.filter(field_name=field_name)

            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(
                    self.get_serializer(page, many=True).data
                )

            return Response(
                self.get_serializer(qs, many=True).data,
                status=status.HTTP_200_OK,
            )

        except ObjectDoesNotExist:
            return Response({"detail": "Target not found."}, status=status.HTTP_404_NOT_FOUND)

        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.exception("media_jobs.for_object failed qp=%s user=%s", dict(qp), getattr(request.user, "pk", None))
            return Response({"detail": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --------------------------------------------------------
    # Query by slug
    # --------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="for-slug")
    def for_slug(self, request):
        qp = request.query_params
        field_name = (qp.get("field_name") or "").strip() or None

        app_label = (qp.get("app_label") or "").strip()
        model = (qp.get("model") or "").strip()
        slug = (qp.get("slug") or "").strip()

        if not (app_label and model and slug):
            return Response(
                {"detail": "Provide (app_label, model, slug)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target = _get_target_by_slug(app_label, model, slug)

            if not _safe_can_view_target(request, target):
                return Response({"detail": "Access restricted."}, status=status.HTTP_403_FORBIDDEN)

            ct = ContentType.objects.get_for_model(target.__class__)
            qs = self.get_queryset().filter(
                content_type=ct,
                object_id=target.pk,
            )

            if field_name:
                qs = qs.filter(field_name=field_name)

            page = self.paginate_queryset(qs)
            if page is not None:
                return self.get_paginated_response(
                    self.get_serializer(page, many=True).data
                )

            return Response(
                self.get_serializer(qs, many=True).data,
                status=status.HTTP_200_OK,
            )

        except ObjectDoesNotExist:
            return Response({"detail": "Target not found."}, status=status.HTTP_404_NOT_FOUND)

        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.exception(
                "media_jobs.for_slug failed app_label=%s model=%s slug=%s user=%s",
                app_label, model, slug, getattr(request.user, "pk", None)
            )
            return Response({"detail": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
