# Copyright Choices ----------------------------------------------------------------------------
COPYRIGHT_YES = 'Yes'
COPYRIGHT_NO = 'No'
COPYRIGHT_OWNED = 'Owned'
COPYRIGHT_CHOICES = [
    (COPYRIGHT_YES, 'Yes'),
    (COPYRIGHT_NO, 'No'),
    (COPYRIGHT_OWNED, 'Owned by Institution')
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

# Delivery Method Types ------------------------------------------------------------------------------------
ONLINE = 'online'
IN_PERSON = 'inperson'
HYBRID = 'hybrid'
DELIVERY_METHOD_CHOICES = [
    (ONLINE, 'Online'),
    (IN_PERSON, 'In-Person'),
    (HYBRID, 'Hybrid'),
]

# Common -------------------------------------------------------------------------
WORSHIP_EVENT = 'worship_event'
SERVICE = 'service'
PRAYER_MEETING = 'prayer_meeting'
BIBLE_STUDY = 'bible_study'
YOUTH_MEETING = 'youth_meeting'
OUTREACH_EVENT = 'outreach_event'
FELLOWSHIP_EVENT = 'fellowship_event'
OTHER_EVENT = 'other'
SERVICE_EVENT_CHOICES = [
    (WORSHIP_EVENT, 'Worship Event'),
    (SERVICE, 'Service'),
    (PRAYER_MEETING, 'Prayer Meeting'),
    (BIBLE_STUDY, 'Bible Study'),
    (YOUTH_MEETING, 'Youth Meeting'),
    (OUTREACH_EVENT, 'Outreach Event'),
    (FELLOWSHIP_EVENT, 'Fellowship Event'),
    (OTHER_EVENT, 'Other'),
]

# Children Event Type Choices ----------------------------------------------------
FESTIVAL = 'festival'
WORKSHOP = 'workshop'
COMPETITION = 'competition'
CONFERENCE = 'conference'
OUTDOOR_ACTIVITY = 'outdoor_activity'
WORSHIP_SERVICE = 'worship_service'
FUNDRAISING = 'fundraising'
EDUCATIONAL = 'educational'
ARTS_AND_CRAFTS = 'arts_and_crafts'
STORYTELLING = 'storytelling'
GAME_EVENT = 'game_event'
HOLIDAY_EVENT = 'holiday_event'
SUMMER_CAMP = 'summer_camp'
OTHER_EVENT = 'other'
CHILDREN_EVENT_TYPE_CHOICES = [
    (FESTIVAL, 'Festival'),
    (WORKSHOP, 'Workshop'),
    (COMPETITION, 'Competition'),
    (CONFERENCE, 'Conference'),
    (OUTDOOR_ACTIVITY, 'Outdoor Activity'),
    (WORSHIP_SERVICE, 'Worship Service'),
    (FUNDRAISING, 'Fundraising Event'),
    (EDUCATIONAL, 'Educational Event'),
    (ARTS_AND_CRAFTS, 'Arts and Crafts'),
    (STORYTELLING, 'Storytelling'),
    (GAME_EVENT, 'Game Event'),
    (HOLIDAY_EVENT, 'Holiday Event'),
    (SUMMER_CAMP, 'Summer Camp'),
    (OTHER_EVENT, 'Other'),
]

# Youth Event Type Choices ------------------------------------------------------
WORSHIP_EVENT = 'worship_event'
SERVICE = 'service'
PRAYER_MEETING = 'prayer_meeting'
BIBLE_STUDY = 'bible_study'
YOUTH_MEETING = 'youth_meeting'
OUTREACH_EVENT = 'outreach_event'
FELLOWSHIP_EVENT = 'fellowship_event'
WORKSHOP = 'workshop'
CONFERENCE = 'conference'
RETREAT = 'retreat'
EDUCATIONAL = 'educational'
FUNDRAISING = 'fundraising'
OUTDOOR_ACTIVITY = 'outdoor_activity'
MENTORING = 'mentoring'
SPORTS_EVENT = 'sports_event'
COMPETITION = 'competition'
SOCIAL_EVENT = 'social_event'
FESTIVAL = 'festival'
MUSIC_EVENT = 'music_event'
CAMP = 'camp'
OTHER_EVENT = 'other'
YOUTH_EVENT_TYPE_CHOICES = [
    (WORSHIP_EVENT, 'Worship Event'),
    (SERVICE, 'Service'),
    (PRAYER_MEETING, 'Prayer Meeting'),
    (BIBLE_STUDY, 'Bible Study'),
    (YOUTH_MEETING, 'Youth Meeting'),
    (OUTREACH_EVENT, 'Outreach Event'),
    (FELLOWSHIP_EVENT, 'Fellowship Event'),
    (WORKSHOP, 'Workshop'),
    (CONFERENCE, 'Conference'),
    (RETREAT, 'Retreat'),
    (EDUCATIONAL, 'Educational Event'),
    (FUNDRAISING, 'Fundraising Event'),
    (OUTDOOR_ACTIVITY, 'Outdoor Activity'),
    (MENTORING, 'Mentoring'),
    (SPORTS_EVENT, 'Sports Event'),
    (COMPETITION, 'Competition'),
    (SOCIAL_EVENT, 'Social Event'),
    (FESTIVAL, 'Festival'),
    (MUSIC_EVENT, 'Music Event'),
    (CAMP, 'Camp'),
    (OTHER_EVENT, 'Other'),
]

# Women Event Type Choices -----------------------------------------------------
ADVOCACY_CAMPAIGNS = 'advocacy_campaigns'
BIBLE_STUDY = 'bible_study'
CONFERENCE = 'conference'
CRAFT_AND_ARTS = 'craft_and_arts'
EDUCATIONAL = 'educational'
FUNDRAISING = 'fundraising'
HEALTH_AND_WELLNESS = 'health_and_wellness'
HEALTH_INITIATIVES = 'health_initiatives'
HOLIDAY_EVENT = 'holiday_event'
MENTAL_HEALTH = 'mental_health'
MENTORING = 'mentoring'
PRAYER_MEETING = 'prayer_meeting'
SAFETY_PROGRAMS = 'safety_programs'
SERVICE = 'service'
SOCIAL_EVENT = 'social_event'
SUPPORT_PROGRAMS = 'support_programs'
WOMEN_FELLOWSHIP = 'women_fellowship'
WOMEN_OUTREACH = 'women_outreach'
WOMEN_RETREAT = 'women_retreat'
WOMEN_SUPPORT_GROUP = 'women_support_group'
WOMEN_WORKSHOP = 'women_workshop'
OTHER_EVENT = 'other'

WOMEN_EVENT_TYPE_CHOICES = [
    (ADVOCACY_CAMPAIGNS, 'Advocacy Campaigns'),
    (BIBLE_STUDY, 'Bible Study'),
    (CONFERENCE, 'Conference'),
    (CRAFT_AND_ARTS, 'Craft and Arts'),
    (EDUCATIONAL, 'Educational Event'),
    (FUNDRAISING, 'Fundraising Event'),
    (HEALTH_AND_WELLNESS, 'Health and Wellness'),
    (HEALTH_INITIATIVES, 'Health Initiatives'),
    (HOLIDAY_EVENT, 'Holiday Event'),
    (MENTAL_HEALTH, 'Mental Health'),
    (MENTORING, 'Mentoring'),
    (PRAYER_MEETING, 'Prayer Meeting'),
    (SAFETY_PROGRAMS, 'Safety Programs'),
    (SERVICE, 'Service'),
    (SOCIAL_EVENT, 'Social Event'),
    (SUPPORT_PROGRAMS, 'Support Programs'),
    (WOMEN_FELLOWSHIP, 'Women Fellowship'),
    (WOMEN_OUTREACH, 'Women Outreach'),
    (WOMEN_RETREAT, 'Women Retreat'),
    (WOMEN_SUPPORT_GROUP, 'Women Support Group'),
    (WOMEN_WORKSHOP, 'Women Workshop'),
    (OTHER_EVENT, 'Other'),
]

# Men Event Type Choices ------------------------------------------------------
ACTIVITY = 'activity'
BIBLE_STUDY = 'bible_study'
CAREER_DEVELOPMENT = 'career_development'
COMMUNITY_PROJECT = 'community_project'
CONFERENCE = 'conference'
EDUCATIONAL = 'educational'
FUNDRAISING = 'fundraising'
HEALTH_WELLNESS = 'health_wellness'
HOLIDAY_EVENT = 'holiday_event'
LEADERSHIP_TRAINING = 'leadership_training'
MEN_FELLOWSHIP = 'men_fellowship'
MEN_OUTREACH = 'men_outreach'
MEN_RETREAT = 'men_retreat'
MEN_SUPPORT_GROUP = 'men_support_group'
MEN_WORKSHOP = 'men_workshop'
MENTORING = 'mentoring'
PRAYER_MEETING = 'prayer_meeting'
SERVICE = 'service'
SOCIAL_EVENT = 'social_event'
SPIRITUAL_GROWTH = 'spiritual_growth'
SPORTS_EVENT = 'sports_event'
OUTDOOR_ACTIVITY = 'outdoor_activity'
OTHER_EVENT = 'other'

MEN_EVENT_TYPE_CHOICES = [
    (ACTIVITY, 'Activity'),
    (BIBLE_STUDY, 'Bible Study'),
    (CAREER_DEVELOPMENT, 'Career Development'),
    (COMMUNITY_PROJECT, 'Community Project'),
    (CONFERENCE, 'Conference'),
    (EDUCATIONAL, 'Educational Event'),
    (FUNDRAISING, 'Fundraising Event'),
    (HEALTH_WELLNESS, 'Health & Wellness'),
    (HOLIDAY_EVENT, 'Holiday Event'),
    (LEADERSHIP_TRAINING, 'Leadership Training'),
    (MEN_FELLOWSHIP, 'Men Fellowship'),
    (MEN_OUTREACH, 'Men Outreach'),
    (MEN_RETREAT, 'Men Retreat'),
    (MEN_SUPPORT_GROUP, 'Men Support Group'),
    (MEN_WORKSHOP, 'Men Workshop'),
    (MENTORING, 'Mentoring'),
    (PRAYER_MEETING, 'Prayer Meeting'),
    (SERVICE, 'Service'),
    (SOCIAL_EVENT, 'Social Event'),
    (SPIRITUAL_GROWTH, 'Spiritual Growth'),
    (SPORTS_EVENT, 'Sports Event'),
    (OUTDOOR_ACTIVITY, 'Outdoor Activity'),
    (OTHER_EVENT, 'Other'),
]

# Media Content Choices --------------------------------------------------------------------
AUDIO = 'audio'
VIDEO = 'video'
ARTICLE = 'article'
BOOK = 'book'
PODCAST = 'podcast'
STUDY_GUIDE = 'study_guide'
GAME = 'game'
ENTERTAINMENT = 'entertainment'
OTHER = 'other'
MEDIA_CONTENT_CHOICES = [
    (VIDEO, 'Video'),
    (AUDIO, 'Audio'),
    (ARTICLE, 'Article'),
    (BOOK, 'Book'),
    (PODCAST, 'Podcast'),
    (STUDY_GUIDE, 'Study Guide'),
    (GAME, 'Game'),
    (ENTERTAINMENT, 'Entertainment'),
    (OTHER, 'Other'),
]

#  Literary Category Choices -----------------------------------------------------------------
APOLOGETICS = 'Apologetics'
BIBLICAL_STUDIES = 'Biblical Studies'
BIOGRAPHY_AUTOBIOGRAPHY = 'Biography/Autobiography'
CHRISTIAN_FICTION = 'Christian Fiction'
CHRISTIAN_MYSTERY_SUSPENSE = 'Christian Mystery/Suspense'
CHRISTIAN_DEVOTIONAL = 'Christian Devotional'
CHRISTIAN_LIVING = 'Christian Living'
CHRISTIAN_BIOGRAPHY_AUTOBIOGRAPHY = 'Christian Biography/Autobiography'
CHRISTIAN_INSPIRATIONAL = 'Christian Inspirational'
CHRISTIAN_HISTORICAL_FICTION = 'Christian Historical Fiction'
DRAMA = 'Drama'
ESSAY = 'Essay'
FANTASY = 'Fantasy'
HISTORICAL = 'Historical'
POETRY = 'Poetry'
SCIENCE = 'Science'
SOCIAL_ISSUES = 'Social Issues'
SPIRITUAL_GROWTH = 'Spiritual Growth'
THEOLOGY = 'Theology'
OTHER = 'Other'
LITERARY_CATEGORY_CHOICES = [
    (APOLOGETICS, 'Apologetics'),
    (BIBLICAL_STUDIES, 'Biblical Studies'),
    (BIOGRAPHY_AUTOBIOGRAPHY, 'Biography/Autobiography'),
    (CHRISTIAN_FICTION, 'Christian Fiction'),
    (CHRISTIAN_MYSTERY_SUSPENSE, 'Christian Mystery/Suspense'),
    (CHRISTIAN_DEVOTIONAL, 'Christian Devotional'),
    (CHRISTIAN_LIVING, 'Christian Living'),
    (CHRISTIAN_BIOGRAPHY_AUTOBIOGRAPHY, 'Christian Biography/Autobiography'),
    (CHRISTIAN_INSPIRATIONAL, 'Christian Inspirational'),
    (CHRISTIAN_HISTORICAL_FICTION, 'Christian Historical Fiction'),
    (DRAMA, 'Drama'),
    (ESSAY, 'Essay'),
    (FANTASY, 'Fantasy'),
    (HISTORICAL, 'Historical'),
    (POETRY, 'Poetry'),
    (SCIENCE, 'Science'),
    (SOCIAL_ISSUES, 'Social Issues'),
    (SPIRITUAL_GROWTH, 'Spiritual Growth'),
    (THEOLOGY, 'Theology'),
    (OTHER, 'Other'),
]


# Resource Type Choices -----------------------------------------------------------------------------
DOCUMENT = 'document'
PRESENTATION = 'presentation'
IMAGE = 'image'
BROCHURE = 'brochure'
CATALOG = 'catalog'
LINK = 'link'
GUIDE = 'guide'
MUSIC = 'music'
TEXT = 'text'
OTHER = 'other'
RESOURCE_TYPE_CHOICES = [
    (DOCUMENT, 'Document'),
    (PRESENTATION, 'Presentation'),
    (IMAGE, 'Image'),
    (BROCHURE, 'Brochure'),
    (CATALOG, 'Catalog'),
    (LINK, 'Link'),
    (GUIDE, 'Guide'),
    (MUSIC, 'Music'),
    (TEXT, 'Text'),
    (OTHER, 'Other'),
]
