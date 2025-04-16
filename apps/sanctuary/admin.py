from django.contrib import admin
from .models import SanctuaryRequest, SanctuaryReview, SanctuaryOutcome
from .helpers import notify_assigned_admin


# SANCTUARY REQUEST Admin --------------------------------------------------------------------
@admin.register(SanctuaryRequest)
class SanctuaryRequestAdmin(admin.ModelAdmin):
    list_display = ('request_type', 'requester', 'status', 'assigned_admin', 'request_date')
    list_filter = ('status', 'assigned_admin')
    search_fields = ('requester__id', 'reason')
    actions = ['assign_to_admin']

    # Action to assign an admin to the request
    def assign_to_admin(self, request, queryset):
        if request.user.is_staff:
            for obj in queryset:
                if obj.assigned_admin is None:
                    obj.assigned_admin = request.user
                    obj.save()
                    notify_assigned_admin(request.user, obj)
            self.message_user(request, "Selected requests have been assigned to you.")
        else:
            self.message_user(request, "Only admins can be assigned to requests.", level='error')

    # Custom filter to show unassigned requests
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if 'unassigned' in request.GET:
            return qs.filter(assigned_admin__isnull=True)
        return qs


# SANCTUARY REVIEW Admin --------------------------------------------------------------------
@admin.register(SanctuaryReview)
class SanctuaryReviewAdmin(admin.ModelAdmin):
    list_display = ('sanctuary_request', 'reviewer', 'review_status', 'review_date')
    list_filter = ('review_status', 'review_date')
    search_fields = ('sanctuary_request__requester__id', 'reviewer__id')
    ordering = ['-review_date']
    

# SANCTUARY OUTCOME Admin --------------------------------------------------------------------
@admin.register(SanctuaryOutcome)
class SanctuaryOutcomeAdmin(admin.ModelAdmin):
    list_display = ('outcome_status', 'completion_date', 'content_object')
    list_filter = ('outcome_status', 'completion_date')
    search_fields = ('content_object',)
    ordering = ['-completion_date']
