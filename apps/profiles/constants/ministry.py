# apps/profiles/constants/ministry.py


# Spiritual Ministry Choices -------------------------------------------------------------
# ===================== SENSITIVE =====================
PASTORING        = "pastoring"
TEACHING         = "teaching"
COUNSELING       = "counseling"
CHAPLAINCY       = "chaplaincy"
CHILDREN         = "children"
YOUTH            = "youth"
SMALLGROUPS      = "smallgroups"
BIBLESTUDY       = "biblestudy"
DISCIPLESHIP     = "discipleship"
MENTORING        = "mentoring"
SHEPHERDING      = "shepherding"
MARRIAGE         = "marriage"
GRIEFCARE        = "griefcare"
HOSPITAL         = "hospital"
PRISON           = "prison"
VISITATION       = "visitation"
REFUGEE          = "refugee"
SENIORS          = "seniors"
SECURITY         = "security"
RECONCILIATION   = "reconciliation"
PEACEMAKING      = "peacemaking"
LEADERSHIP       = "leadership"
TUTORING         = "tutoring"
FINANCE          = "finance"
GOVERNANCE       = "governance"

SENSITIVE_MINISTRY_CHOICES = [
    (PASTORING, "Pastoring"),
    (TEACHING, "Teaching"),
    (COUNSELING, "Counseling"),
    (CHAPLAINCY, "Chaplaincy"),
    (CHILDREN, "Children"),
    (YOUTH, "Youth"),
    (SMALLGROUPS, "SmallGroups"),
    (BIBLESTUDY, "BibleStudy"),
    (DISCIPLESHIP, "Discipleship"),
    (MENTORING, "Mentoring"),
    (SHEPHERDING, "Shepherding"),
    (MARRIAGE, "Marriage"),
    (GRIEFCARE, "GriefCare"),
    (HOSPITAL, "Hospital"),
    (PRISON, "Prison"),
    (VISITATION, "Visitation"),
    (REFUGEE, "Refugee"),
    (SENIORS, "Seniors"),
    (SECURITY, "Security"),
    (RECONCILIATION, "Reconciliation"),
    (PEACEMAKING, "Peacemaking"),
    (LEADERSHIP, "Leadership"),
    (TUTORING, "Tutoring"),
    (FINANCE, "Finance"),
    (GOVERNANCE, "Governance"),
]

# ===================== STANDARD (بدون مدرک) =====================
ADMINISTRATION   = "administration"
HOSPITALITY      = "hospitality"
GREETER          = "greeter"
WELCOME          = "welcome"
NEWCOMER         = "newcomer"
OUTREACH         = "outreach"
EVANGELISM       = "evangelism"
MISSIONS         = "missions"
PRAYER           = "prayer"
INTERCESSION     = "intercession"
WORSHIP          = "worship"
MUSIC            = "music"
CHOIR            = "choir"
BAND             = "band"
AUDIO            = "audio"
VIDEO            = "video"
SOUND            = "sound"
LIGHTING         = "lighting"
LIVESTREAM       = "livestream"
PRODUCTION       = "production"
MEDIA            = "media"
PHOTOGRAPHY      = "photography"
DESIGN           = "design"
IT               = "it"
COMMUNICATIONS   = "communications"
EVENTS           = "events"
LOGISTICS        = "logistics"
SETUP            = "setup"
FACILITIES       = "facilities"
MAINTENANCE      = "maintenance"
TRANSPORT        = "transport"
TRANSLATION      = "translation"
STEWARDSHIP      = "stewardship"
TRAINING         = "training"
BENEVOLENCE      = "benevolence"

STANDARD_MINISTRY_CHOICES = [
    (ADMINISTRATION, "Administration"),
    (HOSPITALITY, "Hospitality"),
    (GREETER, "Greeter"),
    (WELCOME, "Welcome"),
    (NEWCOMER, "Newcomer"),
    (OUTREACH, "Outreach"),
    (EVANGELISM, "Evangelism"),
    (MISSIONS, "Missions"),
    (PRAYER, "Prayer"),
    (INTERCESSION, "Intercession"),
    (WORSHIP, "Worship"),
    (MUSIC, "Music"),
    (CHOIR, "Choir"),
    (BAND, "Band"),
    (AUDIO, "Audio"),
    (VIDEO, "Video"),
    (SOUND, "Sound"),
    (LIGHTING, "Lighting"),
    (LIVESTREAM, "Livestream"),
    (PRODUCTION, "Production"),
    (MEDIA, "Media"),
    (PHOTOGRAPHY, "Photography"),
    (DESIGN, "Design"),
    (IT, "IT"),
    (COMMUNICATIONS, "Communications"),
    (EVENTS, "Events"),
    (LOGISTICS, "Logistics"),
    (SETUP, "Setup"),
    (FACILITIES, "Facilities"),
    (MAINTENANCE, "Maintenance"),
    (TRANSPORT, "Transport"),
    (TRANSLATION, "Translation"),
    (STEWARDSHIP, "Stewardship"),
    (TRAINING, "Training"),
    (BENEVOLENCE, "Benevolence"),
]

# === فهرست نهایی برای choices فیلد مدل (همهٔ آیتم‌ها) ===
SPIRITUAL_MINISTRY_CHOICES = SENSITIVE_MINISTRY_CHOICES + STANDARD_MINISTRY_CHOICES


# ----------------------------------------------------------
from django.utils.translation import gettext_lazy as _
STANDARD_MINISTRY_CHOICES = [
    ("administration", _("Administration")),
    ("hospitality",    _("Hospitality")),
    ("greeter",        _("Greeter")),
    ("welcome",        _("Welcome")),
    ("newcomer",       _("Newcomer")),
    ("outreach",       _("Outreach")),
    ("evangelism",     _("Evangelism")),
    ("missions",       _("Missions")),
    ("prayer",         _("Prayer")),
    ("intercession",   _("Intercession")),
    ("worship",        _("Worship")),
    ("music",          _("Music")),
    ("choir",          _("Choir")),
    ("band",           _("Band")),
    ("audio",          _("Audio")),
    ("video",          _("Video")),
    ("sound",          _("Sound")),
    ("lighting",       _("Lighting")),
    ("livestream",     _("Livestream")),
    ("production",     _("Production")),
    ("media",          _("Media")),
    ("photography",    _("Photography")),
    ("design",         _("Design")),
    ("it",             _("IT")),            # keep acronym
    ("communications", _("Communications")),
    ("events",         _("Events")),
    ("logistics",      _("Logistics")),
    ("setup",          _("Setup")),
    ("facilities",     _("Facilities")),
    ("maintenance",    _("Maintenance")),
    ("transport",      _("Transport")),
    ("translation",    _("Translation")),
    ("stewardship",    _("Stewardship")),
    ("training",       _("Training")),
    ("benevolence",    _("Benevolence")),
]

