# apps/profiles/tests/test_people_suggestions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.profiles.selectors.people_suggestions import (
    get_people_suggestions_queryset,
)
from apps.profiles.views.friendship import FriendshipViewSet


class PeopleSuggestionsContractTests(SimpleTestCase):
    @staticmethod
    def _viewer(
        *,
        user_id=10,
        is_authenticated=True,
        is_active=True,
        is_deleted=False,
    ):
        return SimpleNamespace(
            id=user_id,
            is_authenticated=is_authenticated,
            is_active=is_active,
            is_deleted=is_deleted,
            country=None,
            primary_language=None,
            member_profile=None,
        )

    @staticmethod
    def _chain_queryset():
        queryset = MagicMock()

        queryset.filter.return_value = queryset
        queryset.exclude.return_value = queryset
        queryset.select_related.return_value = queryset
        queryset.annotate.return_value = queryset
        queryset.order_by.return_value = queryset

        return queryset

    @patch(
        "apps.profiles.selectors.people_suggestions.get_friend_user_ids",
        return_value=[20, 21],
    )
    @patch(
        "apps.profiles.selectors.people_suggestions.Friendship.objects",
    )
    @patch(
        "apps.profiles.selectors.people_suggestions.CustomUser.objects",
    )
    def test_people_suggestions_exclude_self_friends_and_pending_requests(
        self,
        user_objects,
        friendship_objects,
        get_friend_user_ids,
    ):
        viewer = self._viewer(
            user_id=10,
        )

        sent_requests_queryset = MagicMock()
        sent_requests_queryset.values_list.return_value = [
            30,
        ]

        received_requests_queryset = MagicMock()
        received_requests_queryset.values_list.return_value = [
            31,
        ]

        mutual_queryset = MagicMock()
        mutual_queryset.filter.return_value = mutual_queryset
        mutual_queryset.annotate.return_value = mutual_queryset
        mutual_queryset.values.return_value = mutual_queryset
        mutual_queryset.__getitem__.return_value = mutual_queryset

        def friendship_filter(*args, **kwargs):
            if (
                kwargs.get("from_user") is viewer
                and kwargs.get("status") == "pending"
            ):
                return sent_requests_queryset

            if (
                kwargs.get("to_user") is viewer
                and kwargs.get("status") == "pending"
            ):
                return received_requests_queryset

            return mutual_queryset

        friendship_objects.filter.side_effect = friendship_filter

        candidates_queryset = self._chain_queryset()
        user_objects.filter.return_value = candidates_queryset

        result = get_people_suggestions_queryset(
            viewer,
        )

        self.assertIs(
            result,
            candidates_queryset,
        )

        get_friend_user_ids.assert_called_once_with(
            viewer,
        )

        candidates_queryset.exclude.assert_any_call(
            id__in={
                10,
                20,
                21,
                30,
                31,
            },
        )

    @patch(
        "apps.profiles.selectors.people_suggestions.get_friend_user_ids",
        return_value=[],
    )
    @patch(
        "apps.profiles.selectors.people_suggestions.Friendship.objects",
    )
    @patch(
        "apps.profiles.selectors.people_suggestions.CustomUser.objects",
    )
    def test_people_suggestions_require_visible_active_accounts(
        self,
        user_objects,
        friendship_objects,
        _get_friend_user_ids,
    ):
        viewer = self._viewer()

        empty_requests = MagicMock()
        empty_requests.values_list.return_value = []

        friendship_objects.filter.side_effect = [
            empty_requests,
            empty_requests,
        ]

        candidates_queryset = self._chain_queryset()
        user_objects.filter.return_value = candidates_queryset

        get_people_suggestions_queryset(
            viewer,
        )

        user_objects.filter.assert_called_once_with(
            is_active=True,
            is_deleted=False,
            is_suspended=False,
        )

    @patch(
        "apps.profiles.selectors.people_suggestions.get_friend_user_ids",
        return_value=[],
    )
    @patch(
        "apps.profiles.selectors.people_suggestions.Friendship.objects",
    )
    @patch(
        "apps.profiles.selectors.people_suggestions.CustomUser.objects",
    )
    def test_people_suggestions_use_ranked_deterministic_primary_order(
        self,
        user_objects,
        friendship_objects,
        _get_friend_user_ids,
    ):
        viewer = self._viewer()

        empty_requests = MagicMock()
        empty_requests.values_list.return_value = []

        friendship_objects.filter.side_effect = [
            empty_requests,
            empty_requests,
        ]

        candidates_queryset = self._chain_queryset()
        user_objects.filter.return_value = candidates_queryset

        get_people_suggestions_queryset(
            viewer,
        )

        candidates_queryset.order_by.assert_called_once_with(
            "-score",
            "-register_date",
            "id",
        )

    @patch(
        "apps.profiles.selectors.people_suggestions.CustomUser.objects",
    )
    def test_unauthenticated_viewer_receives_empty_queryset(
        self,
        user_objects,
    ):
        empty_queryset = object()
        user_objects.none.return_value = empty_queryset

        result = get_people_suggestions_queryset(
            self._viewer(
                is_authenticated=False,
            )
        )

        self.assertIs(
            result,
            empty_queryset,
        )

    @patch(
        "apps.profiles.selectors.people_suggestions.CustomUser.objects",
    )
    def test_inactive_viewer_receives_empty_queryset(
        self,
        user_objects,
    ):
        empty_queryset = object()
        user_objects.none.return_value = empty_queryset

        result = get_people_suggestions_queryset(
            self._viewer(
                is_active=False,
            )
        )

        self.assertIs(
            result,
            empty_queryset,
        )


class PeopleSearchContractTests(SimpleTestCase):
    @staticmethod
    def _queryset_chain():
        queryset = MagicMock()

        queryset.select_related.return_value = queryset
        queryset.only.return_value = queryset
        queryset.filter.return_value = queryset
        queryset.exclude.return_value = queryset
        queryset.annotate.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.distinct.return_value = queryset

        return queryset

    @patch(
        "apps.profiles.views.friendship.SimpleCustomUserSerializer",
    )
    @patch(
        "apps.profiles.views.friendship.BoundaryPolicy.user_ids_with_boundary_between",
        return_value={99},
    )
    @patch(
        "apps.profiles.views.friendship.Friendship.objects",
    )
    @patch(
        "apps.profiles.views.friendship.CustomUser.objects",
    )
    def test_people_search_is_broad_user_search_not_friend_only_search(
        self,
        user_objects,
        friendship_objects,
        boundary_user_ids,
        serializer_class,
    ):
        viewer = SimpleNamespace(
            id=10,
        )

        request = SimpleNamespace(
            user=viewer,
            query_params={
                "q": "target",
            },
        )

        users_queryset = self._queryset_chain()
        user_objects.select_related.return_value = users_queryset

        friend_edges_queryset = MagicMock()
        friend_edges_queryset.filter.return_value = friend_edges_queryset
        friend_edges_queryset.values.return_value = [
            {
                "from_user": 10,
                "to_user": 20,
            },
        ]

        sent_requests_queryset = MagicMock()
        sent_requests_queryset.values.return_value = [
            {
                "to_user": 30,
                "id": 300,
            },
        ]

        received_requests_queryset = MagicMock()
        received_requests_queryset.filter.return_value = received_requests_queryset
        received_requests_queryset.values.return_value = [
            {
                "from_user": 40,
                "id": 400,
            },
        ]

        friendship_objects.filter.side_effect = [
            friend_edges_queryset,
            sent_requests_queryset,
            received_requests_queryset,
        ]

        page = [
            SimpleNamespace(id=20),
            SimpleNamespace(id=50),
        ]

        serializer = MagicMock()
        serializer.data = [
            {
                "id": 20,
            },
            {
                "id": 50,
            },
        ]

        serializer_class.return_value = serializer

        view = FriendshipViewSet()

        view.paginate_queryset = MagicMock(
            return_value=page,
        )

        expected_response = object()

        view.get_paginated_response = MagicMock(
            return_value=expected_response,
        )

        result = view.search_users(
            request,
        )

        self.assertIs(
            result,
            expected_response,
        )

        boundary_user_ids.assert_called_once_with(
            viewer,
        )

        users_queryset.exclude.assert_any_call(
            id=viewer.id,
        )

        users_queryset.exclude.assert_any_call(
            id__in={99},
        )

        users_queryset.filter.assert_called_with(
            is_active=True,
            is_deleted=False,
            is_suspended=False,
        )

        view.paginate_queryset.assert_called_once_with(
            users_queryset,
        )

        serializer_class.assert_called_once()

        serializer_context = serializer_class.call_args.kwargs[
            "context"
        ]

        self.assertEqual(
            serializer_context["friend_ids"],
            {
                20,
            },
        )

        self.assertEqual(
            serializer_context["sent_request_map"],
            {
                30: 300,
            },
        )

        self.assertEqual(
            serializer_context["received_request_map"],
            {
                40: 400,
            },
        )
        

