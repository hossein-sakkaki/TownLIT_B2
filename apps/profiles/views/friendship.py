# apps/profiles/views/friendship.py

import logging

from django.db import transaction
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
from apps.profiles.services.friendship_covenant_cleanup import (
    cleanup_hidden_confidant_fellowship_before_friendship_delete,
)
from apps.profiles.selectors.friends import get_friend_user_ids
from apps.profiles.selectors.common_suggestions import suggest_friends_for_requests_tab
from apps.profiles.selectors.friendship_suggestions import suggest_friends_for_friends_tab
from apps.profiles.selectors.people_suggestions import get_people_suggestions_queryset
from apps.core.boundaries.services.policy import BoundaryPolicy
from apps.core.boundaries.constants import BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE

CustomUser = get_user_model()
logger = logging.getLogger(__name__)




# FRIENDSHIP View --------------------------------------------------------------------------------------------
class FriendshipViewSet(viewsets.ModelViewSet):
    queryset = Friendship.objects.all()
    serializer_class = FriendshipSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ConfigurablePagination
    pagination_page_size = 20

    # ------------------------------------------------------------------
    # Visibility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _visible_user_q():
        return Q(is_active=True, is_deleted=False, is_suspended=False)

    @staticmethod
    def _visible_edge_q():
        return (
            Q(from_user__is_active=True) &
            Q(from_user__is_deleted=False) &
            Q(from_user__is_suspended=False) &
            Q(to_user__is_active=True) &
            Q(to_user__is_deleted=False) &
            Q(to_user__is_suspended=False)
        )

    @staticmethod
    def _filter_visible_user_list(users):
        return [
            user for user in users
            if getattr(user, "is_active", False)
            and not getattr(user, "is_deleted", False)
            and not getattr(user, "is_suspended", False)
        ]

    # ------------------------------------------------------------------
    # Mutual preview helpers
    # ------------------------------------------------------------------
    def _build_mutual_preview_context(
        self,
        viewer,
        candidates,
        preview_limit=5,
    ):
        candidate_ids = [candidate.id for candidate in candidates]

        if not candidate_ids:
            return {}, {}

        viewer_friend_edges = Friendship.objects.filter(
            Q(from_user=viewer) | Q(to_user=viewer),
            status="accepted",
        ).values_list(
            "from_user_id",
            "to_user_id",
        )

        viewer_friend_ids = set()

        for from_user_id, to_user_id in viewer_friend_edges:
            if from_user_id == viewer.id:
                viewer_friend_ids.add(to_user_id)
            else:
                viewer_friend_ids.add(from_user_id)

        if not viewer_friend_ids:
            return {}, {}

        candidate_friend_edges = Friendship.objects.filter(
            (
                Q(from_user_id__in=candidate_ids, to_user_id__in=viewer_friend_ids)
                | Q(to_user_id__in=candidate_ids, from_user_id__in=viewer_friend_ids)
            ),
            status="accepted",
        ).values_list(
            "from_user_id",
            "to_user_id",
        )

        mutual_ids_by_candidate = {
            candidate_id: []
            for candidate_id in candidate_ids
        }

        for from_user_id, to_user_id in candidate_friend_edges:
            if from_user_id in candidate_ids and to_user_id in viewer_friend_ids:
                mutual_ids_by_candidate[from_user_id].append(to_user_id)

            elif to_user_id in candidate_ids and from_user_id in viewer_friend_ids:
                mutual_ids_by_candidate[to_user_id].append(from_user_id)

        all_mutual_ids = {
            mutual_id
            for mutual_ids in mutual_ids_by_candidate.values()
            for mutual_id in mutual_ids
        }

        if not all_mutual_ids:
            return {}, {}

        mutual_users = (
            CustomUser.objects
            .filter(
                id__in=all_mutual_ids,
                is_active=True,
                is_deleted=False,
                is_suspended=False,
            )
            .select_related(
                "label",
                "member_profile",
            )
        )

        mutual_user_map = {
            mutual_user.id: mutual_user
            for mutual_user in mutual_users
        }

        mutual_count_map = {}
        mutual_preview_map = {}

        for candidate_id, mutual_ids in mutual_ids_by_candidate.items():
            unique_ids = list(dict.fromkeys(mutual_ids))

            mutual_count_map[candidate_id] = len(unique_ids)

            preview_users = [
                mutual_user_map[mutual_id]
                for mutual_id in unique_ids[:preview_limit]
                if mutual_id in mutual_user_map
            ]

            mutual_preview_map[candidate_id] = preview_users

        return mutual_count_map, mutual_preview_map

    # ------------------------------------------------------------------    
    # Actions
    # ------------------------------------------------------------------
    def get_queryset(self):
        user = self.request.user

        return (
            Friendship.objects
            .filter(Q(to_user=user) | Q(from_user=user))
            .filter(self._visible_edge_q())
            .order_by('-created_at')
        )
            
    def perform_create(self, serializer):
        try:
            if 'to_user_id' not in serializer.validated_data:
                logger.warning("Missing 'to_user_id' in request data.")
                raise serializers.ValidationError({"to_user_id": "This field is required."})

            to_user = serializer.validated_data['to_user_id']

            if (
                not to_user.is_active
                or getattr(to_user, "is_deleted", False)
                or getattr(to_user, "is_suspended", False)
            ):
                raise serializers.ValidationError(
                    "You cannot send a friend request to this account."
                )

            if to_user == self.request.user:
                logger.warning(f"User {self.request.user.id} tried to send a friend request to themselves.")
                raise serializers.ValidationError("You cannot send a friend request to yourself.")

            if not BoundaryPolicy.can_send_friend_request(
                sender=self.request.user,
                recipient=to_user,
            ):
                raise serializers.ValidationError({
                    "error": BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
                    "code": "interaction_unavailable",
                })
                
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
    
    # Create friendship with boundary cleanup --------------------------------------------
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)

        except serializers.ValidationError as exc:
            detail = getattr(exc, "detail", exc)

            if isinstance(detail, dict):
                if "error" in detail:
                    error = detail["error"]
                    if isinstance(error, list) and error:
                        error = str(error[0])
                    return Response(
                        {"error": str(error)},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                first_key = next(iter(detail), None)
                if first_key:
                    first_value = detail[first_key]
                    if isinstance(first_value, list) and first_value:
                        message = str(first_value[0])
                    else:
                        message = str(first_value)

                    return Response(
                        {
                            "error": message,
                            "field": first_key,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if isinstance(detail, list) and detail:
                return Response(
                    {"error": str(detail[0])},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"error": "Unable to process this friendship request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = self.get_success_headers(serializer.data)

        return Response(
            {
                "message": "Friend request sent successfully!",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
            headers=headers,
        )
    
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
            boundary_excluded_ids = BoundaryPolicy.user_ids_with_boundary_between(request.user)

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
                .exclude(id__in=boundary_excluded_ids)
                .filter(is_active=True, is_deleted=False, is_suspended=False)
                .distinct()
            )

            # ------------------------------------------------------------
            # Friendship + request state lookups
            # ------------------------------------------------------------
            friend_edges = (
                Friendship.objects
                .filter(
                    Q(from_user=request.user, status="accepted") |
                    Q(to_user=request.user, status="accepted")
                )
                .filter(is_active=True)
                .filter(self._visible_edge_q())
                .values("from_user", "to_user")
            )

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
                for r in Friendship.objects
                .filter(
                    to_user=request.user,
                    status="pending",
                    is_active=True,
                    from_user__is_active=True,
                    from_user__is_deleted=False,
                    from_user__is_suspended=False,
                )
                .values("from_user", "id")
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
                .filter(from_user=request.user, status='pending', is_active=True)
                .filter(
                    to_user__is_active=True,
                    to_user__is_deleted=False,
                    to_user__is_suspended=False,
                )
            )

            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error during sent_requests: {e}")
            return Response(
                {'error': 'Unable to fetch sent requests'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='received-requests', permission_classes=[IsAuthenticated])
    def received_requests(self, request):
        try:
            qs = (
                Friendship.objects
                .filter(to_user=request.user, status='pending', is_active=True)
                .filter(
                    from_user__is_active=True,
                    from_user__is_deleted=False,
                    from_user__is_suspended=False,
                )
            )

            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error during received_requests: {e}")
            return Response(
                {'error': 'Unable to fetch received requests'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=['get'],
        url_path='friends-list',
        permission_classes=[IsAuthenticated]
    )
    def friends_list(self, request):
        """
        Return optimized visible friends list.

        Suspended, deleted, or inactive accounts are intentionally hidden
        from the friends list without deleting the friendship relationship.
        """
        try:
            user = request.user

            edges = (
                Friendship.objects
                .filter(
                    Q(from_user=user) | Q(to_user=user),
                    status='accepted',
                    is_active=True,
                )
                .filter(self._visible_edge_q())
                .values('id', 'from_user_id', 'to_user_id')
            )

            counterpart_ids = set()
            friendship_ids_map = {}
            uid = user.id

            for edge in edges:
                fid = edge['from_user_id']
                tid = edge['to_user_id']

                counterpart = tid if fid == uid else fid
                counterpart_ids.add(counterpart)
                friendship_ids_map[counterpart] = edge['id']

            boundary_excluded_ids = set(
                BoundaryPolicy.user_ids_with_boundary_between(user)
            )

            counterpart_ids = counterpart_ids.difference(boundary_excluded_ids)
            friendship_ids_map = {
                user_id: friendship_id
                for user_id, friendship_id in friendship_ids_map.items()
                if user_id not in boundary_excluded_ids
            }

            friends_base_qs = (
                CustomUser.objects
                .filter(
                    id__in=counterpart_ids,
                    is_active=True,
                    is_deleted=False,
                    is_suspended=False,
                )
                .select_related(
                    "label",
                    "member_profile"
                )
            )

            visible_count = friends_base_qs.count()

            first_char = Substr('username', 1, 1)

            group = Case(
                When(username__startswith='_', then=Value(2)),
                When(username__regex=r'^[A-Za-z]', then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )

            friends_qs = (
                friends_base_qs
                .annotate(
                    sort_group=group,
                    username_lower=Lower('username'),
                    first_char_annot=first_char,
                )
                .order_by('sort_group', 'username_lower')
            )

            limit = request.query_params.get('limit')
            if limit:
                try:
                    lim = max(0, int(limit))
                    if lim:
                        friends_qs = friends_qs[:lim]
                except ValueError:
                    pass

            ser = SimpleCustomUserSerializer(
                friends_qs,
                many=True,
                context={
                    "request": request,
                    "friend_ids": set(counterpart_ids),
                    "friendship_ids": friendship_ids_map,
                    "sent_request_map": {},
                    "received_request_map": {},
                    "fellowship_ids": {},
                }
            )

            return Response(
                {
                    "results": ser.data,
                    "meta": {
                        "count": visible_count
                    }
                },
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
        methods=["get"],
        url_path="friends-suggestions",
        permission_classes=[IsAuthenticated],
    )
    def friends_suggestions(self, request):
        user = request.user

        try:
            limit = int(request.query_params.get("limit", 5))
        except (TypeError, ValueError):
            limit = 5

        limit = max(1, min(limit, 20))

        excluded_ids = BoundaryPolicy.excluded_user_ids_for_suggestions(user)

        suggestions = suggest_friends_for_friends_tab(
            user=user,
            limit=limit,
            extra_exclude_ids=excluded_ids,
        )

        suggestions = self._filter_visible_user_list(list(suggestions))

        mutual_count_map, mutual_preview_map = self._build_mutual_preview_context(
            viewer=user,
            candidates=suggestions,
            preview_limit=5,
        )

        serializer = SimpleCustomUserSerializer(
            suggestions,
            many=True,
            context={
                "request": request,
                "mutual_count_map": mutual_count_map,
                "mutual_preview_map": mutual_preview_map,
            },
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------------------------------------------
    @action(
        detail=False,
        methods=["get"],
        url_path="requests-suggestions",
        permission_classes=[IsAuthenticated],
    )
    def requests_suggestions(self, request):
        user = request.user

        try:
            limit = int(request.query_params.get("limit", 5))
        except (TypeError, ValueError):
            limit = 5

        limit = max(1, min(limit, 20))

        excluded_ids = BoundaryPolicy.excluded_user_ids_for_suggestions(user)

        suggestions = suggest_friends_for_requests_tab(
            user=user,
            limit=limit,
            extra_exclude_ids=excluded_ids,
        )

        suggestions = self._filter_visible_user_list(list(suggestions))

        serializer = SimpleCustomUserSerializer(
            suggestions,
            many=True,
            context={
                "request": request,

                # Important:
                # Requests suggestions should not provide mutual friends.
                # Friend-of-friend suggestions belong to friends-suggestions.
                "mutual_count_map": {},
                "mutual_preview_map": {},
            },
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
        Discover tab / Square → Discover tab (paged).

        Returns:
        - ranked users
        - mutual_friends_count
        - mutual_friends preview
        - shared signals such as same_country, same_language, same_branch, same_family
        """
        try:
            viewer = request.user

            qs = get_people_suggestions_queryset(viewer)

            qs = qs.filter(
                is_active=True,
                is_deleted=False,
                is_suspended=False,
            )

            excluded_ids = BoundaryPolicy.excluded_user_ids_for_suggestions(viewer)

            if excluded_ids:
                qs = qs.exclude(id__in=excluded_ids)

            page = self.paginate_queryset(qs)

            if page is not None:
                page_items = list(page)
            else:
                page_items = list(qs[:20])

            candidate_ids = [user.id for user in page_items]
            candidate_ids_set = set(candidate_ids)

            viewer_friend_ids = set(get_friend_user_ids(viewer))
            mutual_preview_map = {
                candidate_id: []
                for candidate_id in candidate_ids
            }

            if viewer_friend_ids and candidate_ids_set:
                edges = (
                    Friendship.objects
                    .filter(
                        status="accepted",
                        is_active=True,
                    )
                    .filter(self._visible_edge_q())
                    .filter(
                        Q(
                            from_user_id__in=viewer_friend_ids,
                            to_user_id__in=candidate_ids_set,
                        )
                        | Q(
                            to_user_id__in=viewer_friend_ids,
                            from_user_id__in=candidate_ids_set,
                        )
                    )
                    .values(
                        "from_user_id",
                        "to_user_id",
                    )
                )

                mutual_ids_map = {
                    candidate_id: set()
                    for candidate_id in candidate_ids
                }

                for edge in edges:
                    from_user_id = edge["from_user_id"]
                    to_user_id = edge["to_user_id"]

                    if from_user_id in candidate_ids_set and to_user_id in viewer_friend_ids:
                        mutual_ids_map[from_user_id].add(to_user_id)

                    elif to_user_id in candidate_ids_set and from_user_id in viewer_friend_ids:
                        mutual_ids_map[to_user_id].add(from_user_id)

                preview_limit = 5

                all_mutual_ids = set()

                for candidate_id, mutual_ids in mutual_ids_map.items():
                    preview_ids = list(mutual_ids)[:preview_limit]
                    mutual_ids_map[candidate_id] = preview_ids
                    all_mutual_ids.update(preview_ids)

                if all_mutual_ids:
                    mutual_users = (
                        CustomUser.objects
                        .filter(
                            id__in=all_mutual_ids,
                            is_active=True,
                            is_deleted=False,
                            is_suspended=False,
                        )
                        .select_related(
                            "label",
                            "member_profile",
                        )
                    )

                    mutual_by_id = {
                        mutual_user.id: mutual_user
                        for mutual_user in mutual_users
                    }

                    for candidate_id, mutual_ids in mutual_ids_map.items():
                        mutual_objects = [
                            mutual_by_id[mutual_id]
                            for mutual_id in mutual_ids
                            if mutual_id in mutual_by_id
                        ]

                        mutual_preview_map[candidate_id] = UserMiniSerializer(
                            mutual_objects,
                            many=True,
                            context={
                                "request": request,
                            },
                        ).data

            serializer = PeopleSuggestionSerializer(
                page_items,
                many=True,
                context={
                    "request": request,
                    "mutual_preview_map": mutual_preview_map,
                },
            )

            if page is not None:
                return self.get_paginated_response(serializer.data)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.exception("Error in people_suggestions")
            return Response(
                {
                    "error": "Unable to retrieve people suggestions",
                },
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

            if not BoundaryPolicy.can_send_friend_request(
                sender=friendship.from_user,
                recipient=friendship.to_user,
            ):
                return Response(
                    {
                        "error": BOUNDARY_GENERIC_UNAVAILABLE_MESSAGE,
                        "code": "interaction_unavailable",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
                
            # Cannot accept request from deleted account
            if (
                not friendship.from_user.is_active
                or getattr(friendship.from_user, "is_deleted", False)
                or getattr(friendship.from_user, "is_suspended", False)
            ):
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
        Delete an accepted friendship.

        Rules:
        - Normal active LITCovenant relationships still block friendship deletion.
        - Hidden Confidant/Entrusted relationships caused by inactive LITShield
          are auto-cleaned first, then friendship deletion continues.
        - This solves the deadlock where the user cannot see/remove the hidden
          Confidant in LITCovenant but also cannot delete the friend.
        """
        try:
            initiator = request.user

            friendship_id = (
                request.data.get("friendship_id") or
                request.data.get("friendshipId")
            )

            if not friendship_id:
                logger.warning(
                    "User %s attempted deletion with no friendship_id.",
                    initiator.id,
                )
                return Response(
                    {"error": "friendship_id is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                friendship = (
                    Friendship.objects
                    .select_for_update()
                    .select_related(
                        "from_user__label",
                        "from_user__member_profile",
                        "to_user__label",
                        "to_user__member_profile",
                    )
                    .filter(
                        id=friendship_id,
                        status="accepted",
                        is_active=True,
                    )
                    .first()
                )

                if not friendship:
                    logger.warning("Friendship not found for delete: id=%s", friendship_id)
                    return Response(
                        {"error": "Friendship not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if (
                    friendship.from_user_id != initiator.id and
                    friendship.to_user_id != initiator.id
                ):
                    logger.warning(
                        "User %s tried to delete friendship not belonging to them.",
                        initiator.id,
                    )
                    return Response(
                        {"error": "You do not have permission to delete this friendship."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                counterpart = (
                    friendship.to_user
                    if friendship.from_user_id == initiator.id
                    else friendship.from_user
                )

                cleanup_result = cleanup_hidden_confidant_fellowship_before_friendship_delete(
                    initiator=initiator,
                    counterpart=counterpart,
                )

                if not cleanup_result.allowed:
                    return Response(
                        {
                            "error": cleanup_result.error or (
                                "You cannot delete this friend while a LITCovenant "
                                "relationship is active. Please remove the LITCovenant first."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                success = remove_symmetric_friendship(initiator, counterpart)

                if not success:
                    logger.error(
                        "Symmetric friendship removal failed: %s <-> %s",
                        initiator.id,
                        counterpart.id,
                    )
                    raise RuntimeError("Failed to delete friendship.")

            logger.info(
                "Friendship deleted: %s <-> %s",
                initiator.id,
                counterpart.id,
            )

            message = "Friendship successfully deleted."

            if cleanup_result.cleaned:
                message = (
                    "Friendship successfully deleted. A hidden Confidant "
                    "LITCovenant relationship was also removed."
                )

            return Response(
                {
                    "message": message,
                    "hidden_covenant_cleanup": cleanup_result.cleaned,
                    "hidden_covenant_cleanup_count": cleanup_result.cleaned_count,
                },
                status=status.HTTP_200_OK,
            )

        except RuntimeError as e:
            logger.exception("Friendship deletion failed: %s", e)
            return Response(
                {"error": "Failed to delete friendship."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            logger.exception("Unexpected error in delete_friendship: %s", e)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )