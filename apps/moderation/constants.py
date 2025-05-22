







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


# Access Request Status ------------------------------------------------
ACCESS_STATUS_NEW = 'new'
ACCESS_STATUS_REVIEWED = 'reviewed'
ACCESS_STATUS_INVITED = 'invited'
ACCESS_STATUS_REJECTED = 'rejected'

ACCESS_STATUS_CHOICES = [
    (ACCESS_STATUS_NEW, 'New'),
    (ACCESS_STATUS_REVIEWED, 'Reviewed'),
    (ACCESS_STATUS_INVITED, 'Invite Sent'),
    (ACCESS_STATUS_REJECTED, 'Rejected'),
]

# How did you hear about us? ----------------------------------------------
HEARD_FROM_FRIEND = 'friend'
HEARD_FROM_CHURCH = 'church'
HEARD_FROM_SOCIAL = 'social'
HEARD_FROM_SEARCH = 'search'
HEARD_FROM_EVENT = 'event'
HEARD_FROM_YOUTUBE = 'youtube'
HEARD_FROM_PODCAST = 'podcast'
HEARD_FROM_NEWSLETTER = 'newsletter'
HEARD_FROM_BLOG = 'blog'
HEARD_FROM_WHATSAPP = 'whatsapp'
HEARD_FROM_TELEGRAM = 'telegram'
HEARD_FROM_INFLUENCER = 'influencer'
HEARD_FROM_OTHER = 'other'

HEAR_ABOUT_US_CHOICES = [
    (HEARD_FROM_FRIEND, 'Friend or Family'),
    (HEARD_FROM_CHURCH, 'Church or Fellowship'),
    (HEARD_FROM_SOCIAL, 'Social Media (Facebook, Instagram, etc.)'),
    (HEARD_FROM_SEARCH, 'Search Engine (Google, Bing, etc.)'),
    (HEARD_FROM_YOUTUBE, 'YouTube'),
    (HEARD_FROM_PODCAST, 'Podcast or Radio Program'),
    (HEARD_FROM_EVENT, 'Event or Conference'),
    (HEARD_FROM_NEWSLETTER, 'Email Newsletter'),
    (HEARD_FROM_BLOG, 'Blog or Article'),
    (HEARD_FROM_WHATSAPP, 'WhatsApp Group / Contact'),
    (HEARD_FROM_TELEGRAM, 'Telegram Channel / Group'),
    (HEARD_FROM_INFLUENCER, 'Influencer or Public Figure'),
    (HEARD_FROM_OTHER, 'Other'),
]
