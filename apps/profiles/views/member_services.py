# apps/profiles/views/member_services.py

import logging

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.profiles.models.services import SpiritualService, MemberServiceType
from apps.profiles.serializers.services import SpiritualServiceSerializer, MemberServiceTypeSerializer
from apps.profiles.services.service_policies import get_policy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------------------------------------
class MemberServicesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_context(self):
        return {"request": self.request}

    # Services Catalog ------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='services-catalog', permission_classes=[IsAuthenticated])
    def services_catalog(self, request):
        qs = SpiritualService.objects.filter(is_active=True).order_by('is_sensitive', 'name')
        data = SpiritualServiceSerializer(qs, many=True, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='my-services', permission_classes=[IsAuthenticated])
    def my_services(self, request):
        member = request.user.member_profile
        qs = (
            MemberServiceType.objects
            .filter(member_service_types=member, is_active=True)
            .select_related('service')
        )
        data = MemberServiceTypeSerializer(qs, many=True, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------
    @action(
        detail=False, methods=['post'], url_path='services',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        permission_classes=[IsAuthenticated]
    )
    @transaction.atomic  # ensure all-or-nothing on errors
    def create_service(self, request):
        """Create a MemberServiceType and attach it to current member."""
        # light start log (helpful for tracing, not noisy)
        logger.info("member.services:create start ct=%s keys=%s",
                    request.content_type, list(request.data.keys()))

        # resolve member
        member = getattr(request.user, "member_profile", None)
        if not member:
            logger.warning("member.services:create no-member-profile user_id=%s", request.user.id)
            return Response({"detail": "Member profile not found for current user."},
                            status=status.HTTP_400_BAD_REQUEST)

        # ensure M2M manager exists
        if not hasattr(member, "service_types"):
            logger.error("member.services:create missing M2M 'service_types' on Member id=%s", member.id)
            return Response({"detail": "Server configuration error."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # validate input
        ser = MemberServiceTypeSerializer(data=request.data, context=self.get_serializer_context())
        if not ser.is_valid():
            logger.info("member.services:create invalid payload errors=%s", ser.errors)
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        # prevent duplicates for this member
        service = ser.validated_data["service"]
        if member.service_types.filter(service=service, is_active=True).exists():
            logger.info("member.services:create duplicate service member_id=%s service_id=%s", member.id, service.id)
            return Response({"detail": "This service is already added to your profile."},
                            status=status.HTTP_400_BAD_REQUEST)

        # create + attach
        try:
            instance = ser.save()  # status set by serializer based on is_sensitive
            member.service_types.add(instance)
        except Exception as e:
            logger.exception("member.services:create persistence failed member_id=%s", member.id)
            return Response({"detail": "Failed to create service item."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # response
        out = MemberServiceTypeSerializer(instance, context=self.get_serializer_context()).data
        logger.info("member.services:create ok member_id=%s mst_id=%s", member.id, instance.id)
        return Response(out, status=status.HTTP_201_CREATED)

    # ---------------------------------------------------------------
    @action(
        detail=False, methods=['patch'], url_path=r'services/(?P<pk>\d+)',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        permission_classes=[IsAuthenticated]
    )
    def update_service(self, request, pk=None):
        member = request.user.member_profile
        try:
            instance = (
                MemberServiceType.objects
                .select_related('service')
                .get(pk=pk, is_active=True)
            )
        except MemberServiceType.DoesNotExist:
            return Response({"detail": "Service item not found."}, status=status.HTTP_404_NOT_FOUND)

        # مالکیت: باید به همین member لینک شده باشد
        if not instance.member_service_types.filter(pk=member.pk).exists():
            return Response({"detail": "You don't have permission to modify this service."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data.pop('service_id', None)

        ser = MemberServiceTypeSerializer(instance, data=data, partial=True, context=self.get_serializer_context())
        ser.is_valid(raise_exception=True)
        ser.save()

        return Response(ser.data, status=status.HTTP_200_OK)

    # ---------------------------------------------------------------
    @action(detail=False, methods=['delete'], url_path=r'services/(?P<pk>\d+)', permission_classes=[IsAuthenticated])
    def delete_service(self, request, pk=None):
        member = request.user.member_profile
        try:
            instance = MemberServiceType.objects.select_related('service').get(pk=pk)
        except MemberServiceType.DoesNotExist:
            return Response({"detail": "Service item not found."}, status=status.HTTP_404_NOT_FOUND)

        # Ownership check: must belong to this member
        if not instance.member_service_types.filter(pk=member.pk).exists():
            return Response({"detail": "You don't have permission to remove this service."}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            # 1) remove file from storage (if any) to avoid orphaned objects
            if instance.document:
                instance.document.delete(save=False)

            # 2) Hard delete the record; M2M through rows will be removed automatically
            instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='services-policy', permission_classes=[IsAuthenticated])
    def policy(self, request):
        service_code = request.query_params.get("service", None)
        data = get_policy(service_code)
        return Response(data, status=status.HTTP_200_OK)

