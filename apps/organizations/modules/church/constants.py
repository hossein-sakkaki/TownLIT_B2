# apps/organizations/modules/church/constants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.db import models


class ChurchCampusStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class ChurchMinistryStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class ChurchMinistryParticipationRole(models.TextChoices):
    PARTICIPANT = "participant", "Participant"
    VOLUNTEER = "volunteer", "Volunteer"
    LEADER = "leader", "Leader"


class ChurchMinistryMembershipStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"


class ChurchLeadershipPositionType(models.TextChoices):
    SENIOR_PASTOR = "senior_pastor", "Senior Pastor"
    ASSOCIATE_PASTOR = "associate_pastor", "Associate Pastor"
    PASTOR = "pastor", "Pastor"
    ELDER = "elder", "Elder"
    DEACON = "deacon", "Deacon"
    MINISTRY_LEADER = "ministry_leader", "Ministry Leader"
    WORSHIP_LEADER = "worship_leader", "Worship Leader"
    CHURCH_ADMINISTRATOR = "church_administrator", "Church Administrator"
    OTHER = "other", "Other"


class ChurchLeadershipAssignmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"


class ChurchGatheringType(models.TextChoices):
    SUNDAY_WORSHIP = "sunday_worship", "Sunday Worship"
    WORSHIP_SERVICE = "worship_service", "Worship Service"
    COMMUNION = "communion", "Communion Service"
    PRAYER_MEETING = "prayer_meeting", "Prayer Meeting"
    FELLOWSHIP = "fellowship", "Fellowship Gathering"
    BAPTISM_SERVICE = "baptism_service", "Baptism Service"
    MEMBERSHIP_MEETING = "membership_meeting", "Membership Meeting"
    SPECIAL_SERVICE = "special_service", "Special Service"
    OTHER = "other", "Other"


class ChurchGatheringSeriesStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class ChurchRecurrenceFrequency(models.TextChoices):
    WEEKLY = "weekly", "Weekly"
    BIWEEKLY = "biweekly", "Every Two Weeks"
    MONTHLY = "monthly", "Monthly"


class ChurchMonthlyWeek(models.TextChoices):
    FIRST = "first", "First"
    SECOND = "second", "Second"
    THIRD = "third", "Third"
    FOURTH = "fourth", "Fourth"
    LAST = "last", "Last"


class ChurchGatheringOccurrenceStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    CANCELED = "canceled", "Canceled"
    COMPLETED = "completed", "Completed"


class ChurchGatheringOccurrenceSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    SERIES = "series", "Recurring Series"


class ChurchAttendanceSessionStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class ChurchAttendanceSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    SELF_CHECK_IN = "self_check_in", "Self Check-in"
    KIOSK = "kiosk", "Kiosk"
    IMPORTED = "imported", "Imported"


class ChurchAttendancePresence(models.TextChoices):
    PRESENT = "present", "Present"
    LATE = "late", "Late"
    SERVING = "serving", "Serving"
    ONLINE = "online", "Online"


class ChurchServingTeamStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class ChurchServingTeamMembershipStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"


class ChurchServicePlanStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    COMPLETED = "completed", "Completed"
    CANCELED = "canceled", "Canceled"


class ChurchServicePlanItemType(models.TextChoices):
    OPENING = "opening", "Opening"
    WORSHIP = "worship", "Worship"
    PRAYER = "prayer", "Prayer"
    SCRIPTURE = "scripture", "Scripture"
    SERMON = "sermon", "Sermon"
    COMMUNION = "communion", "Communion"
    OFFERING = "offering", "Offering"
    ANNOUNCEMENT = "announcement", "Announcement"
    MINISTRY_FEATURE = "ministry_feature", "Ministry Feature"
    RESPONSE = "response", "Response"
    TRANSITION = "transition", "Transition"
    CLOSING = "closing", "Closing"
    CUSTOM = "custom", "Custom"


class ChurchServingAssignmentStatus(models.TextChoices):
    INVITED = "invited", "Invited"
    CONFIRMED = "confirmed", "Confirmed"
    DECLINED = "declined", "Declined"
    CANCELED = "canceled", "Canceled"
    COMPLETED = "completed", "Completed"


class ChurchResourceType(models.TextChoices):
    ROOM = "room", "Room"
    EQUIPMENT = "equipment", "Equipment"
    VEHICLE = "vehicle", "Vehicle"
    OTHER = "other", "Other"


class ChurchResourceStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class ChurchResourceReservationStatus(models.TextChoices):
    RESERVED = "reserved", "Reserved"
    CANCELED = "canceled", "Canceled"
    COMPLETED = "completed", "Completed"


class ChurchCongregantStatus(models.TextChoices):
    NEWCOMER = "newcomer", "Newcomer"
    ATTENDEE = "attendee", "Attendee"
    REGULAR = "regular", "Regular Attendee"
    INACTIVE = "inactive", "Inactive"


class ChurchCongregantSource(models.TextChoices):
    STAFF_CREATED = "staff_created", "Staff Created"
    SELF_REGISTERED = "self_registered", "Self Registered"
    ATTENDANCE = "attendance", "Attendance"
    IMPORTED = "imported", "Imported"


class ChurchDirectoryVisibility(models.TextChoices):
    STAFF_ONLY = "staff_only", "Authorized Church Staff Only"
    ORGANIZATION_MEMBERS = "organization_members", "Organization Members"


class ChurchHouseholdStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class ChurchHouseholdRelationship(models.TextChoices):
    HEAD = "head", "Household Head"
    SPOUSE = "spouse", "Spouse"
    ADULT = "adult", "Adult Household Member"
    DEPENDENT = "dependent", "Dependent"
    OTHER = "other", "Other"


class ChurchHouseholdMembershipStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"


class ChurchPastoralCareCaseStatus(models.TextChoices):
    OPEN = "open", "Open"
    ON_HOLD = "on_hold", "On Hold"
    CLOSED = "closed", "Closed"


class ChurchPastoralCareSensitivity(models.TextChoices):
    STANDARD = "standard", "Standard"
    RESTRICTED = "restricted", "Restricted"
    HIGHLY_CONFIDENTIAL = "highly_confidential", "Highly Confidential"


class ChurchPastoralCareCategory(models.TextChoices):
    GENERAL = "general", "General Pastoral Care"
    NEWCOMER_FOLLOW_UP = "newcomer_follow_up", "Newcomer Follow-up"
    SPIRITUAL_CARE = "spiritual_care", "Spiritual Care"
    BEREAVEMENT = "bereavement", "Bereavement"
    MARRIAGE_FAMILY = "marriage_family", "Marriage / Family"
    ILLNESS_SUPPORT = "illness_support", "Illness Support"
    CRISIS_SUPPORT = "crisis_support", "Crisis Support"
    OTHER = "other", "Other"


class ChurchPastoralCareAssignmentRole(models.TextChoices):
    PRIMARY = "primary", "Primary Care Lead"
    SUPPORT = "support", "Support"


class ChurchPastoralCareAssignmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"


class ChurchPastoralCareNoteType(models.TextChoices):
    GENERAL = "general", "General"
    PRAYER = "prayer", "Prayer"
    FOLLOW_UP = "follow_up", "Follow-up"
    VISIT = "visit", "Visit"
    INTERNAL = "internal", "Internal"


class ChurchPastoralCareNoteVisibility(models.TextChoices):
    CASE_TEAM = "case_team", "Assigned Care Team"
    PASTORAL_LEADERS = "pastoral_leaders", "Pastoral Leaders"


class ChurchPastoralCareContactType(models.TextChoices):
    IN_PERSON = "in_person", "In Person"
    PHONE = "phone", "Phone"
    MESSAGE = "message", "Message"
    VIDEO = "video", "Video"
    HOME_VISIT = "home_visit", "Home Visit"
    HOSPITAL_VISIT = "hospital_visit", "Hospital Visit"
    OTHER = "other", "Other"


class ChurchTeachingSeriesStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class ChurchTeachingContentType(models.TextChoices):
    SERMON = "sermon", "Sermon"
    BIBLE_TEACHING = "bible_teaching", "Bible Teaching"
    DEVOTIONAL = "devotional", "Devotional"
    TRAINING = "training", "Training"


class ChurchTeachingFormat(models.TextChoices):
    WRITTEN = "written", "Written"
    VIDEO = "video", "Video"


class ChurchTeachingStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class ChurchTeachingAudience(models.TextChoices):
    PUBLIC = "public", "Public"
    ORGANIZATION_MEMBERS = "organization_members", "Organization Members"
    INTERNAL = "internal", "Authorized Church Staff"


class ChurchPermissionKey:
    MANAGE_WORKSPACE = "organizations.modules.church.workspace.manage"
    MANAGE_CAMPUSES = "organizations.modules.church.campuses.manage"
    MANAGE_MINISTRIES = "organizations.modules.church.ministries.manage"
    MANAGE_LEADERSHIP = "organizations.modules.church.leadership.manage"
    MANAGE_GATHERINGS = "organizations.modules.church.gatherings.manage"
    VIEW_ATTENDANCE = "organizations.modules.church.attendance.view"
    MANAGE_ATTENDANCE = "organizations.modules.church.attendance.manage"
    MANAGE_SERVING_TEAMS = "organizations.modules.church.serving_teams.manage"
    MANAGE_SERVICE_PLANS = "organizations.modules.church.service_plans.manage"
    MANAGE_SERVING_ASSIGNMENTS = "organizations.modules.church.serving_assignments.manage"
    MANAGE_RESOURCES = "organizations.modules.church.resources.manage"
    VIEW_CONGREGATION_DIRECTORY = "organizations.modules.church.congregation.view"
    MANAGE_CONGREGATION_DIRECTORY = "organizations.modules.church.congregation.manage"
    MANAGE_HOUSEHOLDS = "organizations.modules.church.households.manage"
    VIEW_PASTORAL_CARE = "organizations.modules.church.pastoral_care.view"
    MANAGE_PASTORAL_CARE = "organizations.modules.church.pastoral_care.manage"
    VIEW_CONFIDENTIAL_PASTORAL_CARE = "organizations.modules.church.pastoral_care.confidential.view"
    VIEW_TEACHING = "organizations.modules.church.teaching.view"
    MANAGE_TEACHING = "organizations.modules.church.teaching.manage"
    PUBLISH_TEACHING = "organizations.modules.church.teaching.publish"


CHURCH_PERMISSION_DEFINITIONS = (
    (
        ChurchPermissionKey.MANAGE_WORKSPACE,
        "Manage Church Workspace",
        "church",
        "Manage Church & Congregational Life workspace settings.",
    ),
    (
        ChurchPermissionKey.MANAGE_CAMPUSES,
        "Manage Church Campuses",
        "church",
        "Manage church campuses and physical congregation locations.",
    ),
    (
        ChurchPermissionKey.MANAGE_MINISTRIES,
        "Manage Church Ministries",
        "church",
        "Manage church ministries and ministry participation.",
    ),
    (
        ChurchPermissionKey.MANAGE_LEADERSHIP,
        "Manage Church Leadership",
        "church",
        "Manage church leadership directory assignments.",
    ),
    (
        ChurchPermissionKey.MANAGE_GATHERINGS,
        "Manage Church Gatherings",
        "church",
        "Manage church gathering schedules and occurrences.",
    ),
    (
        ChurchPermissionKey.VIEW_ATTENDANCE,
        "View Church Attendance",
        "church",
        "View member attendance records and aggregate attendance data.",
    ),
    (
        ChurchPermissionKey.MANAGE_ATTENDANCE,
        "Manage Church Attendance",
        "church",
        "Open, record, and close church attendance sessions.",
    ),
    (
        ChurchPermissionKey.MANAGE_SERVING_TEAMS,
        "Manage Church Serving Teams",
        "church",
        "Manage persistent serving teams and their official member rosters.",
    ),
    (
        ChurchPermissionKey.MANAGE_SERVICE_PLANS,
        "Manage Church Service Plans",
        "church",
        "Build and publish operational run-of-show plans for church gatherings.",
    ),
    (
        ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
        "Manage Church Serving Assignments",
        "church",
        "Schedule and coordinate official members serving in church gatherings.",
    ),
    (
        ChurchPermissionKey.MANAGE_RESOURCES,
        "Manage Church Resources",
        "church",
        "Manage rooms, equipment, vehicles, and gathering reservations.",
    ),
    (
        ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
        "View Church Congregation Directory",
        "church",
        "View the internal congregation directory within authorized Church operations.",
    ),
    (
        ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
        "Manage Church Congregation Directory",
        "church",
        "Manage congregation records without duplicating account contact credentials.",
    ),
    (
        ChurchPermissionKey.MANAGE_HOUSEHOLDS,
        "Manage Church Households",
        "church",
        "Manage congregation household groupings without protected minor profile data.",
    ),
    (
        ChurchPermissionKey.VIEW_PASTORAL_CARE,
        "View Church Pastoral Care",
        "church",
        "View standard pastoral care cases through the confidential care workflow.",
    ),
    (
        ChurchPermissionKey.MANAGE_PASTORAL_CARE,
        "Manage Church Pastoral Care",
        "church",
        "Create, assign, transition, and record pastoral care cases.",
    ),
    (
        ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
        "View Confidential Church Pastoral Care",
        "church",
        "View restricted pastoral care records without inheriting access from generic module administration.",
    ),
    (
        ChurchPermissionKey.VIEW_TEACHING,
        "View Church Teaching",
        "church",
        "View Church teaching and sermon content available to authorized Church staff.",
    ),
    (
        ChurchPermissionKey.MANAGE_TEACHING,
        "Manage Church Teaching",
        "church",
        "Create and manage Church teaching series, sermons, and teaching drafts.",
    ),
    (
        ChurchPermissionKey.PUBLISH_TEACHING,
        "Publish Church Teaching",
        "church",
        "Publish and archive Church teaching and sermon content.",
    ),
)


class ChurchRoleKey:
    ADMINISTRATOR = "church_administrator"
    PASTORAL_LEADER = "church_pastoral_leader"
    CAMPUS_MANAGER = "church_campus_manager"
    MINISTRY_MANAGER = "church_ministry_manager"
    SERVICES_MANAGER = "church_services_manager"
    ATTENDANCE_MANAGER = "church_attendance_manager"
    SERVING_COORDINATOR = "church_serving_coordinator"
    RESOURCE_MANAGER = "church_resource_manager"
    CONGREGATION_MANAGER = "church_congregation_manager"
    PASTORAL_CARE_MANAGER = "church_pastoral_care_manager"
    TEACHING_MANAGER = "church_teaching_manager"


CHURCH_ROLE_DEFINITIONS = (
    {
        "key": ChurchRoleKey.ADMINISTRATOR,
        "name": "Church Administrator",
        "description": "Full operational administration for the Church module.",
        "priority": 650,
        "permissions": tuple(
            item[0] for item in CHURCH_PERMISSION_DEFINITIONS
        ),
    },
    {
        "key": ChurchRoleKey.PASTORAL_LEADER,
        "name": "Pastoral Leader",
        "description": "Pastoral leadership access across church life operations.",
        "priority": 620,
        "permissions": (
            ChurchPermissionKey.MANAGE_WORKSPACE,
            ChurchPermissionKey.MANAGE_MINISTRIES,
            ChurchPermissionKey.MANAGE_LEADERSHIP,
            ChurchPermissionKey.MANAGE_GATHERINGS,
            ChurchPermissionKey.MANAGE_SERVICE_PLANS,
            ChurchPermissionKey.VIEW_ATTENDANCE,
            ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
            ChurchPermissionKey.VIEW_PASTORAL_CARE,
            ChurchPermissionKey.MANAGE_PASTORAL_CARE,
            ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
            ChurchPermissionKey.VIEW_TEACHING,
            ChurchPermissionKey.MANAGE_TEACHING,
            ChurchPermissionKey.PUBLISH_TEACHING,
        ),
    },
    {
        "key": ChurchRoleKey.CAMPUS_MANAGER,
        "name": "Campus Manager",
        "description": "Manages campus-level church operations and service delivery.",
        "priority": 560,
        "permissions": (
            ChurchPermissionKey.MANAGE_CAMPUSES,
            ChurchPermissionKey.MANAGE_MINISTRIES,
            ChurchPermissionKey.MANAGE_GATHERINGS,
            ChurchPermissionKey.VIEW_ATTENDANCE,
            ChurchPermissionKey.MANAGE_ATTENDANCE,
            ChurchPermissionKey.MANAGE_SERVING_TEAMS,
            ChurchPermissionKey.MANAGE_SERVICE_PLANS,
            ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
            ChurchPermissionKey.MANAGE_RESOURCES,
            ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
            ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
            ChurchPermissionKey.MANAGE_HOUSEHOLDS,
            ChurchPermissionKey.VIEW_TEACHING,
            ChurchPermissionKey.MANAGE_TEACHING,
            ChurchPermissionKey.PUBLISH_TEACHING,
        ),
    },
    {
        "key": ChurchRoleKey.MINISTRY_MANAGER,
        "name": "Church Ministry Manager",
        "description": "Manages ministries, ministry participation, and serving teams.",
        "priority": 520,
        "permissions": (
            ChurchPermissionKey.MANAGE_MINISTRIES,
            ChurchPermissionKey.MANAGE_LEADERSHIP,
            ChurchPermissionKey.MANAGE_SERVING_TEAMS,
            ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
        ),
    },
    {
        "key": ChurchRoleKey.SERVICES_MANAGER,
        "name": "Church Services Manager",
        "description": "Plans gatherings and coordinates service execution.",
        "priority": 520,
        "permissions": (
            ChurchPermissionKey.MANAGE_GATHERINGS,
            ChurchPermissionKey.VIEW_ATTENDANCE,
            ChurchPermissionKey.MANAGE_SERVICE_PLANS,
            ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
            ChurchPermissionKey.VIEW_TEACHING,
        ),
    },
    {
        "key": ChurchRoleKey.ATTENDANCE_MANAGER,
        "name": "Church Attendance Manager",
        "description": "Manages attendance sessions and attendance records.",
        "priority": 500,
        "permissions": (
            ChurchPermissionKey.VIEW_ATTENDANCE,
            ChurchPermissionKey.MANAGE_ATTENDANCE,
        ),
    },
    {
        "key": ChurchRoleKey.SERVING_COORDINATOR,
        "name": "Church Serving Coordinator",
        "description": "Manages serving teams and volunteer scheduling for gatherings.",
        "priority": 510,
        "permissions": (
            ChurchPermissionKey.MANAGE_SERVING_TEAMS,
            ChurchPermissionKey.MANAGE_SERVICE_PLANS,
            ChurchPermissionKey.MANAGE_SERVING_ASSIGNMENTS,
        ),
    },
    {
        "key": ChurchRoleKey.RESOURCE_MANAGER,
        "name": "Church Resource Manager",
        "description": "Manages reservable church rooms, equipment, and vehicles.",
        "priority": 490,
        "permissions": (
            ChurchPermissionKey.MANAGE_RESOURCES,
        ),
    },
    {
        "key": ChurchRoleKey.CONGREGATION_MANAGER,
        "name": "Church Congregation Manager",
        "description": "Manages internal congregation and household records without pastoral case access.",
        "priority": 505,
        "permissions": (
            ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
            ChurchPermissionKey.MANAGE_CONGREGATION_DIRECTORY,
            ChurchPermissionKey.MANAGE_HOUSEHOLDS,
        ),
    },
    {
        "key": ChurchRoleKey.PASTORAL_CARE_MANAGER,
        "name": "Church Pastoral Care Manager",
        "description": "Manages confidential pastoral care workflows without general Church administration rights.",
        "priority": 610,
        "permissions": (
            ChurchPermissionKey.VIEW_CONGREGATION_DIRECTORY,
            ChurchPermissionKey.VIEW_PASTORAL_CARE,
            ChurchPermissionKey.MANAGE_PASTORAL_CARE,
            ChurchPermissionKey.VIEW_CONFIDENTIAL_PASTORAL_CARE,
        ),
    },
    {
        "key": ChurchRoleKey.TEACHING_MANAGER,
        "name": "Church Teaching Manager",
        "description": "Manages and publishes Church sermons and teaching resources.",
        "priority": 530,
        "permissions": (
            ChurchPermissionKey.VIEW_TEACHING,
            ChurchPermissionKey.MANAGE_TEACHING,
            ChurchPermissionKey.PUBLISH_TEACHING,
        ),
    },
)


class ChurchAuditEvent(models.TextChoices):
    WORKSPACE_INITIALIZED = "workspace_initialized", "Workspace Initialized"
    WORKSPACE_UPDATED = "workspace_updated", "Workspace Updated"
    CAMPUS_CREATED = "campus_created", "Campus Created"
    CAMPUS_UPDATED = "campus_updated", "Campus Updated"
    CAMPUS_PRIMARY_CHANGED = "campus_primary_changed", "Primary Campus Changed"
    CAMPUS_ARCHIVED = "campus_archived", "Campus Archived"
    MINISTRY_CREATED = "ministry_created", "Ministry Created"
    MINISTRY_UPDATED = "ministry_updated", "Ministry Updated"
    MINISTRY_PARTICIPANT_ADDED = "ministry_participant_added", "Ministry Participant Added"
    MINISTRY_PARTICIPANT_REMOVED = "ministry_participant_removed", "Ministry Participant Removed"
    LEADERSHIP_ASSIGNED = "leadership_assigned", "Leadership Assigned"
    LEADERSHIP_ENDED = "leadership_ended", "Leadership Ended"
    GATHERING_SERIES_CREATED = "gathering_series_created", "Gathering Series Created"
    GATHERING_SERIES_UPDATED = "gathering_series_updated", "Gathering Series Updated"
    GATHERING_CREATED = "gathering_created", "Gathering Created"
    GATHERING_CANCELED = "gathering_canceled", "Gathering Canceled"
    GATHERING_COMPLETED = "gathering_completed", "Gathering Completed"
    ATTENDANCE_OPENED = "attendance_opened", "Attendance Opened"
    ATTENDANCE_CHECKED_IN = "attendance_checked_in", "Attendance Checked In"
    ATTENDANCE_CHECKED_OUT = "attendance_checked_out", "Attendance Checked Out"
    ATTENDANCE_GUEST_COUNTS_UPDATED = "attendance_guest_counts_updated", "Guest Counts Updated"
    ATTENDANCE_CLOSED = "attendance_closed", "Attendance Closed"
    SERVING_TEAM_CREATED = "serving_team_created", "Serving Team Created"
    SERVING_TEAM_UPDATED = "serving_team_updated", "Serving Team Updated"
    SERVING_TEAM_MEMBER_ADDED = "serving_team_member_added", "Serving Team Member Added"
    SERVING_TEAM_MEMBER_REMOVED = "serving_team_member_removed", "Serving Team Member Removed"
    SERVICE_PLAN_CREATED = "service_plan_created", "Service Plan Created"
    SERVICE_PLAN_UPDATED = "service_plan_updated", "Service Plan Updated"
    SERVICE_PLAN_PUBLISHED = "service_plan_published", "Service Plan Published"
    SERVICE_PLAN_COMPLETED = "service_plan_completed", "Service Plan Completed"
    SERVICE_PLAN_CANCELED = "service_plan_canceled", "Service Plan Canceled"
    SERVICE_PLAN_ITEM_ADDED = "service_plan_item_added", "Service Plan Item Added"
    SERVICE_PLAN_ITEM_UPDATED = "service_plan_item_updated", "Service Plan Item Updated"
    SERVICE_PLAN_ITEM_REMOVED = "service_plan_item_removed", "Service Plan Item Removed"
    SERVING_ASSIGNMENT_CREATED = "serving_assignment_created", "Serving Assignment Created"
    SERVING_ASSIGNMENT_RESPONDED = "serving_assignment_responded", "Serving Assignment Responded"
    SERVING_ASSIGNMENT_CHECKED_IN = "serving_assignment_checked_in", "Serving Assignment Checked In"
    SERVING_ASSIGNMENT_CHECKED_OUT = "serving_assignment_checked_out", "Serving Assignment Checked Out"
    SERVING_ASSIGNMENT_CANCELED = "serving_assignment_canceled", "Serving Assignment Canceled"
    SERVING_ASSIGNMENT_COMPLETED = "serving_assignment_completed", "Serving Assignment Completed"
    RESOURCE_CREATED = "resource_created", "Resource Created"
    RESOURCE_UPDATED = "resource_updated", "Resource Updated"
    RESOURCE_RESERVED = "resource_reserved", "Resource Reserved"
    RESOURCE_RESERVATION_CANCELED = "resource_reservation_canceled", "Resource Reservation Canceled"
    RESOURCE_RESERVATION_COMPLETED = "resource_reservation_completed", "Resource Reservation Completed"
    CONGREGANT_REGISTERED = "congregant_registered", "Congregant Registered"
    CONGREGANT_UPDATED = "congregant_updated", "Congregant Updated"
    CONGREGANT_DIRECTORY_VISIBILITY_CHANGED = "congregant_directory_visibility_changed", "Congregant Directory Visibility Changed"
    HOUSEHOLD_CREATED = "household_created", "Household Created"
    HOUSEHOLD_UPDATED = "household_updated", "Household Updated"
    HOUSEHOLD_MEMBER_ADDED = "household_member_added", "Household Member Added"
    HOUSEHOLD_MEMBER_REMOVED = "household_member_removed", "Household Member Removed"
    PASTORAL_CASE_CREATED = "pastoral_case_created", "Pastoral Care Case Created"
    PASTORAL_CASE_UPDATED = "pastoral_case_updated", "Pastoral Care Case Updated"
    PASTORAL_CASE_ASSIGNED = "pastoral_case_assigned", "Pastoral Care Case Assigned"
    PASTORAL_CASE_UNASSIGNED = "pastoral_case_unassigned", "Pastoral Care Case Unassigned"
    PASTORAL_CASE_ON_HOLD = "pastoral_case_on_hold", "Pastoral Care Case On Hold"
    PASTORAL_CASE_REOPENED = "pastoral_case_reopened", "Pastoral Care Case Reopened"
    PASTORAL_CASE_CLOSED = "pastoral_case_closed", "Pastoral Care Case Closed"
    PASTORAL_NOTE_ADDED = "pastoral_note_added", "Pastoral Care Note Added"
    PASTORAL_CONTACT_RECORDED = "pastoral_contact_recorded", "Pastoral Care Contact Recorded"
    TEACHING_SERIES_CREATED = "teaching_series_created", "Teaching Series Created"
    TEACHING_SERIES_UPDATED = "teaching_series_updated", "Teaching Series Updated"
    TEACHING_SERIES_ARCHIVED = "teaching_series_archived", "Teaching Series Archived"
    TEACHING_CONTENT_CREATED = "teaching_content_created", "Teaching Content Created"
    TEACHING_CONTENT_UPDATED = "teaching_content_updated", "Teaching Content Updated"
    TEACHING_CONTENT_PUBLISHED = "teaching_content_published", "Teaching Content Published"
    TEACHING_CONTENT_ARCHIVED = "teaching_content_archived", "Teaching Content Archived"
    TEACHING_CONTENT_DELETED = "teaching_content_deleted", "Teaching Content Deleted"
