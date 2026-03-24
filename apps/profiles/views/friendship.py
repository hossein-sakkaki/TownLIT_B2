# apps/profiles/views/friendship.py

import logging

from django.db.models import Q, Case, When, Value, IntegerField
from django.db.models.functions import Lower, Substr

from rest_framework import status, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth import get_user_model

from apps.core.pagination import ConfigurablePagination

from apps.profiles.models.member import Member
from apps.profiles.models.relationships import Friendship, Fellowship
from apps.profiles.serializers.friendships import FriendshipSerializer
from apps.accounts.serializers.user_serializers import (
    SimpleCustomUserSerializer,
    UserMiniSerializer,
)
from apps.profiles.serializers.friendships import PeopleSuggestionSerializer
from apps.profiles.services.symmetric_friendship import (
    add_symmetric_friendship,
    remove_symmetric_friendship,
)
from apps.profiles.selectors.friends import get_friend_user_ids
from apps.profiles.selectors.common_suggestions import suggest_friends_for_requests_tab
from apps.profiles.selectors.friendship_suggestions import suggest_friends_for_friends_tab
from apps.profiles.selectors.people_suggestions import get_people_suggestions_queryset

CustomUser = get_user_model()
logger = logging.getLogger(__name__)




# FRIENDSHIP View --------------------------------------------------------------------------------------------
class FriendshipViewSet(viewsets.ModelViewSet):
    queryset = Friendship.objects.all()
    serializer_class = FriendshipSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ConfigurablePagination
    pagination_page_size = 20

    def get_queryset(self):
        user = self.request.user
        return (
            Friendship.objects
            .filter(Q(to_user=user) | Q(from_user=user))
            # exclude any edge where either endpoint is deleted
            .filter(from_user__is_deleted=False, to_user__is_deleted=False)
            .order_by('-created_at')
        )
            
    def perform_create(self, serializer):
        try:
            if 'to_user_id' not in serializer.validated_data:
                logger.warning("Missing 'to_user_id' in request data.")
                raise serializers.ValidationError({"to_user_id": "This field is required."})

            to_user = serializer.validated_data['to_user_id']

            if not to_user.is_active or getattr(to_user, "is_deleted", False):
                raise serializers.ValidationError(
                    "You cannot send a friend request to this account."
                )

            if to_user == self.request.user:
                logger.warning(f"User {self.request.user.id} tried to send a friend request to themselves.")
                raise serializers.ValidationError("You cannot send a friend request to yourself.")

            # Check for existing active requests
            existing_request = Friendship.objects.filter(
                from_user=self.request.user,
                to_user=to_user,
                is_active=True
            ).exclude(status='declined')
            if existing_request.exists():
                logger.warning(f"Duplicate friend request from user {self.request.user.id} to {to_user.id}.")
                raise serializers.ValidationError("Friendship request already exists.")

            # Check for a reverse friend request
            reverse_request = Friendship.objects.filter(
                from_user=to_user,
                to_user=self.request.user,
                is_active=True,
                status='pending'
            ).exists()
            if reverse_request:
                logger.warning(f"Reverse friend request exists from user {to_user.id} to {self.request.user.id}.")
                raise serializers.ValidationError(
                    "A friend request from this user is already pending. Please respond to that request instead."
                )

            serializer.save(from_user=self.request.user, to_user=to_user, status='pending')
            logger.info(f"Friend request created: {self.request.user.id} -> {to_user.id}")

        except serializers.ValidationError as e:
            logger.error(f"Validation error while creating friend request: {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while creating friend request: {e}")
            raise serializers.ValidationError("An unexpected error occurred.")
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        # Response with custom message and data
        return Response({
            "message": "Friend request sent successfully!",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    # ------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='search-users', permission_classes=[IsAuthenticated])
    def search_users(self, request):
        """
        Fast user search with:
        - optimized queryset (select_related + only)
        - view-aware pagination (ConfigurablePagination)
        - friend status (friend / sent request / received request)
        - excluding deleted users and self
        """
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response([], status=status.HTTP_200_OK)

        try:
            # ------------------------------------------------------------
            # Optimized user lookup
            # ------------------------------------------------------------
            users = (
                CustomUser.objects
                .select_related("label", "member_profile")
                .only(
                    "id", "username", "name", "family", "email",
                    "label__id", "label__name",
                    "member_profile__id",
                    "image_name",
                )
                .filter(
                    Q(username__icontains=query) |
                    Q(name__icontains=query) |
                    Q(family__icontains=query) |
                    Q(email__icontains=query)
                )
                .exclude(id=request.user.id)
                .filter(is_active=True, is_deleted=False)
                .distinct()
            )

            # ------------------------------------------------------------
            # Friendship + request state lookups
            # ------------------------------------------------------------
            friend_edges = Friendship.objects.filter(
                Q(from_user=request.user, status="accepted") |
                Q(to_user=request.user, status="accepted")
            ).values("from_user", "to_user")

            uid = request.user.id
            friend_ids = {
                e["to_user"] if e["from_user"] == uid else e["from_user"]
                for e in friend_edges
            }

            sent_request_map = {
                r["to_user"]: r["id"]
                for r in Friendship.objects.filter(
                    from_user=request.user,
                    status="pending"
                ).values("to_user", "id")
            }

            received_request_map = {
                r["from_user"]: r["id"]
                for r in Friendship.objects.filter(
                    to_user=request.user,
                    status="pending"
                ).values("from_user", "id")
            }

            # ------------------------------------------------------------
            # Pagination (VIEW-AWARE, CORE-COMPATIBLE)
            # ------------------------------------------------------------
            page = self.paginate_queryset(users)
            serializer = SimpleCustomUserSerializer(
                page,
                many=True,
                context={
                    "request": request,
                    "friend_ids": friend_ids,
                    "sent_request_map": sent_request_map,
                    "received_request_map": received_request_map,
                }
            )

            return self.get_paginated_response(serializer.data)

        except Exception as e:
            logger.exception("🔥 search_users failed")
            return Response(
                {"error": "Unable to search users"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ------------------------------------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='sent-requests', permission_classes=[IsAuthenticated])
    def sent_requests(self, request):
        try:
            qs = (
                Friendship.objects
                .filter(from_user=request.user, status='pending')
                .filter(to_user__is_active=True, to_user__is_deleted=False)
            )
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during sent_requests: {e}")
            return Response({'error': 'Unable to fetch sent requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='received-requests', permission_classes=[IsAuthenticated])
    def received_requests(self, request):
        try:
            qs = (
                Friendship.objects
                .filter(to_user=request.user, status='pending')
                .filter(from_user__is_deleted=False)
                .filter(from_user__is_active=True, from_user__is_deleted=False)
            )
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error during received_requests: {e}")
            return Response({'error': 'Unable to fetch received requests'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['get'],
        url_path='friends-list',
        permission_classes=[IsAuthenticated]
    )
    def friends_list(self, request):
        """
        Return optimized list of friends with:
        - alphabetical ordering groups,
        - full serializer context (friend_ids + friendship_ids),
        - fast avatar URLs (via serializer),
        - correct friendship_id for frontend compatibility.
        """
        try:
            user = request.user

            # --- Load friendship edges (accepted + active) ----------------------------
            edges = (
                Friendship.objects
                .filter(
                    Q(from_user=user) | Q(to_user=user),
                    status='accepted',
                    is_active=True,
                )
                .filter(from_user__is_deleted=False, to_user__is_deleted=False)
                .values('id', 'from_user_id', 'to_user_id')
            )

            # --- Build counterpart IDs and friendship_id map -------------------------
            counterpart_ids = set()
            friendship_ids_map = {}   # { user_id: friendship_row_id }
            uid = user.id

            for edge in edges:
                fid = edge['from_user_id']
                tid = edge['to_user_id']

                # find the "other" user
                counterpart = tid if fid == uid else fid
                counterpart_ids.add(counterpart)

                # map that user to the friendship row ID
                friendship_ids_map[counterpart] = edge['id']

            # friend_ids = just counterpart IDs
            friend_ids = counterpart_ids

            # --- Query users with full select_related used by serializer -------------
            friends_qs = (
                CustomUser.objects
                .filter(id__in=counterpart_ids, is_active=True, is_deleted=False)
                .select_related(
                    "label", 
                    "member_profile" 
                )
            )

            # --- Sorting annotations --------------------------------------------------
            first_char = Substr('username', 1, 1)

            group = Case(
                When(username__startswith='_', then=Value(2)),       # group 2: starts with "_"
                When(username__regex=r'^[A-Za-z]', then=Value(0)),  # group 0: A–Z
                default=Value(1),                                   # group 1: others
                output_field=IntegerField(),
            )

            friends_qs = (
                friends_qs
                .annotate(
                    sort_group=group,
                    username_lower=Lower('username'),
                    first_char_annot=first_char,  # for debugging if needed
                )
                .order_by('sort_group', 'username_lower')
            )

            # --- Optional limit ------------------------------------------------------
            limit = request.query_params.get('limit')
            if limit:
                try:
                    lim = max(0, int(limit))
                    if lim:
                        friends_qs = friends_qs[:lim]
                except ValueError:
                    pass  # ignore invalid input

            # --- Serializer with ALL required context --------------------------------
            ser = SimpleCustomUserSerializer(
                friends_qs,
                many=True,
                context={
                    "request": request,

                    # required for serializer logic
                    "friend_ids": friend_ids,
                    "friendship_ids": friendship_ids_map,

                    # optional (for compatibility with other endpoints)
                    "sent_request_map": {},
                    "received_request_map": {},
                    "fellowship_ids": {},
                }
            )

            return Response(
                {"results": ser.data, "meta": {"count": len(counterpart_ids)}},
                status=status.HTTP_200_OK
            )

        except Exception:
            logger.exception("Error in friends_list")
            return Response(
                {"error": "Unable to retrieve friends list"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['get'],
        url_path='friends-suggestions',
        permission_classes=[IsAuthenticated]
    )
    def friends_suggestions(self, request):
        """Return suggestions for the Friends tab."""
        user = request.user
        limit = int(request.query_params.get('limit', 5))

        # suggestions may be a list -> wrap into queryset when possible
        suggestions = suggest_friends_for_friends_tab(user, limit)

        # If it's a QuerySet → annotate & optimize
        if hasattr(suggestions, "select_related"):
            suggestions = suggestions.select_related(
                "label",
                "member_profile"
            )
        else:
            # If it's a list → leave as-is
            suggestions = list(suggestions)

        serializer = SimpleCustomUserSerializer(
            suggestions,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['get'],
        url_path='requests-suggestions',
        permission_classes=[IsAuthenticated]
    )
    def requests_suggestions(self, request):
        """Return suggestions for the Requests tab."""
        user = request.user
        limit = int(request.query_params.get('limit', 5))

        suggestions = suggest_friends_for_requests_tab(user, limit)

        # Detect queryset vs list
        if hasattr(suggestions, "select_related"):
            suggestions = suggestions.select_related(
                "label",
                "member_profile"
            )
        else:
            suggestions = list(suggestions)

        serializer = SimpleCustomUserSerializer(
            suggestions,
            many=True,
            context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    # People suggestions --------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        url_path="people-suggestions",
        permission_classes=[IsAuthenticated],
    )
    def people_suggestions(self, request):
        """
        Square → People tab (paged).

        Returns:
          - ranked users (20/page)
          - mutual_friends_count (annotated in selector)
          - mutual_friends preview (list of mini users: username + profile_url clickable)
        """
        try:
            viewer = request.user

            # 1) Ranked suggestions queryset (your selector)
            qs = get_people_suggestions_queryset(viewer)

            # 2) Pagination
            page = self.paginate_queryset(qs)
            if page is None:
                page = list(qs[: getattr(self, "pagination_page_size", 20)])

            candidate_ids = [u.id for u in page]

            # 3) Build mutual friends preview map (bulk, for only this page)
            viewer_friend_ids = set(get_friend_user_ids(viewer))
            mutual_preview_map = {cid: [] for cid in candidate_ids}

            if viewer_friend_ids and candidate_ids:
                # edges connecting (viewer friends) <-> (candidates)
                edges = (
                    Friendship.objects
                    .filter(status="accepted", is_active=True)
                    .filter(
                        Q(from_user_id__in=viewer_friend_ids, to_user_id__in=candidate_ids) |
                        Q(to_user_id__in=viewer_friend_ids, from_user_id__in=candidate_ids)
                    )
                    .values("from_user_id", "to_user_id")
                )

                # candidate_id -> set(mutual_friend_id)
                mutual_ids_map = {cid: set() for cid in candidate_ids}

                for e in edges:
                    a = e["from_user_id"]
                    b = e["to_user_id"]

                    if a in candidate_ids and b in viewer_friend_ids:
                        mutual_ids_map[a].add(b)
                    elif b in candidate_ids and a in viewer_friend_ids:
                        mutual_ids_map[b].add(a)

                # Keep preview small (UI-friendly)
                PREVIEW_LIMIT = 3

                # flatten ids (one fetch)
                all_mutual_ids = set()
                for cid, mids in mutual_ids_map.items():
                    mids_list = list(mids)[:PREVIEW_LIMIT]
                    mutual_ids_map[cid] = mids_list
                    all_mutual_ids.update(mids_list)

                if all_mutual_ids:
                    mutual_users = (
                        type(viewer).objects
                        .filter(id__in=all_mutual_ids, is_active=True, is_deleted=False)
                        .select_related("label", "member_profile")
                    )
                    mutual_by_id = {u.id: u for u in mutual_users}

                    # serialize per candidate
                    for cid, mids in mutual_ids_map.items():
                        objs = [mutual_by_id[mid] for mid in mids if mid in mutual_by_id]
                        mutual_preview_map[cid] = UserMiniSerializer(
                            objs,
                            many=True,
                            context={"request": request},
                        ).data

            # 4) Serialize candidates (includes mutual preview via context)
            serializer = PeopleSuggestionSerializer(
                page,
                many=True,
                context={
                    "request": request,
                    "mutual_preview_map": mutual_preview_map,
                },
            )

            return self.get_paginated_response(serializer.data)

        except Exception:
            logger.exception("Error in people_suggestions")
            return Response(
                {"error": "Unable to retrieve people suggestions"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=True,
        methods=['post'],
        url_path='accept-friend-request',
        permission_classes=[IsAuthenticated]
    )
    def accept_friend_request(self, request, pk=None):
        try:
            # Preload relationships needed by serializer
            friendship = self.get_queryset().select_related(
                "from_user__label",
                "from_user__member_profile",
                "to_user__label",
                "to_user__member_profile",
            ).get(pk=pk)

            # Only the receiver may accept
            if friendship.to_user != request.user:
                logger.warning(f"User {request.user.id} tried to accept a friendship not directed to them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            # Cannot accept request from deleted account
            if getattr(friendship.from_user, "is_deleted", False):
                return Response(
                    {'error': 'This request is no longer valid (sender deactivated).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Cannot accept request from inactive account
            if not friendship.from_user.is_active:
                return Response(
                    {'error': 'This request is no longer valid.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Process pending request
            if friendship.status == 'pending':
                friendship.status = 'accepted'
                friendship.save()

                # Make symmetric friendship
                success = add_symmetric_friendship(
                    friendship.from_user,
                    friendship.to_user
                )

                if not success:
                    logger.error(
                        f"Failed to create symmetric friendship for {friendship.from_user.id} and {friendship.to_user.id}"
                    )
                    return Response(
                        {'error': 'Failed to create symmetric friendship'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # Serialize the new friend (optimized)
                friend_data = SimpleCustomUserSerializer(
                    friendship.from_user,
                    context={"request": request}
                ).data

                return Response(
                    {'message': 'Friendship accepted', 'friend': friend_data},
                    status=status.HTTP_200_OK
                )

            # Already processed
            logger.info(f"Friendship {friendship.id} already processed or invalid status.")
            return Response(
                {'error': 'Invalid request or already processed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Friendship.DoesNotExist:
            logger.error(f"Friendship with id {pk} not found.")
            return Response({'error': 'Friendship request not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Unexpected error in accept_friend_request: {e}")
            return Response(
                {'error': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        
    @action(detail=True, methods=['post'], url_path='decline-friend-request', permission_classes=[IsAuthenticated])
    def decline_friend_request(self, request, pk=None):
        try:
            friendship = self.get_object()
            if friendship.to_user != request.user:
                logger.warning(f"User {request.user.id} tried to decline a friendship not directed to them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            if friendship.status == 'pending':
                friendship.status = 'declined'
                friendship.is_active = False
                friendship.save()
                logger.info(f"Friendship {friendship.id} declined by user {request.user.id}.")
                return Response({'message': 'Friendship declined'}, status=status.HTTP_200_OK)

            logger.info(f"Friendship {friendship.id} already processed or invalid status.")
            return Response({'error': 'Invalid request or already processed'}, status=status.HTTP_400_BAD_REQUEST)
        except Friendship.DoesNotExist:
            logger.error(f"Friendship with id {pk} not found.")
            return Response({'error': 'Friendship request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in decline_friend_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['delete'], url_path='cancel-request', permission_classes=[IsAuthenticated])
    def cancel_friend_request(self, request, pk=None):
        try:
            friendship = self.get_object()
            if friendship.from_user != request.user:
                logger.warning(f"User {request.user.id} tried to cancel a friendship not initiated by them.")
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            if friendship.status != 'pending':
                logger.info(f"Friendship {friendship.id} cannot be canceled because it is not pending.")
                return Response({'error': 'Only pending requests can be canceled'}, status=status.HTTP_400_BAD_REQUEST)

            friendship.is_active = False
            friendship.status = 'cancelled'
            friendship.save()
            logger.info(f"Friendship {friendship.id} canceled by user {request.user.id}.")
            return Response({'message': 'Friend request canceled.'}, status=status.HTTP_200_OK)
        except Friendship.DoesNotExist:
            logger.error(f"Friendship with id {pk} not found.")
            return Response({'error': 'Friend request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error in cancel_friend_request: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['post'],
        url_path='delete-friendships',
        permission_classes=[IsAuthenticated]
    )
    def delete_friendship(self, request):
        """
        Delete an accepted friendship (symmetric remove).
        Supports both old 'friendshipId' and new 'friendship_id'.
        """
        try:
            initiator = request.user

            # Support both old and new field names
            friendship_id = (
                request.data.get("friendship_id") or
                request.data.get("friendshipId")
            )

            if not friendship_id:
                logger.warning(f"User {initiator.id} attempted deletion with no friendship_id.")
                return Response(
                    {"error": "friendship_id is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Load the friendship row
            friendship = (
                Friendship.objects
                .select_related(
                    "from_user__label", "from_user__member_profile",
                    "to_user__label",   "to_user__member_profile"
                )
                .filter(
                    id=friendship_id,
                    status="accepted",
                    is_active=True
                )
                .first()
            )

            if not friendship:
                logger.warning(f"Friendship not found for delete: id={friendship_id}")
                return Response(
                    {"error": "Friendship not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Ensure the current user is a participant
            if friendship.from_user_id != initiator.id and friendship.to_user_id != initiator.id:
                logger.warning(f"User {initiator.id} tried to delete friendship not belonging to them.")
                return Response(
                    {"error": "You do not have permission to delete this friendship."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Identify counterpart
            counterpart = (
                friendship.to_user
                if friendship.from_user_id == initiator.id
                else friendship.from_user
            )

            # LITCovenant prevention
            existing_fellowship = Fellowship.objects.filter(
                Q(from_user=initiator, to_user=counterpart) |
                Q(from_user=counterpart, to_user=initiator),
                status="Accepted"
            ).exists()

            if existing_fellowship:
                return Response(
                    {
                        "error": (
                            "You cannot delete this friend while a LITCovenant "
                            "relationship is active. Please remove the LITCovenant first."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Symmetric remove
            success = remove_symmetric_friendship(initiator, counterpart)

            if not success:
                logger.error(f"Symmetric friendship removal failed: {initiator.id} <-> {counterpart.id}")
                return Response(
                    {"error": "Failed to delete friendship."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            logger.info(f"Friendship deleted: {initiator.id} <-> {counterpart.id}")

            return Response(
                {"message": "Friendship successfully deleted."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"Unexpected error in delete_friendship: {e}")
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

