# apps/profiles/views/fellowship.py

import logging

from django.db import transaction
from django.db.models import Q

from rest_framework import status, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth import get_user_model

from apps.core.pagination import ConfigurablePagination
from apps.core.security.decorators import require_litshield_access

from apps.profiles.models.member import Member
from apps.profiles.models.relationships import Friendship, Fellowship
from apps.profiles.serializers.fellowships import FellowshipSerializer
from apps.accounts.serializers.user_serializers import SimpleCustomUserSerializer
from apps.profiles.services.symmetric_fellowship import (
    add_symmetric_fellowship,
    remove_symmetric_fellowship,
)

CustomUser = get_user_model()
logger = logging.getLogger(__name__)


# FELLOWSHIP View --------------------------------------------------------------------------------------------
class FellowshipViewSet(viewsets.ModelViewSet):
    queryset = Fellowship.objects.all()
    serializer_class = FellowshipSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ConfigurablePagination
    pagination_page_size = 20

    # --- helper: serialize list and drop None items ---
    def _serialize_nonnull(self, qs):
        """
        Serialize a queryset of Fellowships and drop None items
        (produced by child.to_representation when endpoints are deleted).
        """
        ser = self.get_serializer(qs, many=True, context=self.get_serializer_context())
        # DRF already evaluated .data -> list; filter out None
        return [item for item in ser.data if item is not None]

    def get_queryset(self):
        user = self.request.user
        return (
            Fellowship.objects
            .select_related(
                "from_user", "to_user",
                "from_user__label", "from_user__member_profile",
                "to_user__label", "to_user__member_profile",
            )
            .filter(Q(from_user=user) | Q(to_user=user))
            .filter(from_user__is_deleted=False, to_user__is_deleted=False)
            .order_by('-created_at')
        )

    
    def perform_create(self, serializer):
        try:
            if 'to_user_id' not in serializer.validated_data:
                raise serializers.ValidationError({"error": "The 'to_user_id' field is required."})

            to_user = serializer.validated_data['to_user_id']
            fellowship_type = serializer.validated_data['fellowship_type']
            reciprocal_fellowship_type = serializer.validated_data.get('reciprocal_fellowship_type')

            # hard guards
            if getattr(self.request.user, "is_deleted", False):
                raise serializers.ValidationError({"error": "Your account is deactivated. Reactivate to manage fellowships."})
            if getattr(to_user, "is_deleted", False):
                raise serializers.ValidationError({"error": "You cannot send a fellowship request to a deactivated account."})

            if to_user == self.request.user:
                raise serializers.ValidationError({"error": "You cannot send a fellowship request to yourself."})

            # --- Confidant safety: block hidden Confidant re-requests silently ---
            # If user is in 'hide_confidants' mode and this is a Confidant request,
            # and the target is already an accepted Confidant, return a generic error.
            try:
                member = self.request.user.member_profile
                hide_confidants = getattr(member, "hide_confidants", False)
            except Member.DoesNotExist:
                hide_confidants = False

            if hide_confidants and fellowship_type == "Confidant":
                is_hidden_confidant = Fellowship.objects.filter(
                    from_user=self.request.user,
                    to_user=to_user,
                    fellowship_type="Confidant",
                    status="Accepted",
                ).exists()
                if is_hidden_confidant:
                    # Generic error message to avoid leaking security state
                    raise serializers.ValidationError({
                        "error": "Unable to process this request at the moment."
                    })

            # pending dup check (exclude deleted endpoints)
            existing_request = (
                Fellowship.objects
                .filter(
                    from_user=self.request.user,
                    to_user=to_user,
                    fellowship_type=fellowship_type,
                    status='Pending',
                    from_user__is_deleted=False,
                    to_user__is_deleted=False,
                )
            )
            if existing_request.exists():
                raise serializers.ValidationError({"error": "A similar fellowship request already exists."})

            serializer.save(from_user=self.request.user, reciprocal_fellowship_type=reciprocal_fellowship_type)

        except serializers.ValidationError as e:
            raise e
        except Exception:
            raise serializers.ValidationError({"error": "An unexpected error occurred."})


    @require_litshield_access("covenant")
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response({
            "message": "Fellowship request created successfully!",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='search-friends', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def search_friends(self, request):
        """
        Search within accepted friends only, with:
        - optimized queryset
        - view-aware pagination (ConfigurablePagination)
        - confidant safety rules
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        try:
            # ------------------------------------------------------------
            # Collect accepted friendship counterpart IDs (fast + safe)
            # ------------------------------------------------------------
            edges = (
                Friendship.objects
                .filter(
                    Q(from_user=request.user) | Q(to_user=request.user),
                    status="accepted",
                    is_active=True,
                )
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .values("from_user_id", "to_user_id")
            )

            uid = request.user.id
            friend_ids = {
                e["to_user_id"] if e["from_user_id"] == uid else e["from_user_id"]
                for e in edges
            }

            if not friend_ids:
                return Response([], status=status.HTTP_200_OK)

            # ------------------------------------------------------------
            # Base friends queryset
            # ------------------------------------------------------------
            friends = (
                CustomUser.objects
                .select_related("label", "member_profile")
                .filter(id__in=friend_ids, is_deleted=False, is_active=True)
                .filter(
                    Q(username__icontains=query) |
                    Q(email__icontains=query) |
                    Q(name__icontains=query) |
                    Q(family__icontains=query)
                )
                .distinct()
            )

            # ------------------------------------------------------------
            # Confidant safety (hide accepted confidants if enabled)
            # ------------------------------------------------------------
            try:
                member = request.user.member_profile
                hide_confidants = getattr(member, "hide_confidants", False)
            except Member.DoesNotExist:
                hide_confidants = False

            if hide_confidants:
                hidden_confidant_ids = Fellowship.objects.filter(
                    from_user=request.user,
                    fellowship_type="Confidant",
                    status="Accepted",
                ).values_list("to_user_id", flat=True)

                friends = friends.exclude(id__in=hidden_confidant_ids)

            # ------------------------------------------------------------
            # Pagination (VIEW-AWARE, CORE-COMPATIBLE)
            # ------------------------------------------------------------
            page = self.paginate_queryset(friends)
            serializer = SimpleCustomUserSerializer(
                page,
                many=True,
                context={"request": request}
            )

            return self.get_paginated_response(serializer.data)

        except Exception:
            logger.exception("🔥 search_friends failed")
            return Response(
                {"error": "Unable to search friends"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='sent-requests', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def sent_requests(self, request):
        try:
            qs = (
                Fellowship.objects
                .select_related(
                    "from_user", "to_user",
                    "from_user__label", "from_user__member_profile",
                    "to_user__label", "to_user__member_profile",
                )
                .filter(from_user=request.user, status='Pending')
                # defense-in-depth (already handled in serializer, but cheap filter too)
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .order_by('-created_at')
            )
            clean = self._serialize_nonnull(qs)
            return Response(clean, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during sent_requests: {e}")
            return Response({'error': 'Unable to fetch sent requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='received-requests', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def received_requests(self, request):
        try:
            qs = (
                Fellowship.objects
                .select_related(
                    "from_user", "to_user",
                    "from_user__label", "from_user__member_profile",
                    "to_user__label", "to_user__member_profile",
                )
                .filter(to_user=request.user, status='Pending')
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .order_by('-created_at')
            )
            clean = self._serialize_nonnull(qs)
            return Response(clean, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during received_requests: {e}")
            return Response({'error': 'Unable to fetch received requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='fellowship-list', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def fellowship_list(self, request):
        try:
            user = request.user
            fellowships = (
                Fellowship.objects
                .select_related(
                    "from_user", "to_user",
                    "from_user__member_profile", "to_user__member_profile",
                    "from_user__label", "to_user__label",
                )

                .filter(Q(from_user=user) | Q(to_user=user), status='Accepted')
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
            )

            processed_relationships = set()
            result = []

            should_hide_confidants = getattr(user.member_profile, "hide_confidants", False)

            for fellowship in fellowships:
                if fellowship.from_user == user:
                    opposite_user = fellowship.to_user
                    relationship_type = fellowship.fellowship_type
                else:
                    opposite_user = fellowship.from_user
                    relationship_type = fellowship.reciprocal_fellowship_type

                # skip deleted counterpart (defense in depth)
                if getattr(opposite_user, "is_deleted", False):
                    continue

                if should_hide_confidants and relationship_type == "Confidant":
                    continue

                if relationship_type == "Confidant":
                    if not getattr(user, "pin_security_enabled", False):
                        continue

                if relationship_type == "Entrusted":
                    try:
                        if not getattr(opposite_user, "pin_security_enabled", False):
                            continue
                    except Exception:
                        continue

                key = (opposite_user.id, relationship_type)
                if key in processed_relationships:
                    continue

                is_hidden_by_confidants = (
                    getattr(getattr(opposite_user, "member_profile", None), "is_hidden_by_confidants", None)
                    if relationship_type == "Entrusted" else None
                )

                user_data = SimpleCustomUserSerializer(
                    opposite_user,
                    context={'request': request, 'fellowship_ids': {opposite_user.id: fellowship.id}}
                ).data

                result.append({
                    'user': user_data,
                    'relationship_type': relationship_type,
                    'is_hidden_by_confidants': is_hidden_by_confidants,
                })
                processed_relationships.add(key)

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in fellowship_list: {e}")
            return Response({'error': 'Unable to retrieve fellowship list'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='accept-request', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def accept_request(self, request, pk=None):
        try:
            fellowship = self.get_object()
            if fellowship.to_user != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            # block if requester is deleted now
            if getattr(fellowship.from_user, "is_deleted", False):
                return Response({'error': 'This request is no longer valid (requester deactivated).'}, status=status.HTTP_400_BAD_REQUEST)

            reciprocal_fellowship_type = request.data.get('reciprocalFellowshipType')
            if not reciprocal_fellowship_type:
                return Response({'error': 'Reciprocal fellowship type is required.'}, status=status.HTTP_400_BAD_REQUEST)

            if fellowship.status == 'Pending':
                fellowship.status = 'Accepted'
                fellowship.save()

                add_symmetric_fellowship(
                    from_user=fellowship.from_user,
                    to_user=fellowship.to_user,
                    fellowship_type=fellowship.fellowship_type,
                    reciprocal_fellowship_type=reciprocal_fellowship_type,
                )
                return Response({'message': 'Fellowship accepted'}, status=status.HTTP_200_OK)

            return Response({'error': 'Invalid request or already processed'}, status=status.HTTP_400_BAD_REQUEST)

        except Fellowship.DoesNotExist:
            return Response({'error': 'Fellowship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in accept_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='decline-request', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def decline_request(self, request, pk=None):
        """
        Decline a pending request:
        1) set status -> 'Declined' and save (fires post_save signal -> notification)
        2) then delete the row (we don't keep declined rows)
        """
        try:
            reciprocal_fellowship_type = request.data.get('reciprocalFellowshipType')
            if not reciprocal_fellowship_type:
                return Response({'error': 'Reciprocal fellowship type is required.'}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                fellowship = (Fellowship.objects
                            .select_for_update()
                            .filter(id=pk,
                                    to_user=request.user,
                                    reciprocal_fellowship_type=reciprocal_fellowship_type,
                                    status='Pending')
                            .first())
                if not fellowship:
                    return Response({'error': 'Fellowship not found or already processed.'}, status=status.HTTP_404_NOT_FOUND)

                # 1) trigger notification
                fellowship.status = 'Declined'
                fellowship.save(update_fields=['status'])  # ✅ post_save → notif

                # 2) cleanup row (no need to keep declined)
                fellowship.delete()

            logger.info(f"Fellowship {pk} declined+deleted by user {request.user.id}.")
            return Response({'message': 'Fellowship request declined.'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Unexpected error in decline_request: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='cancel-request', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def cancel_request(self, request, pk=None):
        """
        Cancel my own pending outbound request:
        1) set status -> 'Cancelled' and save (fires post_save signal -> notification)
        2) then delete the row (we don't keep cancelled)
        """
        try:
            with transaction.atomic():
                fellowship = (Fellowship.objects
                            .select_for_update()
                            .get(id=pk))

                if fellowship.from_user != request.user:
                    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

                if fellowship.status != 'Pending':
                    return Response({'error': 'Only pending requests can be canceled'}, status=status.HTTP_400_BAD_REQUEST)

                # 1) trigger notification
                fellowship.status = 'Cancelled'
                fellowship.save(update_fields=['status'])  # ✅ post_save → notif

                # 2) cleanup row
                fellowship.delete()

            logger.info(f"Fellowship {pk} cancelled+deleted by user {request.user.id}.")
            return Response({'message': 'Fellowship request canceled.'}, status=status.HTTP_200_OK)

        except Fellowship.DoesNotExist:
            return Response({'error': 'Fellowship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in cancel_request: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    # ---------------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='delete-fellowship', permission_classes=[IsAuthenticated])
    @require_litshield_access("covenant")
    def delete_fellowship(self, request):
        """
        Remove an accepted fellowship bidirectionally (unpair):
        Delegates to a helper that:
        - sets 'Cancelled' + save() on exactly ONE side (fires a single notification burst),
        - then deletes BOTH sides.
        """
        try:
            initiator = request.user
            counterpart_id = request.data.get('fellowshipId')
            relationship_type = request.data.get('relationshipType')

            if not counterpart_id or not relationship_type:
                return Response({'error': 'Counterpart ID and relationship type are required.'},
                                status=status.HTTP_400_BAD_REQUEST)

            counterpart_user = CustomUser.objects.filter(id=counterpart_id).first()
            if not counterpart_user:
                return Response({'error': 'Counterpart user not found.'}, status=status.HTTP_404_NOT_FOUND)

            ok = remove_symmetric_fellowship(initiator, counterpart_user, relationship_type)
            if ok:
                return Response({'message': 'Fellowship deleted successfully.'}, status=status.HTTP_200_OK)
            return Response({'error': 'Failed to delete fellowship.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Unexpected error in delete_fellowship: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

