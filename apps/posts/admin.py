# apps/posts/admin.py
from django.contrib import admin
from django.contrib.admin import SimpleListFilter, DateFieldListFilter
from django.contrib.contenttypes.models import ContentType
import csv
from django.http import HttpResponse
from django.db import models
from django.forms import Textarea
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Q

from apps.posts.models.pray import Pray
from apps.posts.models.moment import Moment
from apps.posts.models.mission import Mission
from apps.posts.models.testimony import Testimony
from apps.posts.models.witness import Witness
from apps.posts.models.announcement import Announcement
from apps.posts.models.worship import Worship
from apps.posts.models.preach import Preach
from apps.posts.models.common import Resource
from apps.posts.models.conference import Conference
from apps.posts.models.future_conference import FutureConference
from apps.posts.models.lesson import Lesson
from apps.posts.models.library import Library
from apps.posts.models.media_content import MediaContent
from apps.posts.models.service_event import ServiceEvent
from apps.posts.models.reaction import Reaction
from apps.posts.models.comment import Comment

# -------------------- Common mixins & helpers --------------------

class MarkActiveMixin:
    # Bulk toggle for is_active
    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Selected items have been marked as inactive.")
    make_inactive.short_description = "Mark selected items as inactive"

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Selected items have been marked as active.")
    make_active.short_description = "Mark selected items as active"


def admin_change_link_for_instance(obj):
    """
    Build a safe admin change link for any model instance.
    Returns plain text if no link can be built.
    """
    try:
        opts = obj._meta
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
        label = str(obj)
        return format_html('<a href="{}">{}</a>', url, label)
    except Exception:
        return str(obj)


def admin_change_link_for_ct_and_pk(ct, pk):
    """
    Build admin link from ContentType + object_id (GFK).
    Returns plain text if target not found.
    """
    try:
        model_class = ct.model_class()
        if not model_class:
            return f"{ct.app_label}.{ct.model}#{pk}"
        target = model_class.objects.filter(pk=pk).first()
        if not target:
            return f"{ct.app_label}.{ct.model}#{pk}"
        return admin_change_link_for_instance(target)
    except Exception:
        return f"{ct.app_label}.{ct.model}#{pk}"


# -------------------- Filters (content target, flags) --------------------

class ContentAppFilter(SimpleListFilter):
    """Filter by target content_type app_label."""
    title = "Content App"
    parameter_name = "ct_app"

    def lookups(self, request, model_admin):
        qs = ContentType.objects.filter(
            Q(app_label="posts") | Q(app_label="profiles") | Q(app_label="profilesOrg")
        ).order_by("app_label", "model")
        # unique app labels
        apps = sorted(set(qs.values_list("app_label", flat=True)))
        return [(a, a) for a in apps]

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            return queryset.filter(content_type__app_label=val)
        return queryset


class ContentModelFilter(SimpleListFilter):
    """Filter by target content_type model name."""
    title = "Content Model"
    parameter_name = "ct_model"

    def lookups(self, request, model_admin):
        qs = ContentType.objects.filter(
            Q(app_label="posts") | Q(app_label="profiles") | Q(app_label="profilesOrg")
        ).order_by("app_label", "model")
        return [ (f"{ct.app_label}.{ct.model}", f"{ct.app_label}.{ct.model}") for ct in qs ]

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            try:
                app, model = val.split(".", 1)
                return queryset.filter(content_type__app_label=app, content_type__model=model)
            except ValueError:
                return queryset
        return queryset


class HasMessageFilter(SimpleListFilter):
    """Reaction: has/non-empty message."""
    title = "Has message"
    parameter_name = "has_msg"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(~Q(message=""), message__isnull=False)
        if val == "no":
            return queryset.filter(Q(message="") | Q(message__isnull=True))
        return queryset


class HasRecommentFilter(SimpleListFilter):
    """Comment: is a reply or has a parent."""
    title = "Is reply"
    parameter_name = "is_reply"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(recomment__isnull=False)
        if val == "no":
            return queryset.filter(recomment__isnull=True)
        return queryset


# -------------------- Filter for OfficialVideo --------------------
class OfficialVideoFilter(SimpleListFilter):
    """Filter to show only items related to OfficialVideo."""
    title = "Official Video only"
    parameter_name = "is_official_video"

    def lookups(self, request, model_admin):
        return [("yes", "Yes (OfficialVideo)"), ("no", "No (Others)")]

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(
                content_type__app_label="main",
                content_type__model="officialvideo"
            )
        elif val == "no":
            return queryset.exclude(
                content_type__app_label="main",
                content_type__model="officialvideo"
            )
        return queryset


# -------------------- Reaction Admin --------------------
@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    """Fast, searchable, and target-aware admin for reactions."""

    list_display = (
        "user_link",
        "reaction_badge",
        "target_link",
        "target_type",
        "message_snippet",
        "timestamp",
    )
    list_display_links = ("user_link", "reaction_badge", "target_link")

    list_filter = (
        "reaction_type",
        ContentAppFilter,
        ContentModelFilter,
        HasMessageFilter,
        OfficialVideoFilter,  # ✅ added
        "timestamp",
    )

    search_fields = (
        "name__username",
        "name__email",
        "name__name",
        "name__family",
        "reaction_type",
        "object_id",
    )

    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(attrs={
                "rows": 3,
                "style": "font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; line-height:1.4;"
            })
        }
    }

    autocomplete_fields = ("name",)
    list_select_related = ("name", "content_type")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"
    list_per_page = 50
    actions = ("clear_empty_messages", "remove_suspicious_links", "export_csv_secure")


    # --- Display helpers ---
    @admin.display(description="User", ordering="name__username")
    def user_link(self, obj):
        u = getattr(obj, "name", None)
        return admin_change_link_for_instance(u) if u else "-"

    @admin.display(description="Reaction", ordering="reaction_type")
    def reaction_badge(self, obj):
        color = {
            "like": "#C40233",
            "bless": "#F6C860",
            "gratitude": "#3BAA75",
            "amen": "#A23BEC",
            "encouragement": "#0F52BA",
            "empathy": "#48D1CC",
            "faithfire": "#D73F09",
            "support": "#7A5CA2",
        }.get(getattr(obj, "reaction_type", ""), "#2B2C30")
        t = getattr(obj, "reaction_type", "") or "—"
        return mark_safe(
            f'<span style="display:inline-block;padding:.15rem .4rem;border-radius:6px;'
            f'background:rgba(0,0,0,.04);border:1px solid rgba(0,0,0,.06);'
            f'color:{color};font-weight:600;">{t}</span>'
        )

    @admin.display(description="Target", ordering="content_type")
    def target_link(self, obj):
        ct = getattr(obj, "content_type", None)
        pk = getattr(obj, "object_id", None)
        if ct and pk:
            return admin_change_link_for_ct_and_pk(ct, pk)
        return "-"

    @admin.display(description="Target Type")
    def target_type(self, obj):
        ct = getattr(obj, "content_type", None)
        return f"{ct.app_label}.{ct.model}" if ct else "-"

    @admin.display(description="Message")
    def message_snippet(self, obj):
        msg = getattr(obj, "message", "") or ""
        if not msg:
            return "—"
        return (msg[:60] + "…") if len(msg) > 60 else msg

    # --- Actions (anti-spam / hygiene) ---
    actions = ("clear_empty_messages", "remove_suspicious_links")

    @admin.action(description="Clear empty/whitespace messages")
    def clear_empty_messages(self, request, queryset):
        updated = queryset.filter(
            Q(message__isnull=True) | Q(message="") | Q(message__regex=r"^\s+$")
        ).update(message="")
        self.message_user(request, f"Cleared {updated} message(s).")

    @admin.action(description="Remove messages that contain links (anti-spam)")
    def remove_suspicious_links(self, request, queryset):
        qs = queryset.filter(
            Q(message__icontains="http://")
            | Q(message__icontains="https://")
            | Q(message__iregex=r"\bwww\.")
        )
        count = 0
        for r in qs:
            r.message = ""
            r.save(update_fields=["message"])
            count += 1
        self.message_user(request, f"Removed links from {count} reaction(s).")

    @admin.action(description="Export selected as CSV (decrypted)")
    def export_csv_secure(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can export decrypted CSV.", level="error")
            return
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="reactions.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "user", "reaction_type", "message", "content_type", "object_id", "timestamp"])
        for r in queryset.select_related("name", "content_type"):
            writer.writerow([
                r.id,
                getattr(r.name, "username", ""),
                r.reaction_type,
                r.message or "",                     # decrypted by field
                f"{r.content_type.app_label}.{r.content_type.model}" if r.content_type_id else "",
                r.object_id,
                r.timestamp.isoformat(),
            ])
        return response


# -------------------- Comment Admin --------------------
@admin.register(Comment)
class CommentAdmin(MarkActiveMixin, admin.ModelAdmin):
    """Powerful moderation panel for comments with GFK target insight."""

    list_display = (
        "user_link",
        "comment_summary",
        "target_link",
        "target_type",  # ✅ added
        "is_reply_flag",
        "published_at",
        "is_active",
    )
    list_display_links = ("user_link", "comment_summary", "target_link")

    list_filter = (
        "is_active",
        HasRecommentFilter,
        ContentAppFilter,
        ContentModelFilter,
        OfficialVideoFilter,  # ✅ added
        "published_at",
    )

    search_fields = (
        "name__username",
        "name__email",
        "name__name",
        "name__family",
        "object_id",
    )

    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(attrs={
                "rows": 6,
                "style": "font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; line-height:1.5;"
            })
        }
    }

    date_hierarchy = "published_at"
    list_select_related = ("name", "recomment", "content_type")
    autocomplete_fields = ("name", "recomment")
    ordering = ("-published_at",)
    list_per_page = 50
    actions = ("make_active", "make_inactive", "remove_links_in_comments", "export_csv_secure")

    # --- Display helpers ---
    @admin.display(description="User", ordering="name__username")
    def user_link(self, obj):
        u = getattr(obj, "name", None)
        return admin_change_link_for_instance(u) if u else "-"

    @admin.display(description="Comment")
    def comment_summary(self, obj):
        text = getattr(obj, "comment", "") or ""
        return (text[:80] + "…") if len(text) > 80 else text or "—"

    @admin.display(description="Is reply?")
    def is_reply_flag(self, obj):
        return bool(getattr(obj, "recomment_id", None))
    is_reply_flag.boolean = True

    @admin.display(description="Target")
    def target_link(self, obj):
        ct = getattr(obj, "content_type", None)
        pk = getattr(obj, "object_id", None)
        if ct and pk:
            return admin_change_link_for_ct_and_pk(ct, pk)
        return "-"

    @admin.display(description="Target Type")
    def target_type(self, obj):
        ct = getattr(obj, "content_type", None)
        return f"{ct.app_label}.{ct.model}" if ct else "-"

    # --- Actions (anti-spam / hygiene) ---
    @admin.action(description="Remove links from selected comments (anti-spam)")
    def remove_links_in_comments(self, request, queryset):
        qs = queryset.filter(
            Q(comment__icontains="http://")
            | Q(comment__icontains="https://")
            | Q(comment__iregex=r"\bwww\.")
        )
        count = 0
        for c in qs:
            safe = c.comment
            for pat in ["http://", "https://"]:
                safe = safe.replace(pat, "")
            c.comment = safe
            c.save(update_fields=["comment"])
            count += 1
        self.message_user(request, f"Sanitized {count} comment(s).")

    @admin.action(description="Export selected as CSV (decrypted)")
    def export_csv_secure(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can export decrypted CSV.", level="error")
            return
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="comments.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "user", "is_reply", "comment", "content_type", "object_id", "published_at", "is_active"])
        for c in queryset.select_related("name", "content_type", "recomment"):
            writer.writerow([
                c.id,
                getattr(c.name, "username", ""),
                bool(c.recomment_id),
                c.comment or "",                      # decrypted by field
                f"{c.content_type.app_label}.{c.content_type.model}" if c.content_type_id else "",
                c.object_id,
                c.published_at.isoformat(),
                c.is_active,
            ])
        return response



#  Moment Admin ------------------------------------------------------------------------------------------------------------
@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin):
    """
    Admin for Moment
    - Moderation friendly
    - Visibility aware
    - Scales for large datasets
    """

    # -------------------------------------------------
    # List view
    # -------------------------------------------------
    list_display = (
        "id",
        "owner_display",
        "media_type",
        "visibility",
        'is_converted',
        "is_active",
        "is_hidden",
        "is_suspended",
        "reactions_count",
        "comments_count",
        "published_at",
    )

    list_filter = (
        "visibility",
        "is_active",
        "is_hidden",
        "is_suspended",
        "published_at",
    )

    search_fields = (
        "caption",
        "object_id",
    )

    ordering = ("-published_at",)
    date_hierarchy = "published_at"

    readonly_fields = (
        "id",
        "owner_display",
        "reactions_count",
        "recomments_count",
        "comments_count",
        "reactions_breakdown",
        "view_count_internal",
        "last_viewed_at",
        "published_at",
        "updated_at",
    )

    list_editable = (
        "visibility",
    )
    
    # -------------------------------------------------
    # Field layout
    # -------------------------------------------------
    fieldsets = (
        (
            "Owner",
            {
                "fields": (
                    "owner_display",
                    "content_type",
                    "object_id",
                )
            },
        ),
        (
            "Content",
            {
                "fields": (
                    "caption",
                    "image",
                    "video",
                    "thumbnail",
                )
            },
        ),
        (
            "Visibility",
            {
                "fields": (
                    "visibility",
                    "is_hidden",
                    "is_converted",
                )
            },
        ),
        (
            "Moderation",
            {
                "fields": (
                    "is_active",
                    "is_suspended",
                    "reports_count",
                    "suspended_at",
                    "suspension_reason",
                )
            },
        ),
        (
            "Interactions (denormalized)",
            {
                "fields": (
                    "reactions_count",
                    "reactions_breakdown",
                    "comments_count",
                    "recomments_count",
                )
            },
        ),
        (
            "Analytics",
            {
                "fields": (
                    "view_count_internal",
                    "last_viewed_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "published_at",
                    "updated_at",
                )
            },
        ),
    )

    # -------------------------------------------------
    # Admin helpers
    # -------------------------------------------------
    def owner_display(self, obj):
        """
        Human-readable owner representation.
        """
        try:
            ct = ContentType.objects.get_for_id(obj.content_type_id)
            model_name = ct.model
            return f"{model_name} #{obj.object_id}"
        except Exception:
            return "Unknown"

    owner_display.short_description = "Owner"
    owner_display.admin_order_field = "object_id"

    def media_type(self, obj):
        if obj.image:
            return "Image"
        if obj.video:
            return "Video"
        return "-"

    media_type.short_description = "Media"





# Testimony Admin ---------------------------------------------------------------------------------------------------------
@admin.register(Testimony)
class TestimonyAdmin(admin.ModelAdmin):
    """
    Admin focused on observability & troubleshooting of media conversion.
    """
    # -------- List view --------
    list_display = (
        "id",
        "slug",
        "type",
        "owner_repr",
        "is_active",
        "is_converted",
        "media_flags",
        "published_at",
        "updated_at",
        "visibility",
    )
    list_filter = (
        "type",
        "is_active",
        "is_converted",
        "is_hidden",
        # "is_restricted",
        "is_suspended",
        ("published_at", DateFieldListFilter),
        "content_type",    # lets you filter by owner model (Member, Organization, …)
    )
    search_fields = (
        "slug",
        "title",
        "content",
        "audio",
        "video",
        "thumbnail",
    )
    ordering = ("-id",)

    list_editable = (
        "visibility",
    )
    
    # Speed & UX for large M2M sets
    filter_horizontal = ("org_tags", "user_tags")
    raw_id_fields = ("user_tags", "org_tags")

    # Fields layout on detail
    readonly_fields = (
        "owner_link",
        "preview_media",
        "file_links",
        "diagnostics",
        # timestamps are usually readonly in admin
        "published_at",
        "updated_at",
    )

    fieldsets = (
        ("Basic", {
            "fields": (
                ("type", "title", "slug"),
                "content",
            )
        }),
        ("Owner (Generic)", {
            "fields": (
                ("content_type", "object_id"),
                "owner_link",
            )
        }),
        ("Media", {
            "fields": (
                "thumbnail",
                "audio",
                "video",
                "preview_media",
                "file_links",
            )
        }),
        ("Moderation & Visibility", {
            "fields": (
                ("is_active", "is_hidden", "is_suspended", "visibility"),
                "reports_count",
            )
        }),
        ("System", {
            "fields": (
                ("is_converted",),
                ("published_at", "updated_at"),
                "diagnostics",
            )
        }),
        ("Tags (optional)", {
            "classes": ("collapse",),
            "fields": ("org_tags", "user_tags"),
        }),
    )

    # -------- Computed columns / helpers --------
    def owner_repr(self, obj: Testimony):
        """Compact owner representation for the changelist."""
        try:
            return f"{obj.content_type.model}#{obj.object_id}"
        except Exception:
            return "-"

    owner_repr.short_description = "Owner"

    def owner_link(self, obj: Testimony):
        """Clickable link to owner object in admin (if available)."""
        try:
            ct: ContentType = obj.content_type
            url = reverse(f"admin:{ct.app_label}_{ct.model}_change", args=[obj.object_id])
            return mark_safe(f'<a href="{url}">{ct.app_label}.{ct.model} #{obj.object_id}</a>')
        except Exception:
            return "-"

    owner_link.short_description = "Owner link"

    def media_flags(self, obj: Testimony):
        """Quick flags: A/V/T presence."""
        a = "A✔" if getattr(obj, "audio") else "A–"
        v = "V✔" if getattr(obj, "video") else "V–"
        t = "T✔" if getattr(obj, "thumbnail") else "T–"
        return f"{a} {v} {t}"

    media_flags.short_description = "Media"

    def preview_media(self, obj: Testimony):
        """Inline preview (best-effort). HLS may only play natively on Safari."""
        parts = []
        try:
            if obj.thumbnail:
                parts.append(f'<div><img src="{obj.thumbnail.url}" alt="thumb" style="max-width:220px;height:auto;border:1px solid #ddd;padding:2px"/></div>')
        except Exception:
            pass

        try:
            if obj.audio:
                parts.append(f'''
                    <div style="margin-top:8px">
                      <audio controls preload="metadata" style="width:280px">
                        <source src="{obj.audio.url}"/>
                        Your browser does not support the audio element.
                      </audio>
                    </div>
                ''')
        except Exception:
            pass

        # HLS playback via <video src=master.m3u8> works natively on Safari; others may need hls.js
        try:
            if obj.video:
                parts.append(f'''
                    <div style="margin-top:8px">
                      <video controls preload="metadata" style="max-width:420px;height:auto">
                        <source src="{obj.video.url}" type="application/vnd.apple.mpegurl"/>
                        Your browser may not play HLS natively.
                      </video>
                    </div>
                ''')
        except Exception:
            pass

        return mark_safe("".join(parts) or "<em>No preview</em>")

    preview_media.short_description = "Preview"

    def file_links(self, obj: Testimony):
        """Direct links to storage paths (helpful for verifying S3 uploads)."""
        rows = []
        for label in ("thumbnail", "audio", "video"):
            f = getattr(obj, label, None)
            if f:
                try:
                    rows.append(f'<div><strong>{label}</strong>: <a href="{f.url}" target="_blank" rel="noopener">{f.name}</a></div>')
                except Exception:
                    rows.append(f'<div><strong>{label}</strong>: {getattr(f, "name", "-")}</div>')
            else:
                rows.append(f"<div><strong>{label}</strong>: <em>—</em></div>")
        return mark_safe("".join(rows))

    file_links.short_description = "File URLs"

    def diagnostics(self, obj: Testimony):
        """
        Quick consistency check: flags common causes of 'file on S3 but no DB/404' or conversion stalls.
        """
        issues = []

        # type/content coherence (mirrors model.clean)
        if obj.type == Testimony.TYPE_AUDIO:
            if not obj.audio:
                issues.append("Audio testimony has no audio file.")
            if obj.content:
                issues.append("Audio testimony should not have content.")
            if obj.video:
                issues.append("Audio testimony should not have video.")
        elif obj.type == Testimony.TYPE_VIDEO:
            if not obj.video:
                issues.append("Video testimony has no video file.")
            if obj.content:
                issues.append("Video testimony should not have content.")
            if obj.audio:
                issues.append("Video testimony should not have audio.")
        elif obj.type == Testimony.TYPE_WRITTEN:
            if not obj.content:
                issues.append("Written testimony requires content.")
            if obj.audio or obj.video:
                issues.append("Written testimony should not have audio/video.")

        # conversion hints
        try:
            if obj.type in (Testimony.TYPE_AUDIO, Testimony.TYPE_VIDEO):
                if not obj.is_converted:
                    issues.append("Media not converted yet (is_converted=False).")
                # if audio present and name already endswith .mp3 but is_converted False
                if obj.type == Testimony.TYPE_AUDIO and getattr(obj, "audio") and str(obj.audio.name).lower().endswith(".mp3") and not obj.is_converted:
                    issues.append("Audio is MP3 but is_converted=False (no-op case).")
        except Exception:
            pass

        # visibility
        if not obj.is_active:
            issues.append("Item is inactive.")
        if obj.is_hidden:
            issues.append("Item is hidden.")
        # if obj.is_restricted:
        #     issues.append("Item is restricted.")
        if obj.is_suspended:
            issues.append("Item is suspended.")

        if not issues:
            return mark_safe('<span style="color:#0a0">No issues detected</span>')

        lis = "".join(f"<li>{admin.utils.escape(i)}</li>" for i in issues)
        return mark_safe(f'<ul style="margin:0;padding-left:16px;color:#a00">{lis}</ul>')

    diagnostics.short_description = "Diagnostics"

    # -------- Actions --------
    actions = ("action_mark_active", "action_mark_inactive", "action_requeue_conversion", "action_rebuild_slug")

    @admin.action(description="Mark selected as Active")
    def action_mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} item(s) marked active.")

    @admin.action(description="Mark selected as Inactive")
    def action_mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} item(s) marked inactive.")

    @admin.action(description="Requeue media conversion")
    def action_requeue_conversion(self, request, queryset):
        # Force reconversion and (re)enqueue tasks
        cnt = 0
        for obj in queryset:
            try:
                obj.is_converted = False
                obj.save(update_fields=["is_converted"])
                obj.convert_uploaded_media_async()  # from MediaConversionMixin
                cnt += 1
            except Exception as e:
                self.message_user(request, f"Failed to requeue for {obj.pk}: {e}", level="error")
        self.message_user(request, f"{cnt} item(s) requeued for conversion.")

    @admin.action(description="Rebuild slug (unique)")
    def action_rebuild_slug(self, request, queryset):
        """
        Useful if you suspect slug collision caused DB rollback:
        regenerates slug using SlugMixin logic by clearing and re-saving.
        """
        cnt = 0
        for obj in queryset:
            try:
                # Keep a stable source; SlugMixin will regenerate
                obj.slug = None
                obj.save(update_fields=["slug"])  # triggers SlugMixin.save
                cnt += 1
            except Exception as e:
                self.message_user(request, f"Failed to rebuild slug for {obj.pk}: {e}", level="error")
        self.message_user(request, f"{cnt} slug(s) rebuilt.")

    # -------- Search tweaks --------
    def get_search_results(self, request, queryset, search_term):
        """
        Extend default search to allow quick owner lookup by 'object_id' when the term is numeric.
        """
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term.isdigit():
            qs = qs | queryset.filter(object_id=int(search_term))
        return qs, use_distinct




# Resource Admin -----------------------------------------------------------------------------------
@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['resource_name', 'resource_type', 'author', 'uploaded_at', 'is_active']
    search_fields = ['resource_name', 'resource_type', 'author', 'license']
    list_filter = ['resource_type', 'uploaded_at', 'is_active']
    actions = ['make_inactive', 'make_active']
    date_hierarchy = 'uploaded_at'
    readonly_fields = ['uploaded_at']

    # Optimized queryset for related fields
    def get_queryset(self, request):
        """Optimize the queryset for the Resource model."""
        queryset = super().get_queryset(request)
        return queryset
    
    
# Service Event Admin ------------------------------------------------------------------------------
@admin.register(ServiceEvent)
class ServiceEventAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['custom_event_type', 'organization_type', 'event_type_display', 'event_date', 'start_time', 'is_active']
    list_filter = ['organization_type', 'event_method', 'recurring', 'is_active', 'is_hidden', 'is_restricted', 'event_date']
    search_fields = ['custom_event_type', 'organization_type', 'event_type', 'description']
    autocomplete_fields = ['location']
    actions = ['make_inactive', 'make_active']
    date_hierarchy = 'event_date'
    fieldsets = (
        ('Basic Info', {
            'fields': ('organization_type', 'event_type', 'custom_event_type', 'event_banner', 'description', 'contact_information')
        }),
        ('Event Details', {
            'fields': ('event_date', 'day_of_week', 'start_time', 'duration', 'additional_notes', 'recurring', 'frequency')
        }),
        ('Location and Method', {
            'fields': ('event_method', 'location', 'event_link')
        }),
        ('Registration', {
            'fields': ('registration_required', 'registration_link')
        }),
        ('Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )

    # Display custom event type or fallback to standard event type
    def event_type_display(self, obj):
        """Show the event type or custom event type if available."""
        return obj.custom_event_type if obj.custom_event_type else obj.event_type
    event_type_display.short_description = 'Event Type'

    # Optimized queryset for related fields
    def get_queryset(self, request):
        """Optimize the queryset to reduce database queries."""
        queryset = super().get_queryset(request)
        return queryset.select_related('location')


# Inline Witness --------------------------------------------------------------------------------------
# class WitnessInline(admin.TabularInline):
#     model = Witness
#     extra = 2
#     autocomplete_fields = ['testimony']
    



# Witness Admin ---------------------------------------------------------------------------------------------------
@admin.register(Witness)
class WitnessAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 're_published_at', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 're_published_at']
    search_fields = ['title', 'testimony__title']
    fieldsets = (
        ('Witness Details', {
            'fields': ('title', 'testimony', 're_published_at')
        }),
        ('Permissions & Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )
    filter_horizontal = ['testimony']
    actions = ['make_active', 'make_inactive']

    # Optimize the queryset
    def get_queryset(self, request):
        """Optimize the queryset for better performance."""
        queryset = super().get_queryset(request)
        return queryset.select_related('testimony')
    
    # Display a shortened version of the title if it's too long
    def title_summary(self, obj):
        """Displays a shortened version of the title."""
        return obj.title[:50] + "..." if len(obj.title) > 50 else obj.title
    title_summary.short_description = 'Title'



# Pray Admin --------------------------------------------------------------------------------------------------------------@admin.register(Pray)
class PrayAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'is_accepted', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at', 'is_accepted']
    search_fields = ['title', 'content']
    fieldsets = (
        ('Pray Details', {
            'fields': ('title', 'content', 'image', 'parent')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'updated_at', 'is_accepted', 'is_rejected', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Announcement Admin ------------------------------------------------------------------------------------------------------
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'created_at', 'to_date', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'created_at', 'to_date']
    search_fields = ['title', 'description']
    fieldsets = (
        ('Announcement Details', {
            'fields': ('title', 'description', 'image', 'meeting_type', 'url_link', 'link_sticker_text', 'location')
        }),
        ('Dates', {
            'fields': ('created_at', 'to_date')
        }),
        ('Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )


# Lesson Admin ------------------------------------------------------------------------------------------------------------
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'view', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'description']
    filter_horizontal = ['in_town_teachers']
    fieldsets = (
        ('Lesson Details', {
            'fields': ('title', 'season', 'episode', 'description', 'image', 'audio', 'video', 'parent')
        }),
        ('Teachers', {
            'fields': ('in_town_teachers', 'out_town_teachers')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'record_date', 'view', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Preach Admin ------------------------------------------------------------------------------------------------------------
@admin.register(Preach)
class PreachAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'view', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'out_town_preacher']
    fieldsets = (
        ('Preach Details', {
            'fields': ('title', 'in_town_preacher', 'out_town_preacher', 'image', 'video')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'view', 'is_active', 'is_hidden', 'is_restricted')
        })
    )
    

# Worship Admin -----------------------------------------------------------------------------------------------------------
@admin.register(Worship)
class WorshipAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'published_at', 'view', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'sermon', 'hymn_lyrics']
    filter_horizontal = ['in_town_leaders', 'worship_resources']
    fieldsets = (
        ('Worship Details', {
            'fields': ('title', 'season', 'episode', 'sermon', 'hymn_lyrics', 'image', 'audio', 'video', 'parent')
        }),
        ('Leaders', {
            'fields': ('in_town_leaders', 'out_town_leaders')
        }),
        ('Resources', {
            'fields': ('worship_resources',)
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'view', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Media Content Admin -----------------------------------------------------------------------------------------------------
@admin.register(MediaContent)
class MediaContentAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['title', 'content_type', 'published_at', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'published_at']
    search_fields = ['title', 'description']
    
    fieldsets = (
        ('Media Content Details', {
            'fields': ('content_type', 'title', 'description', 'file', 'link')
        }),
        ('Status & Dates', {
            'fields': ('published_at', 'is_active', 'is_hidden', 'is_restricted')
        })
    )


# Library Admin -----------------------------------------------------------------------------------------------------------
@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['book_name', 'author', 'published_date', 'downloaded', 'is_upcoming', 'is_downloadable', 'is_active']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'is_upcoming', 'is_downloadable', 'genre_type', 'published_date']
    search_fields = ['book_name', 'author', 'publisher_name', 'language', 'translation_language', 'translator']
    readonly_fields = ['downloaded']
    actions = ['make_active', 'make_inactive']
    fieldsets = (
        ('Book Details', {
            'fields': ('book_name', 'author', 'publisher_name', 'language', 'translation_language', 'translator', 'genre_type', 'image', 'pdf_file')
        }),
        ('Licensing & Sale', {
            'fields': ('license_type', 'sale_status', 'license_document')
        }),
        ('Release Info', {
            'fields': ('is_upcoming', 'is_downloadable', 'has_print_version')
        }),
        ('Status & Dates', {
            'fields': ('published_date', 'downloaded', 'is_active', 'is_hidden', 'is_restricted')
        })
    )

    def comment_summary(self, obj):
        """Displays a shortened version of the comment."""
        if obj.comments.exists():
            first_comment = obj.comments.first()
            return first_comment.comment[:50] + "..." if len(first_comment.comment) > 50 else first_comment.comment
        return "No comments"
    comment_summary.short_description = 'Comment Summary'
    
    def get_queryset(self, request):
        """Optimized query for related fields."""
        queryset = super().get_queryset(request)
        return queryset


# Mission Admin -----------------------------------------------------------------------------------------------------------
@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['mission_name', 'start_date', 'end_date', 'is_ongoing', 'location', 'is_active']
    list_filter = ['is_ongoing', 'is_active', 'is_hidden', 'start_date', 'end_date', 'location']
    search_fields = ['mission_name', 'description', 'contact_persons__username']
    actions = ['make_active', 'make_inactive']
    fieldsets = (
        ('Mission Details', {
            'fields': ('mission_name', 'description', 'image_or_video', 'location', 'contact_persons', 'start_date', 'end_date', 'is_ongoing')
        }),
        ('Funding Information', {
            'fields': ('funding_goal', 'raised_funds', 'funding_link')
        }),
        ('Volunteer & Report', {
            'fields': ('volunteer_opportunities', 'mission_report')
        }),
        ('Permissions & Status', {
            'fields': ('is_active', 'is_hidden', 'is_restricted')
        })
    )
    filter_horizontal = ['contact_persons']

    def comment_summary(self, obj):
        """Displays a shortened version of the comment."""
        if obj.comments.exists():
            first_comment = obj.comments.first()
            return first_comment.comment[:50] + "..." if len(first_comment.comment) > 50 else first_comment.comment
        return "No comments"
    comment_summary.short_description = 'Comment Summary'

    def get_queryset(self, request):
        """Optimize the queryset for better performance."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('contact_persons')


# Conference Admin -----------------------------------------------------------------------------------------------------------@admin.register(Conference)
class ConferenceAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['conference_name', 'conference_date', 'conference_end_date', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'conference_date', 'conference_end_date']
    search_fields = ['conference_name', 'description']
    date_hierarchy = 'conference_date'
    filter_horizontal = ['workshops', 'conference_resources']
    readonly_fields = ['slug']
    actions = ['make_inactive', 'make_active']
    fieldsets = (
        ('Conference Info', {
            'fields': ('conference_name', 'description', 'slug')
        }),
        ('Workshops & Resources', {
            'fields': ('workshops', 'conference_resources')
        }),
        ('Dates & Status', {
            'fields': ('conference_date', 'conference_time', 'conference_end_date', 'is_active', 'is_hidden', 'is_restricted')
        }),
    )


# Future Conference Admin -----------------------------------------------------------------------------------------------------------
@admin.register(FutureConference)
class FutureConferenceAdmin(admin.ModelAdmin, MarkActiveMixin):
    list_display = ['conference_name', 'conference_date', 'conference_end_date', 'registration_required', 'is_active', 'is_hidden', 'is_restricted']
    list_filter = ['is_active', 'is_hidden', 'is_restricted', 'conference_date', 'conference_end_date', 'registration_required']
    search_fields = ['conference_name', 'conference_description']
    date_hierarchy = 'conference_date'
    filter_horizontal = ['in_town_speakers', 'sponsors']
    readonly_fields = ['slug']
    actions = ['make_inactive', 'make_active']
    fieldsets = (
        ('Conference Info', {
            'fields': ('conference_name', 'conference_description', 'slug')
        }),
        ('Speakers & Sponsors', {
            'fields': ('in_town_speakers', 'out_town_speakers', 'sponsors')
        }),
        ('Registration & Location', {
            'fields': ('registration_required', 'delivery_type', 'conference_location', 'registration_link')
        }),
        ('Dates & Status', {
            'fields': ('conference_date', 'conference_time', 'conference_end_date', 'is_active', 'is_hidden', 'is_restricted')
        }),
    )


