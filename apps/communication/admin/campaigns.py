# apps/communication/admin/campaigns.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.

import json
from copy import deepcopy

from django.contrib import admin, messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (
    Count,
    F,
    Max,
    Q,
)
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils.html import format_html, strip_tags

from apps.communication.constants import (
    CampaignStatus,
    EmailBlockType,
)
from apps.communication.forms import (
    CampaignWorkspaceForm,
    EmailCampaignAdminForm,
    EmailCampaignBlockAdminForm,
)
from apps.communication.models import (
    EmailCampaign,
    EmailCampaignBlock,
)
from apps.communication.services import (
    CampaignPreflightService,
    CampaignSchedulingService,
    send_test_email_for_campaign,
)


class EmailCampaignBlockInline(admin.StackedInline):
    model = EmailCampaignBlock
    form = EmailCampaignBlockAdminForm
    extra = 0
    show_change_link = False

    fields = (
        "block_type",
        "name",
        "sort_order",
        "is_enabled",
        "headline",
        "content",
        "secondary_content",
        "image_url",
        "image_alt",
        "action_label",
        "action_url",
        "attribution",
        "alignment",
        "spacer_height",
        "social_links",
        "custom_html",
    )

    def has_add_permission(self, request, obj=None):
        if obj and not obj.can_edit_content:
            return False

        return super().has_add_permission(
            request,
            obj,
        )

    def has_delete_permission(self, request, obj=None):
        if obj and not obj.can_edit_content:
            return False

        return super().has_delete_permission(
            request,
            obj,
        )


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    form = EmailCampaignAdminForm
    inlines = [EmailCampaignBlockInline]

    list_display = (
        "title",
        "status_badge",
        "campaign_type",
        "audience_summary",
        "scheduled_time",
        "delivery_summary",
        "engagement_summary",
        "preview_link",
        "created_at",
    )
    list_filter = (
        "status",
        "campaign_type",
        "target_group",
        "topic",
        "created_by",
        "tag",
    )
    search_fields = (
        "title",
        "subject",
        "description",
        "tag",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    filter_horizontal = ("recipients",)

    autocomplete_fields = (
        "template",
        "theme",
        "audience",
        "topic",
    )

    actions = (
        "mark_ready",
        "queue_campaigns_now",
        "schedule_campaigns",
        "unschedule_campaigns",
        "send_test_email",
        "clone_campaigns",
    )

    readonly_fields = (
        "status",
        "created_at",
        "updated_at",
        "started_at",
        "queued_at",
        "last_dispatch_at",
        "dispatch_attempt_count",
        "celery_task_id",
        "sent_at",
        "completed_at",
        "failed_at",
        "canceled_at",
        "recipient_count",
        "sent_count",
        "delivered_count",
        "failed_count",
        "bounced_count",
        "complaint_count",
        "open_count",
        "unique_open_count",
        "click_count",
        "unique_click_count",
        "unsubscribe_count",
        "last_error",

        "last_test_sent_at",
        "last_test_email",
        "last_test_content_version",
    )

    fieldsets = (
        (
            "1. Campaign",
            {
                "fields": (
                    "title",
                    "description",
                    "campaign_type",
                    "tag",
                ),
            },
        ),
        (
            "2. Message",
            {
                "fields": (
                    "subject",
                    "preheader_text",
                    "template",
                    "theme",
                    "custom_html",
                ),
            },
        ),
        (
            "3. Audience",
            {
                "fields": (
                    "audience",
                    "recipients",
                    "target_group",
                    "topic",
                    "ignore_unsubscribe",
                ),
            },
        ),
        (
            "4. Test & Schedule",
            {
                "fields": (
                    "test_email",
                    "scheduled_time",
                    "schedule_timezone",
                ),
            },
        ),
        (
            "Sender & Tracking",
            {
                "fields": (
                    "from_name",
                    "reply_to_email",
                    "track_opens",
                    "track_clicks",
                    "utm_source",
                    "utm_medium",
                    "utm_campaign",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Workflow",
            {
                "fields": (
                    "status",
                    "review_requested_at",
                    "approved_by",
                    "approved_at",
                    "queued_at",
                    "last_dispatch_at",
                    "dispatch_attempt_count",
                    "celery_task_id",
                    "started_at",
                    "sent_at",
                    "completed_at",
                    "failed_at",
                    "canceled_at",
                    "last_error",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Analytics",
            {
                "fields": (
                    "recipient_count",
                    "sent_count",
                    "delivered_count",
                    "failed_count",
                    "bounced_count",
                    "complaint_count",
                    "open_count",
                    "unique_open_count",
                    "click_count",
                    "unique_click_count",
                    "unsubscribe_count",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    REVISION_FIELDS = frozenset({
        "campaign_type",
        "subject",
        "preheader_text",
        "template",
        "theme",
        "custom_html",
        "audience",
        "recipients",
        "target_group",
        "topic",
        "ignore_unsubscribe",
        "from_name",
        "reply_to_email",
        "track_opens",
        "track_clicks",
        "utm_source",
        "utm_medium",
        "utm_campaign",
    })

    # ------------------------------------------------------------------
    # Workspace routing
    # ------------------------------------------------------------------

    def get_urls(self):
        custom_urls = [
            path(
                "workspace/<int:object_id>/review/",
                self.admin_site.admin_view(
                    self.workspace_review_view
                ),
                name=(
                    "communication_"
                    "emailcampaign_workspace_review"
                ),
            ),
            path(
                "workspace/<int:object_id>/blocks/action/",
                self.admin_site.admin_view(
                    self.workspace_block_action_view
                ),
                name=(
                    "communication_"
                    "emailcampaign_workspace_block_action"
                ),
            ),
            path(
                "workspace/new/",
                self.admin_site.admin_view(
                    self.workspace_campaign_view
                ),
                name=(
                    "communication_"
                    "emailcampaign_workspace_new"
                ),
            ),
            path(
                "workspace/<int:object_id>/",
                self.admin_site.admin_view(
                    self.workspace_campaign_view
                ),
                name=(
                    "communication_"
                    "emailcampaign_workspace_change"
                ),
            ),
        ]

        return custom_urls + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        if request.GET.get("classic") == "1":
            return super().changelist_view(
                request,
                extra_context,
            )

        return self.workspace_home(request)

    def add_view(
        self,
        request,
        form_url="",
        extra_context=None,
    ):
        if request.GET.get("classic") == "1":
            return super().add_view(
                request,
                form_url,
                extra_context,
            )

        return redirect(
            "admin:communication_emailcampaign_workspace_new"
        )

    def change_view(
        self,
        request,
        object_id,
        form_url="",
        extra_context=None,
    ):
        if request.GET.get("classic") == "1":
            return super().change_view(
                request,
                object_id,
                form_url,
                extra_context,
            )

        return redirect(
            "admin:communication_emailcampaign_workspace_change",
            object_id=object_id,
        )

    def workspace_home(self, request):
        queryset = self.get_queryset(request)

        search_query = (
            request.GET.get("q") or ""
        ).strip()
        status_filter = (
            request.GET.get("status") or ""
        ).strip()

        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(subject__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(tag__icontains=search_query)
            )

        valid_statuses = {
            value
            for value, _label in CampaignStatus.choices
        }

        if status_filter in valid_statuses:
            queryset = queryset.filter(
                status=status_filter
            )

        queryset = queryset.order_by(
            "-created_at"
        )

        paginator = Paginator(
            queryset,
            20,
        )
        page_obj = paginator.get_page(
            request.GET.get("page")
        )

        all_campaigns = EmailCampaign.objects.all()

        metrics = all_campaigns.aggregate(
            total=Count("id"),
            draft=Count(
                "id",
                filter=Q(
                    status=CampaignStatus.DRAFT
                ),
            ),
            scheduled=Count(
                "id",
                filter=Q(
                    status=CampaignStatus.SCHEDULED
                ),
            ),
            sending=Count(
                "id",
                filter=Q(
                    status__in=[
                        CampaignStatus.QUEUED,
                        CampaignStatus.SENDING,
                    ]
                ),
            ),
            sent=Count(
                "id",
                filter=Q(
                    status=CampaignStatus.SENT
                ),
            ),
        )

        changelist_url = reverse(
            "admin:communication_emailcampaign_changelist"
        )

        context = {
            **self.admin_site.each_context(request),
            "title": "Communication Workspace",
            "opts": self.model._meta,
            "page_obj": page_obj,
            "campaigns": page_obj.object_list,
            "metrics": metrics,
            "status_choices": CampaignStatus.choices,
            "search_query": search_query,
            "status_filter": status_filter,
            "new_campaign_url": reverse(
                "admin:"
                "communication_emailcampaign_workspace_new"
            ),
            "classic_admin_url": (
                f"{changelist_url}?classic=1"
            ),
        }

        return render(
            request,
            "admin/communication/workspace.html",
            context,
        )

    def workspace_campaign_view(
        self,
        request,
        object_id=None,
    ):
        campaign = None

        if object_id is not None:
            campaign = get_object_or_404(
                self.get_queryset(request),
                pk=object_id,
            )

        if request.method == "POST":
            form = CampaignWorkspaceForm(
                request.POST,
                instance=campaign,
                admin_site=self.admin_site,
            )

            if form.is_valid():
                campaign = self._save_workspace_form(
                    request,
                    form,
                )

                response = self._run_workspace_action(
                    request,
                    campaign,
                )

                if response:
                    return response

                return redirect(
                    "admin:"
                    "communication_emailcampaign_workspace_change",
                    object_id=campaign.pk,
                )
        else:
            form = CampaignWorkspaceForm(
                instance=campaign,
                admin_site=self.admin_site,
            )

        blocks = []

        if campaign:
            blocks = list(
                campaign.content_blocks.order_by(
                    "sort_order",
                    "id",
                )
            )

        template_block_count = 0

        if campaign and campaign.template_id:
            template_block_count = (
                campaign.template
                .content_blocks
                .filter(is_enabled=True)
                .count()
            )

        context = {
            **self.admin_site.each_context(request),
            "title": (
                campaign.title
                if campaign
                else "New Campaign"
            ),
            "opts": self.model._meta,
            "campaign": campaign,
            "form": form,
            "blocks": blocks,
            "block_count": len(blocks),
            "workspace_home_url": reverse(
                "admin:"
                "communication_emailcampaign_changelist"
            ),
            "preview_url": (
                reverse(
                    "communication:"
                    "email-campaign-preview",
                    args=[campaign.pk],
                )
                if campaign
                else ""
            ),
            "classic_change_url": (
                reverse(
                    "admin:"
                    "communication_emailcampaign_change",
                    args=[campaign.pk],
                )
                + "?classic=1"
                if campaign
                else ""
            ),
            "has_content": (
                self._has_content(campaign)
                if campaign
                else False
            ),
            "workspace_blocks": [
                self._serialize_block(block)
                for block in blocks
            ],
            "block_type_choices": [
                {
                    "value": value,
                    "label": str(label),
                }
                for value, label in EmailBlockType.choices
            ],
            "block_action_url": (
                reverse(
                    "admin:"
                    "communication_"
                    "emailcampaign_workspace_block_action",
                    kwargs={
                        "object_id": campaign.pk,
                    },
                )
                if campaign
                else ""
            ),
            "block_builder_editable": (
                bool(
                    campaign
                    and campaign.can_edit_content
                )
            ),
            "template_block_count": template_block_count,
            "review_url": (
                reverse(
                    "admin:"
                    "communication_"
                    "emailcampaign_workspace_review",
                    kwargs={
                        "object_id": campaign.pk,
                    },
                )
                if campaign
                else ""
            ),
        }

        return render(
            request,
            "admin/communication/"
            "campaign_workspace.html",
            context,
        )

    def workspace_block_action_view(
        self,
        request,
        object_id,
    ):
        if request.method != "POST":
            return JsonResponse(
                {
                    "ok": False,
                    "error": "POST required.",
                },
                status=405,
            )

        campaign = get_object_or_404(
            self.get_queryset(request),
            pk=object_id,
        )

        if not self.has_change_permission(
            request,
            campaign,
        ):
            raise PermissionDenied

        if not campaign.can_edit_content:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        "This campaign can no longer "
                        "be edited."
                    ),
                },
                status=409,
            )

        try:
            payload = json.loads(
                request.body.decode("utf-8")
                or "{}"
            )
        except json.JSONDecodeError:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Invalid request body.",
                },
                status=400,
            )

        action = (
            payload.get("action")
            or ""
        ).strip()

        handlers = {
            "save": self._workspace_save_block,
            "delete": self._workspace_delete_block,
            "duplicate": self._workspace_duplicate_block,
            "toggle": self._workspace_toggle_block,
            "reorder": self._workspace_reorder_blocks,
            "materialize_template": (
                self._workspace_materialize_template
            ),
        }

        handler = handlers.get(action)

        if not handler:
            return JsonResponse(
                {
                    "ok": False,
                    "error": (
                        "Unsupported block action."
                    ),
                },
                status=400,
            )

        try:
            handler(
                campaign=campaign,
                payload=payload,
            )

        except ValueError as error:
            return JsonResponse(
                {
                    "ok": False,
                    "error": str(error),
                },
                status=400,
            )

        EmailCampaign.objects.filter(
            pk=campaign.pk
        ).update(
            content_version=F(
                "content_version"
            ) + 1
        )

        return self._workspace_blocks_response(
            campaign
        )

    def workspace_review_view(
        self,
        request,
        object_id,
    ):
        if request.method != "GET":
            return JsonResponse(
                {
                    "ok": False,
                    "error": "GET required.",
                },
                status=405,
            )

        campaign = get_object_or_404(
            self.get_queryset(request),
            pk=object_id,
        )

        if not self.has_view_or_change_permission(
            request,
            campaign,
        ):
            raise PermissionDenied

        service = CampaignPreflightService()

        report = service.build(
            campaign
        )

        queue_token = ""
        schedule_token = ""

        if report.can_send:
            queue_token = (
                service.make_confirmation_token(
                    campaign=campaign,
                    report=report,
                    action="queue",
                )
            )

            schedule_token = (
                service.make_confirmation_token(
                    campaign=campaign,
                    report=report,
                    action="schedule",
                )
            )

        return JsonResponse({
            "ok": True,
            "campaign_id": campaign.pk,
            "content_version": (
                campaign.content_version
            ),
            "audience_label": (
                report.audience_label
            ),
            "total_recipients": (
                report.total_recipients
            ),
            "suppressed_recipients": (
                report.suppressed_recipients
            ),
            "deliverable_recipients": (
                report.deliverable_recipients
            ),
            "can_send": report.can_send,
            "checks": [
                {
                    "key": check.key,
                    "label": check.label,
                    "state": check.state,
                    "detail": check.detail,
                }
                for check in report.checks
            ],
            "suppression_reasons": [
                {
                    "reason": item.reason,
                    "label": item.label,
                    "count": item.count,
                }
                for item in (
                    report.suppression_reasons
                )
            ],
            "confirmation": {
                "queue_token": queue_token,
                "schedule_token": (
                    schedule_token
                ),
                "strong_required": (
                    report.deliverable_recipients
                    >= service
                    .strong_confirmation_threshold
                ),
                "strong_threshold": (
                    service
                    .strong_confirmation_threshold
                ),
            },
        })

    def _workspace_save_block(
        self,
        *,
        campaign,
        payload,
    ):
        block_id = payload.get(
            "block_id"
        )
        fields = (
            payload.get("fields")
            or {}
        )

        if block_id:
            block = get_object_or_404(
                campaign.content_blocks,
                pk=block_id,
            )
        else:
            block = EmailCampaignBlock(
                campaign=campaign,
                sort_order=(
                    self._next_block_sort_order(
                        campaign
                    )
                ),
            )

        form_data = {
            "block_type": (
                fields.get("block_type")
                or block.block_type
                or ""
            ),
            "name": (
                fields.get("name")
                or ""
            ),
            "sort_order": (
                block.sort_order
                or self._next_block_sort_order(
                    campaign
                )
            ),
            "is_enabled": (
                "on"
                if fields.get(
                    "is_enabled",
                    True,
                )
                else ""
            ),
            "headline": (
                fields.get("headline")
                or ""
            ),
            "content": (
                fields.get("content")
                or ""
            ),
            "secondary_content": (
                fields.get(
                    "secondary_content"
                )
                or ""
            ),
            "image_url": (
                fields.get("image_url")
                or ""
            ),
            "image_alt": (
                fields.get("image_alt")
                or ""
            ),
            "action_label": (
                fields.get("action_label")
                or ""
            ),
            "action_url": (
                fields.get("action_url")
                or ""
            ),
            "attribution": (
                fields.get("attribution")
                or ""
            ),
            "alignment": (
                fields.get("alignment")
                or "left"
            ),
            "spacer_height": (
                fields.get("spacer_height")
                or 24
            ),
            "social_links": (
                fields.get("social_links")
                or ""
            ),
            "custom_html": (
                fields.get("custom_html")
                or ""
            ),
        }

        form = EmailCampaignBlockAdminForm(
            data=form_data,
            instance=block,
        )

        if not form.is_valid():
            raise ValueError(
                self._workspace_form_error_message(
                    form
                )
            )

        block = form.save(
            commit=False
        )
        block.campaign = campaign
        block.save()


    def _workspace_delete_block(
        self,
        *,
        campaign,
        payload,
    ):
        block = get_object_or_404(
            campaign.content_blocks,
            pk=payload.get("block_id"),
        )

        block.delete()

        self._renumber_campaign_blocks(
            campaign
        )


    def _workspace_duplicate_block(
        self,
        *,
        campaign,
        payload,
    ):
        source = get_object_or_404(
            campaign.content_blocks,
            pk=payload.get("block_id"),
        )

        clone = EmailCampaignBlock.objects.create(
            campaign=campaign,
            block_type=source.block_type,
            name=(
                f"{source.name} (Copy)"
                if source.name
                else ""
            ),
            data=deepcopy(
                source.data or {}
            ),
            styles=deepcopy(
                source.styles or {}
            ),
            sort_order=source.sort_order,
            is_enabled=source.is_enabled,
        )

        ordered = list(
            campaign.content_blocks.exclude(
                pk=clone.pk
            ).order_by(
                "sort_order",
                "id",
            )
        )

        source_index = next(
            (
                index
                for index, block in enumerate(
                    ordered
                )
                if block.pk == source.pk
            ),
            len(ordered) - 1,
        )

        ordered.insert(
            source_index + 1,
            clone,
        )

        self._apply_block_order(
            ordered
        )


    def _workspace_toggle_block(
        self,
        *,
        campaign,
        payload,
    ):
        block = get_object_or_404(
            campaign.content_blocks,
            pk=payload.get("block_id"),
        )

        block.is_enabled = bool(
            payload.get("enabled")
        )

        block.save(
            update_fields=[
                "is_enabled",
                "updated_at",
            ]
        )


    def _workspace_reorder_blocks(
        self,
        *,
        campaign,
        payload,
    ):
        block_ids = payload.get(
            "block_ids"
        )

        if not isinstance(
            block_ids,
            list,
        ):
            raise ValueError(
                "Invalid block order."
            )

        try:
            block_ids = [
                int(block_id)
                for block_id in block_ids
            ]
        except (TypeError, ValueError):
            raise ValueError(
                "Invalid block identifiers."
            )

        existing = list(
            campaign.content_blocks.order_by(
                "sort_order",
                "id",
            )
        )

        existing_ids = {
            block.pk
            for block in existing
        }

        if set(block_ids) != existing_ids:
            raise ValueError(
                "Block order is incomplete."
            )

        by_id = {
            block.pk: block
            for block in existing
        }

        ordered = [
            by_id[block_id]
            for block_id in block_ids
        ]

        self._apply_block_order(
            ordered
        )


    def _workspace_materialize_template(
        self,
        *,
        campaign,
        payload,
    ):
        if campaign.content_blocks.exists():
            raise ValueError(
                "Campaign blocks already exist."
            )

        if not campaign.template_id:
            raise ValueError(
                "Choose an email template first."
            )

        template_blocks = list(
            campaign.template
            .content_blocks
            .order_by(
                "sort_order",
                "id",
            )
        )

        if not template_blocks:
            raise ValueError(
                "The selected template has no blocks."
            )

        EmailCampaignBlock.objects.bulk_create(
            [
                EmailCampaignBlock(
                    campaign=campaign,
                    block_type=block.block_type,
                    name=block.name,
                    data=deepcopy(
                        block.data or {}
                    ),
                    styles=deepcopy(
                        block.styles or {}
                    ),
                    sort_order=block.sort_order,
                    is_enabled=block.is_enabled,
                )
                for block in template_blocks
            ]
        )

        self._renumber_campaign_blocks(
            campaign
        )


    def _next_block_sort_order(
        self,
        campaign,
    ):
        maximum = (
            campaign.content_blocks
            .aggregate(
                maximum=Max("sort_order")
            )
            .get("maximum")
        )

        return (
            (maximum or 0)
            + 10
        )


    def _renumber_campaign_blocks(
        self,
        campaign,
    ):
        blocks = list(
            campaign.content_blocks.order_by(
                "sort_order",
                "id",
            )
        )

        self._apply_block_order(
            blocks
        )


    def _apply_block_order(
        self,
        blocks,
    ):
        changed = []

        for index, block in enumerate(
            blocks,
            start=1,
        ):
            sort_order = index * 10

            if block.sort_order == sort_order:
                continue

            block.sort_order = sort_order
            changed.append(block)

        if changed:
            EmailCampaignBlock.objects.bulk_update(
                changed,
                ["sort_order"],
            )


    def _workspace_blocks_response(
        self,
        campaign,
    ):
        campaign.refresh_from_db()

        blocks = list(
            campaign.content_blocks.order_by(
                "sort_order",
                "id",
            )
        )

        return JsonResponse({
            "ok": True,
            "blocks": [
                self._serialize_block(block)
                for block in blocks
            ],
            "has_content": (
                self._has_content(
                    campaign
                )
            ),
        })


    def _serialize_block(
        self,
        block,
    ):
        return {
            "id": block.pk,
            "block_type": (
                block.block_type
            ),
            "block_type_label": (
                block.get_block_type_display()
            ),
            "name": block.name or "",
            "sort_order": block.sort_order,
            "is_enabled": (
                block.is_enabled
            ),
            "data": block.data or {},
            "styles": block.styles or {},
            "summary": (
                self._block_summary(
                    block
                )
            ),
        }


    def _block_summary(
        self,
        block,
    ):
        data = block.data or {}

        candidates = [
            data.get("title"),
            data.get("label"),
            data.get("attribution"),
            data.get("alt"),
            data.get("html"),
        ]

        for value in candidates:
            if not value:
                continue

            text = strip_tags(
                str(value)
            ).strip()

            if text:
                return text[:90]

        return ""


    def _workspace_form_error_message(
        self,
        form,
    ):
        messages_list = []

        for field_name, errors in (
            form.errors.items()
        ):
            field = form.fields.get(
                field_name
            )

            label = (
                field.label
                if field
                else field_name
            )

            for error in errors:
                messages_list.append(
                    f"{label}: {error}"
                )

        return (
            " ".join(messages_list)
            or "Block could not be saved."
        )
    
    def _save_workspace_form(
        self,
        request,
        form,
    ):
        with transaction.atomic():
            campaign = form.save(
                commit=False
            )

            is_new = not campaign.pk

            if is_new:
                campaign.created_by = (
                    request.user
                )
            elif self._form_changes_revision(
                form
            ):
                campaign.content_version = (
                    (campaign.content_version or 0)
                    + 1
                )

            campaign.updated_by = (
                request.user
            )

            campaign.save()
            form.save_m2m()

        return campaign

    def _form_changes_revision(
        self,
        form,
    ):
        return bool(
            self.REVISION_FIELDS.intersection(
                form.changed_data
            )
        )
    
    def _run_workspace_action(
        self,
        request,
        campaign,
    ):
        action = request.POST.get(
            "workspace_action",
            "save",
        )

        if action == "save":
            self.message_user(
                request,
                "Campaign saved.",
                messages.SUCCESS,
            )
            return None

        if action == "test":
            return self._workspace_send_test(
                request,
                campaign,
            )

        if action == "queue":
            return self._workspace_queue_now(
                request,
                campaign,
            )

        if action == "schedule":
            return self._workspace_schedule(
                request,
                campaign,
            )

        if action == "unschedule":
            return self._workspace_unschedule(
                request,
                campaign,
            )

        self.message_user(
            request,
            "Campaign saved.",
            messages.SUCCESS,
        )

        return None

    def _workspace_send_test(
        self,
        request,
        campaign,
    ):
        if not campaign.test_email:
            self.message_user(
                request,
                "Enter a Test Email before sending a test.",
                messages.ERROR,
            )
            return None

        if not self._has_content(campaign):
            self.message_user(
                request,
                "Add campaign content before sending a test.",
                messages.ERROR,
            )
            return None

        if send_test_email_for_campaign(
            campaign
        ):
            self._mark_test_sent(
                campaign
            )

            self.message_user(
                request,
                (
                    "Test email sent to "
                    f"{campaign.test_email}."
                ),
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "The test email could not be sent.",
                messages.ERROR,
            )

        return None

    def _mark_test_sent(
        self,
        campaign,
    ):
        sent_at = timezone.now()

        EmailCampaign.objects.filter(
            pk=campaign.pk
        ).update(
            last_test_sent_at=sent_at,
            last_test_email=(
                campaign.test_email
                or ""
            ),
            last_test_content_version=(
                campaign.content_version
            ),
        )

        campaign.last_test_sent_at = (
            sent_at
        )
        campaign.last_test_email = (
            campaign.test_email
            or ""
        )
        campaign.last_test_content_version = (
            campaign.content_version
        )
    
    def _workspace_queue_now(
        self,
        request,
        campaign,
    ):
        service = CampaignPreflightService()

        report = service.build(
            campaign
        )

        if not report.can_send:
            self.message_user(
                request,
                (
                    "Campaign cannot be sent yet. "
                    "Review the pre-send checklist."
                ),
                messages.ERROR,
            )
            return None

        token = request.POST.get(
            "confirmation_token",
            "",
        )

        if not service.validate_confirmation_token(
            token=token,
            campaign=campaign,
            report=report,
            action="queue",
        ):
            self.message_user(
                request,
                (
                    "The campaign changed after review. "
                    "Review it again before sending."
                ),
                messages.ERROR,
            )
            return None

        result = (
            CampaignSchedulingService()
            .queue_now(
                campaign_id=campaign.pk
            )
        )

        if result.queued:
            self.message_user(
                request,
                "Campaign queued for delivery.",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                result.error
                or "Campaign could not be queued.",
                messages.ERROR,
            )

        return None

    def _workspace_schedule(
        self,
        request,
        campaign,
    ):
        if not campaign.scheduled_time:
            self.message_user(
                request,
                "Choose a scheduled send time first.",
                messages.ERROR,
            )
            return None

        service = CampaignPreflightService()

        report = service.build(
            campaign
        )

        if not report.can_send:
            self.message_user(
                request,
                (
                    "Campaign cannot be scheduled yet. "
                    "Review the pre-send checklist."
                ),
                messages.ERROR,
            )
            return None

        token = request.POST.get(
            "confirmation_token",
            "",
        )

        if not service.validate_confirmation_token(
            token=token,
            campaign=campaign,
            report=report,
            action="schedule",
        ):
            self.message_user(
                request,
                (
                    "The campaign changed after review. "
                    "Review it again before scheduling."
                ),
                messages.ERROR,
            )
            return None

        try:
            CampaignSchedulingService().schedule(
                campaign_id=campaign.pk,
                run_at=campaign.scheduled_time,
                timezone_name=(
                    campaign.schedule_timezone
                ),
            )

            self.message_user(
                request,
                "Campaign scheduled successfully.",
                messages.SUCCESS,
            )

        except Exception as error:
            self.message_user(
                request,
                str(error),
                messages.ERROR,
            )

        return None

    def _workspace_unschedule(
        self,
        request,
        campaign,
    ):
        try:
            CampaignSchedulingService().unschedule(
                campaign_id=campaign.pk
            )

            self.message_user(
                request,
                "Campaign returned to Draft.",
                messages.SUCCESS,
            )

        except Exception as error:
            self.message_user(
                request,
                str(error),
                messages.ERROR,
            )

        return None

    # ------------------------------------------------------------------
    # Classic admin
    # ------------------------------------------------------------------

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "template",
            "theme",
            "audience",
            "topic",
            "created_by",
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.pk:
            obj.created_by = request.user

        elif self._form_changes_revision(
            form
        ):
            obj.content_version = (
                (obj.content_version or 0)
                + 1
            )

        obj.updated_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    @admin.display(description="Status")
    def status_badge(self, obj):
        styles = {
            CampaignStatus.DRAFT: (
                "#666",
                "#F1F1F1",
            ),
            CampaignStatus.REVIEW: (
                "#8A4B08",
                "#FFF1D6",
            ),
            CampaignStatus.READY: (
                "#14532D",
                "#DCFCE7",
            ),
            CampaignStatus.SCHEDULED: (
                "#1E3A8A",
                "#DBEAFE",
            ),
            CampaignStatus.QUEUED: (
                "#4338CA",
                "#E0E7FF",
            ),
            CampaignStatus.SENDING: (
                "#6B21A8",
                "#F3E8FF",
            ),
            CampaignStatus.PAUSED: (
                "#854D0E",
                "#FEF3C7",
            ),
            CampaignStatus.SENT: (
                "#166534",
                "#DCFCE7",
            ),
            CampaignStatus.CANCELED: (
                "#525252",
                "#E5E5E5",
            ),
            CampaignStatus.FAILED: (
                "#991B1B",
                "#FEE2E2",
            ),
        }

        foreground, background = styles.get(
            obj.status,
            ("#333", "#EEE"),
        )

        return format_html(
            '<span style="display:inline-block;padding:3px 8px;'
            'border-radius:999px;font-weight:600;color:{};'
            'background:{};">{}</span>',
            foreground,
            background,
            obj.get_status_display(),
        )

    @admin.display(description="Audience")
    def audience_summary(self, obj):
        if obj.recipients.exists():
            return (
                f"Manual · "
                f"{obj.recipients.count()}"
            )

        if obj.audience_id:
            return obj.audience.name

        return obj.get_target_group_display()

    @admin.display(description="Delivery")
    def delivery_summary(self, obj):
        if not obj.recipient_count:
            return "—"

        return (
            f"{obj.sent_count:,}/"
            f"{obj.recipient_count:,}"
        )

    @admin.display(description="Engagement")
    def engagement_summary(self, obj):
        if not obj.sent_count:
            return "—"

        return (
            f"Open {obj.open_rate:.1f}% · "
            f"Click {obj.click_rate:.1f}%"
        )

    @admin.display(description="Preview")
    def preview_link(self, obj):
        url = reverse(
            "communication:"
            "email-campaign-preview",
            args=[obj.pk],
        )

        return format_html(
            '<a href="{}" target="_blank">'
            "Preview</a>",
            url,
        )

    @admin.action(
        description="Mark selected campaigns as ready"
    )
    def mark_ready(self, request, queryset):
        count = queryset.filter(
            status__in=[
                CampaignStatus.DRAFT,
                CampaignStatus.REVIEW,
                CampaignStatus.PAUSED,
                CampaignStatus.FAILED,
            ]
        ).update(
            status=CampaignStatus.READY,
            failed_at=None,
            last_error="",
        )

        self.message_user(
            request,
            f"{count} campaign(s) marked ready.",
            messages.SUCCESS,
        )

    @admin.action(
        description="Queue selected campaigns for sending now"
    )
    def queue_campaigns_now(
        self,
        request,
        queryset,
    ):
        service = CampaignSchedulingService()
        queued = 0

        for campaign in queryset:
            if not self._has_content(campaign):
                self.message_user(
                    request,
                    f"'{campaign.title}' has no email content.",
                    messages.ERROR,
                )
                continue

            result = service.queue_now(
                campaign_id=campaign.id
            )

            if result.queued:
                queued += 1
            else:
                self.message_user(
                    request,
                    (
                        f"Could not queue "
                        f"'{campaign.title}': "
                        f"{result.error}"
                    ),
                    messages.WARNING,
                )

        if queued:
            self.message_user(
                request,
                f"{queued} campaign(s) queued.",
                messages.SUCCESS,
            )

    @admin.action(
        description="Schedule selected campaigns"
    )
    def schedule_campaigns(
        self,
        request,
        queryset,
    ):
        service = CampaignSchedulingService()
        scheduled = 0

        for campaign in queryset:
            if not campaign.scheduled_time:
                self.message_user(
                    request,
                    (
                        f"Set a scheduled time for "
                        f"'{campaign.title}' first."
                    ),
                    messages.WARNING,
                )
                continue

            if not self._has_content(campaign):
                self.message_user(
                    request,
                    f"'{campaign.title}' has no email content.",
                    messages.ERROR,
                )
                continue

            try:
                service.schedule(
                    campaign_id=campaign.id,
                    run_at=campaign.scheduled_time,
                    timezone_name=(
                        campaign.schedule_timezone
                    ),
                )
                scheduled += 1

            except Exception as error:
                self.message_user(
                    request,
                    (
                        f"Could not schedule "
                        f"'{campaign.title}': {error}"
                    ),
                    messages.ERROR,
                )

        if scheduled:
            self.message_user(
                request,
                f"{scheduled} campaign(s) scheduled.",
                messages.SUCCESS,
            )

    @admin.action(
        description="Unschedule selected campaigns"
    )
    def unschedule_campaigns(
        self,
        request,
        queryset,
    ):
        service = CampaignSchedulingService()
        count = 0

        for campaign in queryset:
            try:
                service.unschedule(
                    campaign_id=campaign.id
                )
                count += 1
            except Exception:
                continue

        if count:
            self.message_user(
                request,
                (
                    f"{count} campaign(s) "
                    "returned to Draft."
                ),
                messages.SUCCESS,
            )

    @admin.action(description="Send test email")
    def send_test_email(
        self,
        request,
        queryset,
    ):
        sent = 0

        for campaign in queryset:
            if not campaign.test_email:
                self.message_user(
                    request,
                    (
                        f"No test email configured for "
                        f"'{campaign.title}'."
                    ),
                    messages.WARNING,
                )
                continue

            if send_test_email_for_campaign(
                campaign
            ):
                self._mark_test_sent(
                    campaign
                )
                sent += 1
            else:
                self.message_user(
                    request,
                    (
                        f"Test email failed for "
                        f"'{campaign.title}'."
                    ),
                    messages.ERROR,
                )

        if sent:
            self.message_user(
                request,
                f"{sent} test email(s) sent.",
                messages.SUCCESS,
            )

    @admin.action(
        description="Clone selected campaigns"
    )
    def clone_campaigns(
        self,
        request,
        queryset,
    ):
        count = 0

        for campaign in queryset.prefetch_related(
            "recipients",
            "content_blocks",
        ):
            with transaction.atomic():
                clone = self._clone_campaign(
                    campaign,
                    request.user,
                )

                clone.recipients.set(
                    campaign.recipients.all()
                )

                EmailCampaignBlock.objects.bulk_create(
                    [
                        EmailCampaignBlock(
                            campaign=clone,
                            block_type=block.block_type,
                            name=block.name,
                            data=block.data,
                            styles=block.styles,
                            sort_order=block.sort_order,
                            is_enabled=block.is_enabled,
                        )
                        for block in (
                            campaign.content_blocks.all()
                        )
                    ]
                )

            count += 1

        self.message_user(
            request,
            f"{count} campaign(s) cloned.",
            messages.SUCCESS,
        )

    def _clone_campaign(
        self,
        source,
        user,
    ):
        clone = EmailCampaign()

        reset_fields = {
            "id",
            "created_at",
            "updated_at",
            "status",
            "review_requested_at",
            "approved_by",
            "approved_at",
            "queued_at",
            "last_dispatch_at",
            "dispatch_attempt_count",
            "celery_task_id",
            "started_at",
            "sent_at",
            "completed_at",
            "canceled_at",
            "failed_at",
            "recipient_count",
            "sent_count",
            "delivered_count",
            "failed_count",
            "bounced_count",
            "complaint_count",
            "open_count",
            "unique_open_count",
            "click_count",
            "unique_click_count",
            "unsubscribe_count",
            "last_error",
            "created_by",
            "updated_by",
        }

        for field in (
            EmailCampaign._meta.concrete_fields
        ):
            if (
                field.primary_key
                or field.name in reset_fields
            ):
                continue

            setattr(
                clone,
                field.name,
                getattr(source, field.name),
            )

        clone.title = (
            f"{source.title} (Copy)"
        )
        clone.status = CampaignStatus.DRAFT
        clone.scheduled_time = None
        clone.created_by = user
        clone.updated_by = user
        clone.save()

        return clone

    def _has_content(
        self,
        campaign,
    ):
        return (
            CampaignPreflightService
            .has_renderable_content(
                campaign
            )
        )