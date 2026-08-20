# apps/communication/services/recipients.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.communication.constants import (
    AudienceKind,
    AudienceMatchType,
    AudienceRuleField,
    AudienceRuleOperator,
)
from apps.moderation.models import AccessRequest

from .exceptions import AudienceConfigurationError
from .legacy_targets import resolve_preset_objects


CustomUser = get_user_model()


@dataclass(frozen=True)
class EmailRecipient:
    email: str
    first_name: str
    username: str
    source: str

    user: Any = None
    external_contact: Any = None
    legacy_access_request: Any = None

    @property
    def normalized_email(self):
        return self.email.strip().lower()

    @property
    def user_id(self):
        return getattr(self.user, "id", None)

    @property
    def external_contact_id(self):
        return getattr(self.external_contact, "id", None)


class AudienceResolver:
    """
    Resolve campaign targeting into unique email recipients.
    """

    def resolve_campaign(self, campaign):
        recipients = {}

        if campaign.recipients.exists():
            users = campaign.recipients.filter(
                is_active=True
            )

            self._add_users(
                recipients,
                users,
                source="manual",
            )

            return list(recipients.values())

        if campaign.audience_id:
            self._resolve_saved_audience(
                campaign.audience,
                recipients,
            )

            return list(recipients.values())

        objects = resolve_preset_objects(
            campaign.target_group
        )

        self._add_objects(
            recipients,
            objects,
            source="preset",
        )

        return list(recipients.values())

    def _resolve_saved_audience(
        self,
        audience,
        recipients,
    ):
        if audience.preset_key:
            objects = resolve_preset_objects(
                audience.preset_key
            )

            self._add_objects(
                recipients,
                objects,
                source="audience_preset",
            )

        elif audience.kind in {
            AudienceKind.DYNAMIC,
            AudienceKind.HYBRID,
        }:
            users = self._resolve_dynamic_users(
                audience
            )

            self._add_users(
                recipients,
                users,
                source="audience_rules",
            )

        if audience.kind in {
            AudienceKind.MANUAL,
            AudienceKind.HYBRID,
        }:
            self._add_users(
                recipients,
                audience.users.filter(is_active=True),
                source="audience_manual",
            )

        self._add_external_contacts(
            recipients,
            audience.external_contacts.filter(
                is_active=True
            ),
        )

    def _resolve_dynamic_users(self, audience):
        queryset = CustomUser.objects.all()

        rules = audience.rules.filter(
            is_active=True
        ).order_by(
            "sort_order",
            "id",
        )

        if not rules.exists():
            return queryset.none()

        if audience.match_type == AudienceMatchType.ALL:
            for rule in rules:
                queryset = queryset.filter(
                    self._rule_q(rule)
                )

            return queryset.distinct()

        query = Q()

        for rule in rules:
            query |= self._rule_q(rule)

        return queryset.filter(query).distinct()

    def _rule_q(self, rule):
        field_name = self._query_field(
            rule.field
        )

        operator = rule.operator
        value = rule.value

        if operator == AudienceRuleOperator.TRUE:
            query = Q(**{field_name: True})

        elif operator == AudienceRuleOperator.FALSE:
            query = Q(**{field_name: False})

        elif operator == AudienceRuleOperator.EQUALS:
            query = Q(**{field_name: value})

        elif operator == AudienceRuleOperator.NOT_EQUALS:
            query = ~Q(**{field_name: value})

        elif operator == AudienceRuleOperator.IN:
            values = value if isinstance(value, list) else [value]
            query = Q(**{f"{field_name}__in": values})

        elif operator == AudienceRuleOperator.NOT_IN:
            values = value if isinstance(value, list) else [value]
            query = ~Q(**{f"{field_name}__in": values})

        elif operator == AudienceRuleOperator.CONTAINS:
            query = Q(
                **{f"{field_name}__icontains": value}
            )

        elif operator == AudienceRuleOperator.BEFORE:
            query = Q(
                **{f"{field_name}__lt": value}
            )

        elif operator == AudienceRuleOperator.AFTER:
            query = Q(
                **{f"{field_name}__gt": value}
            )

        else:
            raise AudienceConfigurationError(
                f"Unsupported audience operator: {operator}"
            )

        if rule.negate:
            query = ~query

        return query

    def _query_field(self, field):
        mappings = {
            AudienceRuleField.ACTIVE: "is_active",
            AudienceRuleField.MEMBER: "is_member",
            AudienceRuleField.ADMIN: "is_admin",
            AudienceRuleField.SUSPENDED: "is_suspended",
            AudienceRuleField.LABEL: "label__name",
            AudienceRuleField.REGISTER_DATE: "register_date",
        }

        try:
            return mappings[field]
        except KeyError as error:
            raise AudienceConfigurationError(
                "This audience field is not mapped yet: "
                f"{field}"
            ) from error

    def _add_objects(
        self,
        recipients,
        objects,
        *,
        source,
    ):
        for obj in objects:
            if isinstance(obj, CustomUser):
                self._add_user(
                    recipients,
                    obj,
                    source=source,
                )
                continue

            if isinstance(obj, AccessRequest):
                self._add_access_request(
                    recipients,
                    obj,
                    source=source,
                )

    def _add_users(
        self,
        recipients,
        users,
        *,
        source,
    ):
        for user in users:
            self._add_user(
                recipients,
                user,
                source=source,
            )

    def _add_user(
        self,
        recipients,
        user,
        *,
        source,
    ):
        email = (user.email or "").strip()

        if not email:
            return

        key = email.lower()

        recipients[key] = EmailRecipient(
            email=email,
            first_name=(
                getattr(user, "name", "")
                or email.split("@")[0].title()
            ),
            username=getattr(user, "username", "") or "",
            source=source,
            user=user,
        )

    def _add_access_request(
        self,
        recipients,
        access_request,
        *,
        source,
    ):
        email = (access_request.email or "").strip()

        if not email:
            return

        key = email.lower()

        if key in recipients:
            return

        recipients[key] = EmailRecipient(
            email=email,
            first_name=(
                getattr(access_request, "first_name", "")
                or "Friend"
            ),
            username="guest",
            source=source,
            legacy_access_request=access_request,
        )

    def _add_external_contacts(
        self,
        recipients,
        contacts,
    ):
        for contact in contacts:
            email = (contact.email or "").strip()

            if not email:
                continue

            key = email.lower()

            # Registered users take precedence.
            if key in recipients:
                continue

            recipients[key] = EmailRecipient(
                email=email,
                first_name=contact.name or "Friend",
                username=contact.name or "guest",
                source="external_contact",
                external_contact=contact,
            )