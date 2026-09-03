# apps/organizations/modules/church/services/__init__.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from .access import (
    ensure_church_module_access,
    ensure_church_permission,
    user_has_church_permission,
)
from .bootstrap import bootstrap_church_workspace
from .workspace import update_church_workspace
from .campuses import (
    archive_church_campus,
    create_church_campus,
    set_primary_church_campus,
    update_church_campus,
)
from .ministries import (
    add_church_ministry_participant,
    create_church_ministry,
    remove_church_ministry_participant,
    update_church_ministry,
)
from .leadership import assign_church_leadership, end_church_leadership
from .gatherings import (
    cancel_church_gathering,
    complete_church_gathering,
    create_church_gathering_occurrence,
    create_church_gathering_series,
    materialize_church_gathering_occurrences,
    update_church_gathering_series,
)
from .serving_teams import (
    add_church_serving_team_member,
    create_church_serving_team,
    remove_church_serving_team_member,
    update_church_serving_team,
)
from .service_plans import (
    add_church_service_plan_item,
    cancel_church_service_plan,
    complete_church_service_plan,
    create_church_service_plan,
    publish_church_service_plan,
    remove_church_service_plan_item,
    update_church_service_plan,
    update_church_service_plan_item,
)
from .serving_assignments import (
    cancel_church_serving_assignment,
    check_in_church_serving_assignment,
    check_out_church_serving_assignment,
    complete_church_serving_assignment,
    create_church_serving_assignment,
    respond_to_church_serving_assignment,
)
from .resources import (
    cancel_church_resource_reservation,
    complete_church_resource_reservation,
    create_church_resource,
    reserve_church_resource,
    update_church_resource,
)
from .attendance import (
    check_in_church_member,
    check_out_church_member,
    close_church_attendance_session,
    open_church_attendance_session,
    update_church_guest_counts,
)

__all__ = [
    "ensure_church_module_access",
    "ensure_church_permission",
    "user_has_church_permission",
    "bootstrap_church_workspace",
    "update_church_workspace",
    "archive_church_campus",
    "create_church_campus",
    "set_primary_church_campus",
    "update_church_campus",
    "add_church_ministry_participant",
    "create_church_ministry",
    "remove_church_ministry_participant",
    "update_church_ministry",
    "assign_church_leadership",
    "end_church_leadership",
    "cancel_church_gathering",
    "complete_church_gathering",
    "create_church_gathering_occurrence",
    "create_church_gathering_series",
    "materialize_church_gathering_occurrences",
    "update_church_gathering_series",
    "check_in_church_member",
    "check_out_church_member",
    "close_church_attendance_session",
    "open_church_attendance_session",
    "update_church_guest_counts",
    "add_church_serving_team_member",
    "create_church_serving_team",
    "remove_church_serving_team_member",
    "update_church_serving_team",
    "add_church_service_plan_item",
    "cancel_church_service_plan",
    "complete_church_service_plan",
    "create_church_service_plan",
    "publish_church_service_plan",
    "remove_church_service_plan_item",
    "update_church_service_plan",
    "update_church_service_plan_item",
    "cancel_church_serving_assignment",
    "check_in_church_serving_assignment",
    "check_out_church_serving_assignment",
    "complete_church_serving_assignment",
    "create_church_serving_assignment",
    "respond_to_church_serving_assignment",
    "cancel_church_resource_reservation",
    "complete_church_resource_reservation",
    "create_church_resource",
    "reserve_church_resource",
    "update_church_resource",
    "register_external_congregant",
    "register_guest_congregant",
    "register_member_congregant",
    "set_own_church_directory_visibility",
    "sync_member_congregant_official_membership",
    "update_church_congregant",
    "add_church_household_member",
    "create_church_household",
    "remove_church_household_member",
    "update_church_household",
    "can_view_pastoral_case",
    "can_view_pastoral_note",
    "ensure_pastoral_case_access",
    "ensure_pastoral_manage_permission",
    "user_has_direct_church_permission",
    "add_pastoral_care_note",
    "assign_pastoral_care_case",
    "close_pastoral_care_case",
    "create_pastoral_care_case",
    "end_pastoral_care_assignment",
    "get_pastoral_care_case_closure_summary",
    "get_pastoral_care_case_summary",
    "get_pastoral_care_contact_summary",
    "get_pastoral_care_note_body",
    "put_pastoral_care_case_on_hold",
    "record_pastoral_care_contact",
    "reopen_pastoral_care_case",
    "archive_church_teaching_content",
    "archive_church_teaching_series",
    "create_church_teaching_content",
    "create_church_teaching_series",
    "delete_draft_church_teaching_content",
    "publish_church_teaching_content",
    "update_church_teaching_content",
    "update_church_teaching_series",
]

from .congregation import (
    register_external_congregant,
    register_guest_congregant,
    register_member_congregant,
    set_own_church_directory_visibility,
    sync_member_congregant_official_membership,
    update_church_congregant,
)
from .households import (
    add_church_household_member,
    create_church_household,
    remove_church_household_member,
    update_church_household,
)
from .pastoral_access import (
    can_view_pastoral_case,
    can_view_pastoral_note,
    ensure_pastoral_case_access,
    ensure_pastoral_manage_permission,
    user_has_direct_church_permission,
)
from .pastoral_care import (
    add_pastoral_care_note,
    assign_pastoral_care_case,
    close_pastoral_care_case,
    create_pastoral_care_case,
    end_pastoral_care_assignment,
    get_pastoral_care_case_closure_summary,
    get_pastoral_care_case_summary,
    get_pastoral_care_contact_summary,
    get_pastoral_care_note_body,
    put_pastoral_care_case_on_hold,
    record_pastoral_care_contact,
    reopen_pastoral_care_case,
)

from .teaching import (
    archive_church_teaching_content,
    archive_church_teaching_series,
    create_church_teaching_content,
    create_church_teaching_series,
    delete_draft_church_teaching_content,
    publish_church_teaching_content,
    update_church_teaching_content,
    update_church_teaching_series,
)
