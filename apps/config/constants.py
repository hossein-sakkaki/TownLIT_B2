# Gender choices ----------------------------------------------------------------------------------
MALE = 'Male'
FEMALE = 'Female'
GENDER_CHOICES = [
    (MALE, 'Male'),
    (FEMALE, 'Female'),
]


# Delivery Method Types ------------------------------------------------------------------------------------
ONLINE = 'online'
IN_PERSON = 'inperson'
HYBRID = 'hybrid'
DELIVERY_METHOD_CHOICES = [
    (ONLINE, 'Online'),
    (IN_PERSON, 'In-Person'),
    (HYBRID, 'Hybrid'),
]


# SELLING TYPE Choices ---------------------------------------------------------------------
FREE = 'free'
FOR_SALE = 'for_sale'
SELLING_TYPE_CHOICES = [
    ('free', 'Free'),
    ('for_sale', 'For Sale'),
]


# Address Type Choices -------------------------------------------------------------------------------
HOME = 'home'
WORK = 'work'
OFFICE = 'office'
WAREHOUSE = 'warehouse'
CHURCH = 'church'
SCHOOL = 'school'
UNIVERSITY = 'university'
CONFERENCE_CENTER = 'conference_center'
MISSION_CENTER = 'mission_center'
COUNSELING_CENTER = 'counseling_center'
BRANCH = 'branch'
FRIENDS_HOME = 'friends_home'
SUPPLIER = 'supplier'
GYM = 'gym'
CHARITY_CENTER = 'charity_center'
DISTRIBUTION_POINT = 'distribution_point'
EVENT_LOCATION = 'event_location'
YOUTH_CENTER = 'youth_center'
RETREAT_CENTER = 'retreat_center'
OTHER = 'other'
ADDRESS_TYPE_CHOICES = [
    (HOME, 'Home'),
    (WORK, 'Work'),
    (OFFICE, 'Office'),
    (WAREHOUSE, 'Warehouse'),
    (CHURCH, 'Church'),
    (SCHOOL, 'School'),
    (UNIVERSITY, 'University'),
    (CONFERENCE_CENTER, 'Conference Center'),
    (MISSION_CENTER, 'Mission Center'),
    (COUNSELING_CENTER, 'Christian Counseling Center'),
    (BRANCH, 'Branch'),
    (FRIENDS_HOME, 'Friend\'s Home'),
    (SUPPLIER, 'Supplier'),
    (GYM, 'Gym'),
    (CHARITY_CENTER, 'Charity Center'),
    (DISTRIBUTION_POINT, 'Distribution Point'),
    (EVENT_LOCATION, 'Event Location'),
    (YOUTH_CENTER, 'Youth Center'),
    (RETREAT_CENTER, 'Retreat Center'),
    (OTHER, 'Other'),
]


# Copyright Choices ----------------------------------------------------------------------------
COPYRIGHT_YES = 'Yes'
COPYRIGHT_NO = 'No'
COPYRIGHT_OWNED = 'Owned'
COPYRIGHT_CHOICES = [
    (COPYRIGHT_YES, 'Yes'),
    (COPYRIGHT_NO, 'No'),
    (COPYRIGHT_OWNED, 'Owned by Institution')
]

# Timezone Choices --------------------------------------------------------------------------------
import pytz
TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]


# Days of Week Choices ----------------------------------------------------------------------------
MONDAY = 'monday'
TUESDAY = 'tuesday'
WEDNESDAY = 'wednesday'
THURSDAY = 'thursday'
FRIDAY = 'friday'
SATURDAY = 'saturday'
SUNDAY = 'sunday'
DAYS_OF_WEEK_CHOICES = [
    (MONDAY, 'Monday'),
    (TUESDAY, 'Tuesday'),
    (WEDNESDAY, 'Wednesday'),
    (THURSDAY, 'Thursday'),
    (FRIDAY, 'Friday'),
    (SATURDAY, 'Saturday'),
    (SUNDAY, 'Sunday'),
]


#  Ferequency Choices -------------------------------------------------------------------------------
WEEKLY = 'weekly'
MONTHLY = 'monthly'
ANNUALLY = 'annually'
FREQUENCY_CHOICES = [
    (WEEKLY, 'Weekly'),
    (MONTHLY, 'Monthly'),
    (ANNUALLY, 'Annually'),
]


# REACTION TYPE Choices ----------------------------------------------------------------------------
LIKE = 'like'
BLESS = 'bless'
GRATITUDE = 'gratitude'
AMEN = 'amen'
ENCOURAGEMENT = 'encouragement'
EMPATHY = 'empathy'
REACTION_TYPE_CHOICES = [
    (LIKE, 'Like'),
    (BLESS, 'Bless'),
    (GRATITUDE, 'Gratitude'),
    (AMEN, 'Amen'),
    (ENCOURAGEMENT, 'Encouragement'),
    (EMPATHY, 'Empathy'),
]


# Church Denominations ----------------------------------------------------------------------------
LUTHERANISM = 'lutheranism'
CALVINISM_OR_REFORMED = 'calvinism_or_reformed'
ANGLICANISM = 'anglicanism'
METHODISM = 'methodism'
BAPTISM = 'baptism'
PRESBYTERIANISM = 'presbyterianism'
PENTECOSTALISM = 'pentecostalism'
ADVENTISM = 'adventism'
ANABAPTISM = 'anabaptism'
CONGREGATIONALISM = 'congregationalism'
ROMAN_CATHOLICISM = 'roman_catholicism'
EASTERN_CATHOLIC_CHURCHES = 'eastern_catholic_churches'
EASTERN_ORTHODOXY = 'eastern_orthodoxy'
ORIENTAL_ORTHODOXY = 'oriental_Orthodoxy'
CHURCH_OF_THE_EAST = 'church_of_the_East'
CHURCH_DENOMINATIONS_CHOICES = [
    (LUTHERANISM, 'Lutheranism'),
    (CALVINISM_OR_REFORMED, 'Calvinism or Reformed'),
    (ANGLICANISM, 'Anglicanism'),
    (METHODISM, 'Methodism'),
    (BAPTISM, 'Baptism'),
    (PRESBYTERIANISM, 'Presbyterianism'),
    (PENTECOSTALISM, 'Pentecostalism'),
    (ADVENTISM, 'Adventism'),
    (ANABAPTISM, 'Anabaptism'),
    (CONGREGATIONALISM, 'Congregationalism'),
    (ROMAN_CATHOLICISM, 'Roman Catholicism'),
    (EASTERN_CATHOLIC_CHURCHES, 'Eastern Catholic Churches'),
    (EASTERN_ORTHODOXY, 'Eastern Orthodoxy'),
    (ORIENTAL_ORTHODOXY, 'Oriental Orthodoxy'),
    (CHURCH_OF_THE_EAST, 'Church of the East'),
]


# User Label Choices --------------------------------------------------------------------------------
BELIEVER = 'believer'
SEEKER = 'seeker'
PREFER_NOT_TO_SAY = 'prefer_not_to_say'
USER_LABEL_CHOICES = [
    (BELIEVER, 'I follow Jesus (Believer)'),
    (SEEKER, 'I’m exploring faith (Seeker)'),
    (PREFER_NOT_TO_SAY, 'I’d prefer not to say'),
]

# Organization Service Category Choices -------------------------------------------------------------
ADDICTION_RECOVERY = 'addiction_recovery'
BIBLE_STUDY = 'bible_study'
CHAPLAINCY_SERVICES = 'chaplaincy_services'
CHILDREN_SERVICES = 'children_services'
CHRISTIAN_BROADCASTING = 'christian_broadcasting'
CHRISTIAN_CAMPS = 'christian_camps'
CHRISTIAN_HOSPITAL = 'christian_hospital'
CHRISTIAN_LEGAL_SERVICES = 'christian_legal_services'
CHRISTIAN_MUSIC = 'christian_music'
CHRISTIAN_SCHOOLS = 'christian_schools'
CHRISTIAN_UNIVERSITY = 'christian_university'
CHURCH_SERVICES = 'church_services'
COMMUNITY_CENTERS = 'community_centers'
COUNSELING_SERVICES = 'counseling_services'
DEVELOPMENT_PROGRAMS = 'development_programs'
DISABILITY_MINISTRIES = 'disability_ministries'
DISASTER_RELIEF = 'disaster_relief'
DRAMA_AND_THEATER = 'drama_and_theater'
ELDERLY_CARE = 'elderly_care'
ENVIRONMENTAL_STEWARDSHIP = 'environmental_stewardship'
EVANGELISTIC_CAMPAIGNS = 'evangelistic_campaigns'
FAMILY_RETREATS = 'family_retreats'
FOOD_BANKS = 'food_banks'
HEALTH_CLINIC = 'health_clinic'
HOMELESS_SHELTERS = 'homeless_shelters'
HUMAN_RIGHTS_ADVOCACY = 'human_rights_advocacy'
INTERNATIONAL_MISSIONS = 'international_missions'
INTERFAITH_DIALOGUES = 'interfaith_dialogues'
JOB_TRAINING = 'job_training'
LOCAL_MISSIONS = 'local_missions'
MARRIAGE_COUNSELING = 'marriage_counseling'
MEDICAL_MISSION = 'medical_mission'
MENS_MINISTRIES = 'mens_ministries'
MENTAL_HEALTH_MINISTRIES = 'mental_health_ministries'
ONLINE_MINISTRIES = 'online_ministries'
ORPHANAGE = 'orphanage'
PARENTING_CLASSES = 'parenting_classes'
PUBLISHING = 'publishing'
PRAYER_MEETINGS = 'prayer_meetings'
REFUGEE_ASSISTANCE = 'refugee_assistance'
SUNDAY_SCHOOL = 'sunday_school'
SPORTS_MINISTRIES = 'sports_ministries'
THEOLOGICAL_EDUCATION = 'theological_education'
VACATION_BIBLE_SCHOOL = 'vacation_bible_school'
VISUAL_ARTS = 'visual_arts'
WOMENS_MINISTRIES = 'womens_ministries'
WORSHIP_CONCERTS = 'worship_concerts'
YOUTH_SERVICES = 'youth_services'
ORGANIZATION_SERVICE_CATEGORY_CHOICES = [
    (ADDICTION_RECOVERY, 'Addiction Recovery'),
    (BIBLE_STUDY, 'Bible Study'),
    (CHAPLAINCY_SERVICES, 'Chaplaincy Services'),
    (CHILDREN_SERVICES, 'Children Services'),
    (CHRISTIAN_BROADCASTING, 'Christian Broadcasting'),
    (CHRISTIAN_CAMPS, 'Christian Camps'),
    (CHRISTIAN_HOSPITAL, 'Christian Hospital'),
    (CHRISTIAN_LEGAL_SERVICES, 'Christian Legal Services'),
    (CHRISTIAN_MUSIC, 'Christian Music'),
    (CHRISTIAN_SCHOOLS, 'Christian Schools'),
    (CHRISTIAN_UNIVERSITY, 'Christian University'),
    (CHURCH_SERVICES, 'Church Services'),
    (COMMUNITY_CENTERS, 'Community Centers'),
    (COUNSELING_SERVICES, 'Counseling Services'),
    (DEVELOPMENT_PROGRAMS, 'Development Programs'),
    (DISABILITY_MINISTRIES, 'Disability Ministries'),
    (DISASTER_RELIEF, 'Disaster Relief'),
    (DRAMA_AND_THEATER, 'Drama and Theater'),
    (ELDERLY_CARE, 'Elderly Care'),
    (ENVIRONMENTAL_STEWARDSHIP, 'Environmental Stewardship'),
    (EVANGELISTIC_CAMPAIGNS, 'Evangelistic Campaigns'),
    (FAMILY_RETREATS, 'Family Retreats'),
    (FOOD_BANKS, 'Food Banks'),
    (HEALTH_CLINIC, 'Health Clinic'),
    (HOMELESS_SHELTERS, 'Homeless Shelters'),
    (HUMAN_RIGHTS_ADVOCACY, 'Human Rights Advocacy'),
    (INTERNATIONAL_MISSIONS, 'International Missions'),
    (INTERFAITH_DIALOGUES, 'Interfaith Dialogues'),
    (JOB_TRAINING, 'Job Training'),
    (LOCAL_MISSIONS, 'Local Missions'),
    (MARRIAGE_COUNSELING, 'Marriage Counseling'),
    (MEDICAL_MISSION, 'Medical Mission'),
    (MENS_MINISTRIES, 'Men\'s Ministries'),
    (MENTAL_HEALTH_MINISTRIES, 'Mental Health Ministries'),
    (ONLINE_MINISTRIES, 'Online Ministries'),
    (ORPHANAGE, 'Orphanage'),
    (PARENTING_CLASSES, 'Parenting Classes'),
    (PUBLISHING, 'Publishing'),
    (PRAYER_MEETINGS, 'Prayer Meetings'),
    (REFUGEE_ASSISTANCE, 'Refugee Assistance'),
    (SUNDAY_SCHOOL, 'Sunday School'),
    (SPORTS_MINISTRIES, 'Sports Ministries'),
    (THEOLOGICAL_EDUCATION, 'Theological Education'),
    (VACATION_BIBLE_SCHOOL, 'Vacation Bible School'),
    (VISUAL_ARTS, 'Visual Arts'),
    (WOMENS_MINISTRIES, 'Women\'s Ministries'),
    (WORSHIP_CONCERTS, 'Worship Concerts'),
    (YOUTH_SERVICES, 'Youth Services'),
]

# Spiritual Ministry Choices -------------------------------------------------------------
ADMINISTRATION = 'administration'
CHARITABLE_WORK = 'charitable_work'
CHAPLAINCY = 'chaplaincy'
CHILDRENS_MINISTRY = 'childrens_ministry'
CHURCH_PLANTING = 'church_planting'
COUNSELING = 'counseling'
DISCIPLESHIP = 'discipleship'
EVANGELISM = 'evangelism'
HEALING_MINISTRY = 'healing_ministry'
HOSPITAL_VISITATION = 'hospital_visitation'
HOSPITALITY = 'hospitality'
INTERCESSORY_PRAYER = 'intercessory_prayer'
LEADERSHIP = 'leadership'
MEDIA_MINISTRY = 'media_ministry'
MISSIONARY_WORK = 'missionary_work'
MUSIC_MINISTRY = 'music_ministry'
OUTREACH_MINISTRY = 'outreach_ministry'
PASTORING = 'pastoring'
PRAYER_MINISTRY = 'prayer_ministry'
SMALL_GROUP_LEADERSHIP = 'small_group_leadership'
SPIRITUAL_DIRECTION = 'spiritual_direction'
SUPPORT_GROUP_LEADERSHIP = 'support_group_leadership'
TEACHING = 'teaching'
WORSHIP_LEADERSHIP = 'worship_leadership'
YOUTH_MINISTRY = 'youth_ministry'
SPIRITUAL_MINISTRY_CHOICES = [
    (ADMINISTRATION, 'Administration'),
    (CHARITABLE_WORK, 'Charitable Work'),
    (CHAPLAINCY, 'Chaplaincy'),
    (CHILDRENS_MINISTRY, 'Children’s Ministry'),
    (CHURCH_PLANTING, 'Church Planting'),
    (COUNSELING, 'Counseling'),
    (DISCIPLESHIP, 'Discipleship'),
    (EVANGELISM, 'Evangelism'),
    (HEALING_MINISTRY, 'Healing Ministry'),
    (HOSPITAL_VISITATION, 'Hospital Visitation'),
    (HOSPITALITY, 'Hospitality'),
    (INTERCESSORY_PRAYER, 'Intercessory Prayer'),
    (LEADERSHIP, 'Leadership'),
    (MEDIA_MINISTRY, 'Media Ministry'),
    (MISSIONARY_WORK, 'Missionary Work'),
    (MUSIC_MINISTRY, 'Music Ministry'),
    (OUTREACH_MINISTRY, 'Outreach Ministry'),
    (PASTORING, 'Pastoring'),
    (PRAYER_MINISTRY, 'Prayer Ministry'),
    (SMALL_GROUP_LEADERSHIP, 'Small Group Leadership'),
    (SPIRITUAL_DIRECTION, 'Spiritual Direction'),
    (SUPPORT_GROUP_LEADERSHIP, 'Support Group Leadership'),
    (TEACHING, 'Teaching'),
    (WORSHIP_LEADERSHIP, 'Worship Leadership'),
    (YOUTH_MINISTRY, 'Youth Ministry'),
]


# POLICY OF TOWNNLIT Choices ------------------------------------------------------------
PRIVACY_POLICY = 'privacy_policy'
TERMS_OF_SERVICE = 'terms_of_service'
COMMUNITY_GUIDELINES = 'community_guidelines'
DATA_USAGE_POLICY = 'data_usage_policy'
CONTENT_MODERATION_POLICY = 'content_moderation_policy'
COPYRIGHT_POLICY = 'copyright_policy'
DISPUTE_RESOLUTION = 'dispute_resolution'
VISION_AND_MISSION = 'vision_and_mission'
TOWNLIT_HISTORY = 'townlit_history'
TOWNLIT_BELIEFS = 'townlit_beliefs'
TERMS_AND_CONDITIONS = 'terms_and_conditions'
COOKIE_POLICY = 'cookie_policy'
TERMS_AND_POLICIES_CHOICES = [
    (PRIVACY_POLICY, 'Privacy Policy'),
    (TERMS_OF_SERVICE, 'Terms of Service'),
    (COMMUNITY_GUIDELINES, 'Community Guidelines'),
    (DATA_USAGE_POLICY, 'Data Usage Policy'),
    (CONTENT_MODERATION_POLICY, 'Content Moderation Policy'),
    (COPYRIGHT_POLICY, 'Copyright Policy'),
    (DISPUTE_RESOLUTION, 'Dispute Resolution and Arbitration'),
    (VISION_AND_MISSION, 'Vision and Mission'),
    (TOWNLIT_HISTORY, 'TownLIT History'),
    (TOWNLIT_BELIEFS, 'TownLIT Beliefs'),
    (TERMS_AND_CONDITIONS, 'Terms and Conditions'),
    (COOKIE_POLICY, 'Cookie Policy'),
]


# DISPLAY LOCATIONS for Terms and Policies --------------------------------------------
DISPLAY_IN_FOOTER = 'footer'
DISPLAY_IN_OFFICIAL = 'official'
DISPLAY_IN_BOTH = 'both'

POLICY_DISPLAY_LOCATION_CHOICES = [
    (DISPLAY_IN_FOOTER, 'Footer'),
    (DISPLAY_IN_OFFICIAL, 'Official Info Page'),
    (DISPLAY_IN_BOTH, 'Both'),
]


# DISPLAY LOCATIONS for Terms and Policies (Left or Right) -----------------------------
FOOTER_LEFT = 'left'
FOOTER_RIGHT = 'right'
FOOTER_COLUMN_CHOICES = [
    (FOOTER_LEFT, 'Left Column'),
    (FOOTER_RIGHT, 'Right Column'),
]


# LOG ACTION Choices ---------------------------------------------------------------------
VIEW = 'view'
EDIT = 'edit'
DELETE = 'delete'
LOG_ACTION_CHOICES = [
    (VIEW, 'View'),
    (EDIT, 'Edit'),
    (DELETE, 'Delete'),
]

# USER FEEDBACK STATUS Choices -----------------------------------------------------------
NEW = 'new'
REVIEWED = 'reviewed'
RESOLVED = 'resolved'
USER_FEEDBACK_STATUS_CHOICES = [
    (NEW, 'New'),
    (REVIEWED, 'Reviewed'),
    (RESOLVED, 'Resolved'),
]

