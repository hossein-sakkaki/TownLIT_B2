







# COLLABORATION TYPE Choices --------------------------------------------------------------
CONTENT = 'content'
WRITING = 'writing'
TRANSLATION = 'translation'
VIDEO = 'video'
DESIGN = 'design'
DEVELOPMENT = 'development'
OUTREACH = 'outreach'
PRAYER = 'prayer'
ADMIN = 'admin'
FINANCIAL = 'financial'
MENTORING = 'mentoring'
TEACHING = 'teaching'
OTHER = 'other'

COLLABORATION_TYPE_CHOICES = [
    (CONTENT, 'Content Creation'),
    (WRITING, 'Writing / Editing / Blogging'),
    (TRANSLATION, 'Translation'),
    (VIDEO, 'Video Editing / Production'),
    (DESIGN, 'Design & UI'),
    (DEVELOPMENT, 'Development / Programming'),
    (OUTREACH, 'Community Outreach'),
    (PRAYER, 'Prayer Ministry'),
    (MENTORING, 'Mentoring / Discipleship Support'),
    (TEACHING, 'Teaching / Bible Study Facilitation'),
    (ADMIN, 'Administrative Help'),
    (FINANCIAL, 'Financial Contribution / Support'),
    (OTHER, 'Other'),
]


# COLLABORATION MODE Choices 
ONLINE = 'online'
ONSITE = 'onsite'
HYBRID = 'hybrid'

COLLABORATION_MODE_CHOICES = [
    (ONLINE, 'Online'),
    (ONSITE, 'On-site'),
    (HYBRID, 'Hybrid'),
]

# COLLABORATION STATUS Choices 
COLLABORATION_STATUS_NEW = 'new'
COLLABORATION_STATUS_REVIEWED = 'reviewed'
COLLABORATION_STATUS_CONTACTED = 'contacted'
COLLABORATION_STATUS_CLOSED = 'closed'

COLLABORATION_STATUS_CHOICES = [
    (COLLABORATION_STATUS_NEW, 'New'),
    (COLLABORATION_STATUS_REVIEWED, 'Reviewed'),
    (COLLABORATION_STATUS_CONTACTED, 'Contacted'),
    (COLLABORATION_STATUS_CLOSED, 'Closed'),
]


# Job Application Statuses
JOB_STATUS_NEW = 'new'
JOB_STATUS_REVIEWED = 'reviewed'
JOB_STATUS_INTERVIEW = 'interview'
JOB_STATUS_HIRED = 'hired'
JOB_STATUS_REJECTED = 'rejected'

JOB_STATUS_CHOICES = [
    (JOB_STATUS_NEW, 'New'),
    (JOB_STATUS_REVIEWED, 'Reviewed'),
    (JOB_STATUS_INTERVIEW, 'Interview Scheduled'),
    (JOB_STATUS_HIRED, 'Hired'),
    (JOB_STATUS_REJECTED, 'Rejected'),
]


# COLLABORATION AVAILABILITY (Weekly Hours)
AVAILABILITY_5 = "5"
AVAILABILITY_8 = "8"
AVAILABILITY_10 = "10"
AVAILABILITY_15 = "15"
AVAILABILITY_20 = "20"
AVAILABILITY_30 = "30"
AVAILABILITY_40 = "40"

COLLABORATION_AVAILABILITY_CHOICES = [
    (AVAILABILITY_5, "5 hours/week"),
    (AVAILABILITY_8, "8 hours/week"),
    (AVAILABILITY_10, "10 hours/week"),
    (AVAILABILITY_15, "15 hours/week"),
    (AVAILABILITY_20, "20 hours/week"),
    (AVAILABILITY_30, "30 hours/week"),
    (AVAILABILITY_40, "40 hours/week"),
]
