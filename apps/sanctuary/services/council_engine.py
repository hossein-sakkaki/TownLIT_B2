# apps/sanctuary/services/council_engine.py

from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional, Tuple, Set

from django.db.models import Q
from django.contrib.auth import get_user_model

from apps.sanctuary.models import SanctuaryReview
from apps.sanctuary.constants.states import PENDING, UNDER_REVIEW, NO_OPINION

if TYPE_CHECKING:
    from apps.accounts.models import CustomUser
    from apps.sanctuary.models import SanctuaryRequest

UserModel = get_user_model()


class CouncilSelectionEngine:
    """
    Picks 12 council members based on:
    - Not currently busy in active council sanctuaries
    - Language match with target owner
    - 8 denomination matches + 4 language-only matches
    - Random selection
    """

    def __init__(self, *, request_obj: "SanctuaryRequest"):
        self.req = request_obj

    # -----------------------------
    # Resolve target owner user
    # -----------------------------
    def resolve_target_owner(self) -> Optional["CustomUser"]:
        target = getattr(self.req, "content_object", None)
        if not target:
            return None

        if isinstance(target, UserModel):
            return target  # type: ignore[return-value]

        for attr in ("user", "owner", "author", "created_by", "name", "org_owner_user", "member_user"):
            u = getattr(target, attr, None)
            if u is not None and hasattr(u, "id"):
                return u  # type: ignore[return-value]

        return None

    # -----------------------------
    # Languages of the target owner
    # -----------------------------
    def resolve_target_languages(self, owner: "CustomUser") -> Set[str]:
        """
        Robust: supports either (primary_language, secondary_language)
        or a single (language) field depending on your CustomUser model.
        """
        langs: Set[str] = set()

        p = getattr(owner, "primary_language", None)
        s = getattr(owner, "secondary_language", None)
        if p:
            langs.add(str(p).strip().lower())
        if s:
            langs.add(str(s).strip().lower())

        # Fallback single language field if your model uses it
        if not langs:
            l = getattr(owner, "language", None)
            if l:
                langs.add(str(l).strip().lower())

        return langs

    # -----------------------------
    # Denomination of the target owner (Member profile)
    # -----------------------------
    def resolve_target_denom(self, owner: "CustomUser") -> Tuple[Optional[str], Optional[str]]:
        mp = getattr(owner, "member_profile", None)
        if not mp:
            return None, None

        branch = getattr(mp, "denomination_branch", None)
        family = getattr(mp, "denomination_family", None)
        return branch, family

    # -----------------------------
    # Users currently busy in active council sanctuaries
    # -----------------------------
    def busy_user_ids(self) -> Set[int]:
        """
        Busy = has an ACTIVE council slot that is still NO_OPINION.
        (once voted, user becomes free immediately)
        """
        qs = SanctuaryReview.objects.filter(
            sanctuary_request__resolution_mode="council",
            sanctuary_request__status__in=[PENDING, UNDER_REVIEW],
            review_status=NO_OPINION,
        )

        # Optional field support
        if hasattr(SanctuaryReview, "is_active"):
            qs = qs.filter(is_active=True)

        return set(qs.values_list("reviewer_id", flat=True))

    # -----------------------------
    # Language filter (match any of target langs)
    # -----------------------------
    def filter_by_languages(self, qs, target_langs: Set[str]):
        """
        Matches any of target langs against user language fields.
        Adjust field names here if your CustomUser differs.
        """
        if not target_langs:
            return qs

        # Prefer primary/secondary if exist; fallback to language
        cond = Q()

        # These fields may or may not exist in your CustomUser;
        # Q() on non-existing fields will raise FieldError.
        # So we detect existence safely.
        user_fields = {f.name for f in UserModel._meta.get_fields()}

        if "primary_language" in user_fields:
            cond |= Q(primary_language__in=list(target_langs))
        if "secondary_language" in user_fields:
            cond |= Q(secondary_language__in=list(target_langs))
        if "language" in user_fields:
            cond |= Q(language__in=list(target_langs))

        if not cond:
            return qs  # no known language fields, don't filter

        return qs.filter(cond)

    # -----------------------------
    # Base eligible pool
    # -----------------------------
    def base_queryset(self, target_langs: Optional[Set[str]] = None):
        """
        Base eligible pool for council selection:
          - user.is_active
          - user.is_verified_identity
          - member_profile.is_townlit_verified
          - sanctuary_participation.is_participant == True
          - sanctuary_participation.is_eligible == True
          - NOT busy
          - NOT requester
          - NOT target owner (recommended)
        """
        qs = (
            UserModel.objects.filter(
                is_active=True,
                is_verified_identity=True,
                member_profile__is_townlit_verified=True,
                sanctuary_participation__is_participant=True,
                sanctuary_participation__is_eligible=True,
            )
            .select_related("member_profile", "sanctuary_participation")
        )

        # Exclude busy users
        busy_ids = self.busy_user_ids()
        if busy_ids:
            qs = qs.exclude(id__in=busy_ids)

        # Exclude requester
        qs = qs.exclude(id=self.req.requester_id)

        # Exclude target owner (recommended safety)
        owner = self.resolve_target_owner()
        if owner:
            qs = qs.exclude(id=owner.id)

        # Optional: language filtering
        if target_langs:
            qs = self.filter_by_languages(qs, target_langs)

        return qs

    # -----------------------------
    # Denomination match queryset
    # -----------------------------
    def denom_match_queryset(self, qs, branch: Optional[str], family: Optional[str]):
        cond = Q()
        if branch:
            cond |= Q(member_profile__denomination_branch=branch)
        if family:
            cond |= Q(member_profile__denomination_family=family)

        return qs.filter(cond) if cond else qs.none()

    # -----------------------------
    # Pick random IDs safely
    # -----------------------------
    def pick_random_ids(self, ids: List[int], k: int) -> List[int]:
        if len(ids) <= k:
            random.shuffle(ids)
            return ids
        return random.sample(ids, k)

    # -----------------------------
    # Main select
    # -----------------------------
    def select_council(self, *, total: int = 12, denom_majority: int = 8) -> Optional[List["CustomUser"]]:
        owner = self.resolve_target_owner()
        if not owner:
            return None

        target_langs = self.resolve_target_languages(owner)
        branch, family = self.resolve_target_denom(owner)

        base = self.base_queryset(target_langs)

        # 1) denom-majority bucket
        denom_qs = self.denom_match_queryset(base, branch, family)
        denom_ids = list(denom_qs.values_list("id", flat=True))
        chosen_denom_ids = self.pick_random_ids(denom_ids, denom_majority)

        # 2) remaining bucket (language match already ensured)
        remaining_needed = total - len(chosen_denom_ids)
        remaining_qs = base.exclude(id__in=chosen_denom_ids)
        remaining_ids = list(remaining_qs.values_list("id", flat=True))
        chosen_rest_ids = self.pick_random_ids(remaining_ids, remaining_needed)

        final_ids = chosen_denom_ids + chosen_rest_ids

        # Hard rule: need 12 total
        if len(final_ids) < total:
            return None

        # Hard rule: need 8 denom matches
        if len(chosen_denom_ids) < denom_majority:
            return None

        users = list(UserModel.objects.filter(id__in=final_ids))
        users_map = {u.id: u for u in users}
        return [users_map[i] for i in final_ids if i in users_map]  # preserve order
