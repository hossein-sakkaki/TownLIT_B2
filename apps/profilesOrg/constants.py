# Organization Type ----------------------------------------------------------------------------
CHURCH = 'Church'
MISSION_ORGANIZATION = 'Mission Organization'
# PARACHURCH_ORGANIZATION = 'Parachurch Organization'
CHRISTIAN_PUBLISHING_HOUSE = 'Christian Publishing House'
CHRISTIAN_COUNSELING_CENTER = 'Christian Counseling Center'
CHRISTIAN_WORSHIP_MINISTRY = 'Christian Worship Ministry'
CHRISTIAN_CONFERENCE_CENTER = 'Christian Conference Center'
CHRISTIAN_EDUCATIONAL_INSTITUTION = 'Christian School, University or Bible College'
# CHRISTIAN_CHARITY = 'Christian Charity'
CHRISTIAN_CHILDRENS_ORGANIZATION = 'Christian Children’s Organization'
CHRISTIAN_YOUTH_ORGANIZATION = 'Christian Youth Organization'
CHRISTIAN_WOMENS_ORGANIZATION = 'Christian Women’s Organization'
CHRISTIAN_MENS_ORGANIZATION = 'Christian Men’s Organization'
STORE = 'Store'
ORGANIZATION_TYPE_CHOICES = [
    (CHURCH, 'Church'),
    (MISSION_ORGANIZATION, 'Mission Organization'),
    # (PARACHURCH_ORGANIZATION, 'Parachurch Organization'),
    (CHRISTIAN_PUBLISHING_HOUSE, 'Christian Publishing House'),
    (CHRISTIAN_COUNSELING_CENTER, 'Christian Counseling Center'),
    (CHRISTIAN_WORSHIP_MINISTRY, 'Christian Worship Ministry'),
    (CHRISTIAN_CONFERENCE_CENTER, 'Christian Conference Center'),
    (CHRISTIAN_EDUCATIONAL_INSTITUTION, 'Christian School, University or Bible College'),
    # (CHRISTIAN_CHARITY, 'Christian Charity'),
    (CHRISTIAN_CHILDRENS_ORGANIZATION, 'Christian Children’s Organization'),
    (CHRISTIAN_YOUTH_ORGANIZATION, 'Christian Youth Organization'),
    (CHRISTIAN_WOMENS_ORGANIZATION, 'Christian Women’s Organization'),
    (CHRISTIAN_MENS_ORGANIZATION, 'Christian Men’s Organization'),
    (STORE, 'Store'),
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


# Delivery Method Types ------------------------------------------------------------------------------------
ONLINE = 'online'
IN_PERSON = 'inperson'
HYBRID = 'hybrid'
DELIVERY_METHOD_CHOICES = [
    (ONLINE, 'Online'),
    (IN_PERSON, 'In-Person'),
    (HYBRID, 'Hybrid'),
]


# Organization Manager Choices ---------------------------------------------------------------------
FULL_ACCESS = 'full_access'
LIMITED_ACCESS = 'limited_access'
ACCESS_LEVEL_CHOICES = [
    (FULL_ACCESS, 'Full Access'),
    (LIMITED_ACCESS, 'Limited Access'),
]


# Timezone Choices --------------------------------------------------------------------------------
import pytz
TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]


# Price Type Choices ----------------------------------------------------------------------------------
PRICE_FREE = 'Free'
PRICE_PAID = 'Paid'
PRICE_TYPE_CHOICES = [
    (PRICE_FREE, 'Free'),
    (PRICE_PAID, 'Paid')
]


# Institution Type Choices -------------------------------------------------------------------------
SCHOOL = 'school'
UNIVERSITY = 'university'
BIBLE_COLLEGE = 'bible_college'
INSTITUTION_TYPE_CHOICES = [
    (SCHOOL, 'School'),
    (UNIVERSITY, 'University'),
    (BIBLE_COLLEGE, 'Bible College'),
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


# Voting Type Choices ----------------------------------------------------------------------------------
VOTE_OWNER_ADDITION = 'owner_addition'
VOTE_OWNER_REMOVAL = 'owner_removal'
VOTE_ADMIN_REPLACEMENT = 'admin_replacement'
VOTE_DELETION = 'deletion'
VOTE_RESTORATION = 'restoration'
VOTE_OWNER_WITHDRAWAL = 'withdrawal'
VOTING_TYPE_CHOICES = [
    (VOTE_OWNER_ADDITION, 'Owner Addition'),
    (VOTE_OWNER_REMOVAL, 'Owner Removal'),
    (VOTE_ADMIN_REPLACEMENT, 'Admin Replacement'),
    (VOTE_DELETION, 'Deletion'),
    (VOTE_RESTORATION, 'Restoration'),
    (VOTE_OWNER_WITHDRAWAL, 'Owner Withdrawal')
]


# Voting Result Choices ----------------------------------------------------------------------------------
RESULT_APPROVED = 'approved'
RESULT_REJECTED = 'rejected'
VOTING_RESULT_CHOICES = [
    (RESULT_APPROVED, 'Approved'),
    (RESULT_REJECTED, 'Rejected')
]


# Christian Counseling Center Services ------------------------------------------------------------
MARRIAGE_COUNSELING = 'marriage_counseling'
FAMILY_COUNSELING = 'family_counseling'
INDIVIDUAL_COUNSELING = 'individual_counseling'
PREMARITAL_COUNSELING = 'premarital_counseling'
SPIRITUAL_COUNSELING = 'spiritual_counseling'
PSYCHOLOGICAL_COUNSELING = 'psychological_counseling'
GROUP_COUNSELING = 'group_counseling'
GRIEF_COUNSELING = 'grief_counseling'
ADDICTION_COUNSELING = 'addiction_counseling'
CRISIS_COUNSELING = 'crisis_counseling'
CAREER_COUNSELING = 'career_counseling'
ACADEMIC_COUNSELING = 'academic_counseling'
COUNSELING_SERVICE_CHOICES = [
    (MARRIAGE_COUNSELING, 'Marriage Counseling'),
    (FAMILY_COUNSELING, 'Family Counseling'),
    (INDIVIDUAL_COUNSELING, 'Individual Counseling'),
    (PREMARITAL_COUNSELING, 'Premarital Counseling'),
    (SPIRITUAL_COUNSELING, 'Spiritual Counseling'),
    (PSYCHOLOGICAL_COUNSELING, 'Psychological Counseling'),
    (GROUP_COUNSELING, 'Group Counseling'),
    (GRIEF_COUNSELING, 'Grief Counseling'),
    (ADDICTION_COUNSELING, 'Addiction Counseling'),
    (CRISIS_COUNSELING, 'Crisis Counseling'),
    (CAREER_COUNSELING, 'Career Counseling'),
    (ACADEMIC_COUNSELING, 'Academic Counseling'),
]


# Worship Style Choices -------------------------------------------------------------------------
TRADITIONAL = 'traditional'
CONTEMPORARY = 'contemporary'
GOSPEL = 'gospel'
HYMNAL = 'hymnal'
CHARISMATIC = 'charismatic'
LITURGICAL = 'liturgical'
ACOUSTIC = 'acoustic'
ROCK = 'rock'
ELECTRONIC = 'electronic'
CHORAL = 'choral'
SPONTANEOUS = 'spontaneous'
INSTRUMENTAL = 'instrumental'
MEDITATIVE = 'meditative'
BLENDED = 'blended'
AFRICAN_GOSPEL = 'african_gospel'
LATIN_AMERICAN = 'latin_american'
CARIBBEAN = 'caribbean'
CELTIC = 'celtic'
NATIVE_AMERICAN = 'native_american'
ASIAN_FUSION = 'asian_fusion'
REGGAE = 'reggae'
HIP_HOP = 'hip_hop'
FOLK = 'folk'
JAZZ = 'jazz'
WORSHIP_STYLE_CHOICES = [
    (TRADITIONAL, 'Traditional'),
    (CONTEMPORARY, 'Contemporary'),
    (GOSPEL, 'Gospel'),
    (HYMNAL, 'Hymnal'),
    (CHARISMATIC, 'Charismatic'),
    (LITURGICAL, 'Liturgical'),
    (ACOUSTIC, 'Acoustic'),
    (ROCK, 'Rock'),
    (ELECTRONIC, 'Electronic'),
    (CHORAL, 'Choral'),
    (SPONTANEOUS, 'Spontaneous'),
    (INSTRUMENTAL, 'Instrumental'),
    (MEDITATIVE, 'Meditative'),
    (BLENDED, 'Blended'),
    (AFRICAN_GOSPEL, 'African Gospel'),
    (LATIN_AMERICAN, 'Latin American'),
    (CARIBBEAN, 'Caribbean'),
    (CELTIC, 'Celtic'),
    (NATIVE_AMERICAN, 'Native American'),
    (ASIAN_FUSION, 'Asian Fusion'),
    (REGGAE, 'Reggae'),
    (HIP_HOP, 'Hip-Hop'),
    (FOLK, 'Folk'),
    (JAZZ, 'Jazz'),
]


# Language choices ----------------------------------------------------------------------------------
ENGLISH = 'en'
AFRIKAANS = 'af'
ALBANIAN = 'sq'
AMHARIC = 'am'
ARABIC = 'ar'
ARMENIAN = 'hy'
AZERBAIJANI = 'az'
BASQUE = 'eu'
BENGALI = 'bn'
BOSNIAN = 'bs'
BULGARIAN = 'bg'
BURMESE = 'my'
CATALAN = 'ca'
CHINESE = 'zh'
CROATIAN = 'hr'
CZECH = 'cs'
DANISH = 'da'
DUTCH = 'nl'
ESTONIAN = 'et'
FILIPINO = 'tl'
FINNISH = 'fi'
FRENCH = 'fr'
GEORGIAN = 'ka'
GERMAN = 'de'
GREEK = 'el'
GUJARATI = 'gu'
HAUSA = 'ha'
HEBREW = 'he'
HINDI = 'hi'
HUNGARIAN = 'hu'
ICELANDIC = 'is'
IGBO = 'ig'
INDONESIAN = 'id'
IRISH = 'ga'
ITALIAN = 'it'
JAPANESE = 'ja'
JAVANESE = 'jv'
KANNADA = 'kn'
KAZAKH = 'kk'
KOREAN = 'ko'
KURDISH = 'ku'
KYRGYZ = 'ky'
LAO = 'lo'
LATVIAN = 'lv'
LITHUANIAN = 'lt'
MACEDONIAN = 'mk'
MALAGASY = 'mg'
MALAY = 'ms'
MALAYALAM = 'ml'
MARATHI = 'mr'
MONGOLIAN = 'mn'
NEPALI = 'ne'
NORWEGIAN = 'no'
ORIYA = 'or'
PASHTO = 'ps'
PERSIAN = 'fa'
POLISH = 'pl'
PORTUGUESE = 'pt'
PUNJABI = 'pa'
ROMANIAN = 'ro'
RUSSIAN = 'ru'
SERBIAN = 'sr'
SINHALA = 'si'
SLOVAK = 'sk'
SLOVENIAN = 'sl'
SOMALI = 'so'
SPANISH = 'es'
SWAHILI = 'sw'
SWEDISH = 'sv'
TAMIL = 'ta'
TELUGU = 'te'
THAI = 'th'
TURKISH = 'tr'
UKRAINIAN = 'uk'
URDU = 'ur'
UZBEK = 'uz'
VIETNAMESE = 'vi'
WELSH = 'cy'
XHOSA = 'xh'
YORUBA = 'yo'
ZULU = 'zu'
OTHER = 'other'
LANGUAGE_CHOICES = [
    (ENGLISH, 'English'),
    (AFRIKAANS, 'Afrikaans'),
    (ALBANIAN, 'Albanian'),
    (AMHARIC, 'Amharic'),
    (ARABIC, 'Arabic'),
    (ARMENIAN, 'Armenian'),
    (AZERBAIJANI, 'Azerbaijani'),
    (BASQUE, 'Basque'),
    (BENGALI, 'Bengali'),
    (BOSNIAN, 'Bosnian'),
    (BULGARIAN, 'Bulgarian'),
    (BURMESE, 'Burmese'),
    (CATALAN, 'Catalan'),
    (CHINESE, 'Chinese'),
    (CROATIAN, 'Croatian'),
    (CZECH, 'Czech'),
    (DANISH, 'Danish'),
    (DUTCH, 'Dutch'),
    (ESTONIAN, 'Estonian'),
    (FILIPINO, 'Filipino'),
    (FINNISH, 'Finnish'),
    (FRENCH, 'French'),
    (GEORGIAN, 'Georgian'),
    (GERMAN, 'German'),
    (GREEK, 'Greek'),
    (GUJARATI, 'Gujarati'),
    (HAUSA, 'Hausa'),
    (HEBREW, 'Hebrew'),
    (HINDI, 'Hindi'),
    (HUNGARIAN, 'Hungarian'),
    (ICELANDIC, 'Icelandic'),
    (IGBO, 'Igbo'),
    (INDONESIAN, 'Indonesian'),
    (IRISH, 'Irish'),
    (ITALIAN, 'Italian'),
    (JAPANESE, 'Japanese'),
    (JAVANESE, 'Javanese'),
    (KANNADA, 'Kannada'),
    (KAZAKH, 'Kazakh'),
    (KOREAN, 'Korean'),
    (KURDISH, 'Kurdish'),
    (KYRGYZ, 'Kyrgyz'),
    (LAO, 'Lao'),
    (LATVIAN, 'Latvian'),
    (LITHUANIAN, 'Lithuanian'),
    (MACEDONIAN, 'Macedonian'),
    (MALAGASY, 'Malagasy'),
    (MALAY, 'Malay'),
    (MALAYALAM, 'Malayalam'),
    (MARATHI, 'Marathi'),
    (MONGOLIAN, 'Mongolian'),
    (NEPALI, 'Nepali'),
    (NORWEGIAN, 'Norwegian'),
    (ORIYA, 'Oriya'),
    (PASHTO, 'Pashto'),
    (PERSIAN, 'Persian'),
    (POLISH, 'Polish'),
    (PORTUGUESE, 'Portuguese'),
    (PUNJABI, 'Punjabi'),
    (ROMANIAN, 'Romanian'),
    (RUSSIAN, 'Russian'),
    (SERBIAN, 'Serbian'),
    (SINHALA, 'Sinhala'),
    (SLOVAK, 'Slovak'),
    (SLOVENIAN, 'Slovenian'),
    (SOMALI, 'Somali'),
    (SPANISH, 'Spanish'),
    (SWAHILI, 'Swahili'),
    (SWEDISH, 'Swedish'),
    (TAMIL, 'Tamil'),
    (TELUGU, 'Telugu'),
    (THAI, 'Thai'),
    (TURKISH, 'Turkish'),
    (UKRAINIAN, 'Ukrainian'),
    (URDU, 'Urdu'),
    (UZBEK, 'Uzbek'),
    (VIETNAMESE, 'Vietnamese'),
    (WELSH, 'Welsh'),
    (XHOSA, 'Xhosa'),
    (YORUBA, 'Yoruba'),
    (ZULU, 'Zulu'),
    (OTHER, 'Other'),
]


# Program Degree ---------------------------------------------------------------------------------
BACHELOR_OF_THEOLOGY = 'Bachelor of Theology (BTh)'
BACHELOR_OF_BIBLICAL_STUDIES = 'Bachelor of Biblical Studies (BBS)'
BACHELOR_OF_DIVINITY = 'Bachelor of Divinity (BDiv)'
BACHELOR_OF_ARTS_IN_RELIGIOUS_STUDIES = 'Bachelor of Arts in Religious Studies (BA)'
BACHELOR_OF_MINISTRY = 'Bachelor of Ministry (BMin)'
BACHELOR_OF_CHRISTIAN_COUNSELING = 'Bachelor of Christian Counseling (BCC)'
BACHELOR_OF_MISSIOLOGY = 'Bachelor of Missiology (BMis)'

MASTER_OF_DIVINITY = 'Master of Divinity (MDiv)'
MASTER_OF_THEOLOGY = 'Master of Theology (ThM)'
MASTER_OF_BIBLICAL_STUDIES = 'Master of Biblical Studies (MBS)'
MASTER_OF_MINISTRY = 'Master of Ministry (MMin)'
MASTER_OF_CHRISTIAN_COUNSELING = 'Master of Christian Counseling (MCC)'
MASTER_OF_APOLOGETICS = 'Master of Apologetics (MAp)'
MASTER_OF_MISSIOLOGY = 'Master of Missiology (MMis)'

DOCTOR_OF_THEOLOGY = 'Doctor of Theology (ThD)'
DOCTOR_OF_MINISTRY = 'Doctor of Ministry (DMin)'
DOCTOR_OF_PHILOSOPHY_IN_RELIGIOUS_STUDIES = 'Doctor of Philosophy in Religious Studies (PhD)'
DOCTOR_OF_APOLOGETICS = 'Doctor of Apologetics (DAp)'
DOCTOR_OF_MISSIOLOGY = 'Doctor of Missiology (DMis)'

DIPLOMA_IN_PASTORAL_MINISTRY = 'Diploma in Pastoral Ministry'
DIPLOMA_IN_BIBLICAL_STUDIES = 'Diploma in Biblical Studies'
DIPLOMA_IN_CHRISTIAN_COUNSELING = 'Diploma in Christian Counseling'
DIPLOMA_IN_APOLOGETICS = 'Diploma in Apologetics'
DIPLOMA_IN_MISSIOLOGY = 'Diploma in Missiology'

CERTIFICATE_IN_PASTORAL_MINISTRY = 'Certificate in Pastoral Ministry'
CERTIFICATE_IN_BIBLICAL_STUDIES = 'Certificate in Biblical Studies'
CERTIFICATE_IN_CHRISTIAN_COUNSELING = 'Certificate in Christian Counseling'
CERTIFICATE_IN_APOLOGETICS = 'Certificate in Apologetics'
CERTIFICATE_IN_MISSIOLOGY = 'Certificate in Missiology'

ASSOCIATE_DEGREE_IN_BIBLICAL_STUDIES = 'Associate Degree in Biblical Studies'
ASSOCIATE_DEGREE_IN_MINISTRY = 'Associate Degree in Ministry'
ASSOCIATE_DEGREE_IN_RELIGIOUS_STUDIES = 'Associate Degree in Religious Studies'
ASSOCIATE_DEGREE_IN_CHRISTIAN_COUNSELING = 'Associate Degree in Christian Counseling'

PROGRAM_NAME_CHOICES = [
    (BACHELOR_OF_THEOLOGY, 'Bachelor of Theology (BTh)'),
    (BACHELOR_OF_BIBLICAL_STUDIES, 'Bachelor of Biblical Studies (BBS)'),
    (BACHELOR_OF_DIVINITY, 'Bachelor of Divinity (BDiv)'),
    (BACHELOR_OF_ARTS_IN_RELIGIOUS_STUDIES, 'Bachelor of Arts in Religious Studies (BA)'),
    (BACHELOR_OF_MINISTRY, 'Bachelor of Ministry (BMin)'),
    (BACHELOR_OF_CHRISTIAN_COUNSELING, 'Bachelor of Christian Counseling (BCC)'),
    (BACHELOR_OF_MISSIOLOGY, 'Bachelor of Missiology (BMis)'),
    
    (MASTER_OF_DIVINITY, 'Master of Divinity (MDiv)'),
    (MASTER_OF_THEOLOGY, 'Master of Theology (ThM)'),
    (MASTER_OF_BIBLICAL_STUDIES, 'Master of Biblical Studies (MBS)'),
    (MASTER_OF_MINISTRY, 'Master of Ministry (MMin)'),
    (MASTER_OF_CHRISTIAN_COUNSELING, 'Master of Christian Counseling (MCC)'),
    (MASTER_OF_APOLOGETICS, 'Master of Apologetics (MAp)'),
    (MASTER_OF_MISSIOLOGY, 'Master of Missiology (MMis)'),

    (DOCTOR_OF_THEOLOGY, 'Doctor of Theology (ThD)'),
    (DOCTOR_OF_MINISTRY, 'Doctor of Ministry (DMin)'),
    (DOCTOR_OF_PHILOSOPHY_IN_RELIGIOUS_STUDIES, 'Doctor of Philosophy in Religious Studies (PhD)'),
    (DOCTOR_OF_APOLOGETICS, 'Doctor of Apologetics (DAp)'),
    (DOCTOR_OF_MISSIOLOGY, 'Doctor of Missiology (DMis)'),
    
    (DIPLOMA_IN_PASTORAL_MINISTRY, 'Diploma in Pastoral Ministry'),
    (DIPLOMA_IN_BIBLICAL_STUDIES, 'Diploma in Biblical Studies'),
    (DIPLOMA_IN_CHRISTIAN_COUNSELING, 'Diploma in Christian Counseling'),
    (DIPLOMA_IN_APOLOGETICS, 'Diploma in Apologetics'),
    (DIPLOMA_IN_MISSIOLOGY, 'Diploma in Missiology'),

    (CERTIFICATE_IN_PASTORAL_MINISTRY, 'Certificate in Pastoral Ministry'),
    (CERTIFICATE_IN_BIBLICAL_STUDIES, 'Certificate in Biblical Studies'),
    (CERTIFICATE_IN_CHRISTIAN_COUNSELING, 'Certificate in Christian Counseling'),
    (CERTIFICATE_IN_APOLOGETICS, 'Certificate in Apologetics'),
    (CERTIFICATE_IN_MISSIOLOGY, 'Certificate in Missiology'),

    (ASSOCIATE_DEGREE_IN_BIBLICAL_STUDIES, 'Associate Degree in Biblical Studies'),
    (ASSOCIATE_DEGREE_IN_MINISTRY, 'Associate Degree in Ministry'),
    (ASSOCIATE_DEGREE_IN_RELIGIOUS_STUDIES, 'Associate Degree in Religious Studies'),
    (ASSOCIATE_DEGREE_IN_CHRISTIAN_COUNSELING, 'Associate Degree in Christian Counseling'),
]


# Contry Choices --------------------------------------------------------------
AFGHANISTAN = 'AF'
ALBANIA = 'AL'
ALGERIA = 'DZ'
ANDORRA = 'AD'
ANGOLA = 'AO'
ANTIGUA_AND_BARBUDA = 'AG'
ARGENTINA = 'AR'
ARMENIA = 'AM'
AUSTRALIA = 'AU'
AUSTRIA = 'AT'
AZERBAIJAN = 'AZ'
BAHAMAS = 'BS'
BAHRAIN = 'BH'
BANGLADESH = 'BD'
BARBADOS = 'BB'
BELARUS = 'BY'
BELGIUM = 'BE'
BELIZE = 'BZ'
BENIN = 'BJ'
BHUTAN = 'BT'
BOLIVIA = 'BO'
BOSNIA_AND_HERZEGOVINA = 'BA'
BOTSWANA = 'BW'
BRAZIL = 'BR'
BRUNEI = 'BN'
BULGARIA = 'BG'
BURKINA_FASO = 'BF'
BURUNDI = 'BI'
CABO_VERDE = 'CV'
CAMBODIA = 'KH'
CAMEROON = 'CM'
CANADA = 'CA'
CENTRAL_AFRICAN_REPUBLIC = 'CF'
CHAD = 'TD'
CHILE = 'CL'
CHINA = 'CN'
COLOMBIA = 'CO'
COMOROS = 'KM'
CONGO = 'CG'
CONGO_DR = 'CD'
COSTA_RICA = 'CR'
CROATIA = 'HR'
CUBA = 'CU'
CYPRUS = 'CY'
CZECHIA = 'CZ'
DENMARK = 'DK'
DJIBOUTI = 'DJ'
DOMINICA = 'DM'
DOMINICAN_REPUBLIC = 'DO'
ECUADOR = 'EC'
EGYPT = 'EG'
EL_SALVADOR = 'SV'
EQUATORIAL_GUINEA = 'GQ'
ERITREA = 'ER'
ESTONIA = 'EE'
ESWATINI = 'SZ'
ETHIOPIA = 'ET'
FIJI = 'FJ'
FINLAND = 'FI'
FRANCE = 'FR'
GABON = 'GA'
GAMBIA = 'GM'
GEORGIA = 'GE'
GERMANY = 'DE'
GHANA = 'GH'
GREECE = 'GR'
GRENADA = 'GD'
GUATEMALA = 'GT'
GUINEA = 'GN'
GUINEA_BISSAU = 'GW'
GUYANA = 'GY'
HAITI = 'HT'
HOLY_SEE = 'VA'
HONDURAS = 'HN'
HUNGARY = 'HU'
ICELAND = 'IS'
INDIA = 'IN'
INDONESIA = 'ID'
IRAN = 'IR'
IRAQ = 'IQ'
IRELAND = 'IE'
ISRAEL = 'IL'
ITALY = 'IT'
IVORY_COAST = 'CI'
JAMAICA = 'JM'
JAPAN = 'JP'
JORDAN = 'JO'
KAZAKHSTAN = 'KZ'
KENYA = 'KE'
KIRIBATI = 'KI'
KOREA_NORTH = 'KP'
KOREA_SOUTH = 'KR'
KOSOVO = 'XK'
KUWAIT = 'KW'
KYRGYZSTAN = 'KG'
LAOS = 'LA'
LATVIA = 'LV'
LEBANON = 'LB'
LESOTHO = 'LS'
LIBERIA = 'LR'
LIBYA = 'LY'
LIECHTENSTEIN = 'LI'
LITHUANIA = 'LT'
LUXEMBOURG = 'LU'
MADAGASCAR = 'MG'
MALAWI = 'MW'
MALAYSIA = 'MY'
MALDIVES = 'MV'
MALI = 'ML'
MALTA = 'MT'
MARSHALL_ISLANDS = 'MH'
MAURITANIA = 'MR'
MAURITIUS = 'MU'
MEXICO = 'MX'
MICRONESIA = 'FM'
MOLDOVA = 'MD'
MONACO = 'MC'
MONGOLIA = 'MN'
MONTENEGRO = 'ME'
MOROCCO = 'MA'
MOZAMBIQUE = 'MZ'
MYANMAR = 'MM'
NAMIBIA = 'NA'
NAURU = 'NR'
NEPAL = 'NP'
NETHERLANDS = 'NL'
NEW_ZEALAND = 'NZ'
NICARAGUA = 'NI'
NIGER = 'NE'
NIGERIA = 'NG'
NORTH_MACEDONIA = 'MK'
NORWAY = 'NO'
OMAN = 'OM'
PAKISTAN = 'PK'
PALAU = 'PW'
PALESTINE = 'PS'
PANAMA = 'PA'
PAPUA_NEW_GUINEA = 'PG'
PARAGUAY = 'PY'
PERU = 'PE'
PHILIPPINES = 'PH'
POLAND = 'PL'
PORTUGAL = 'PT'
QATAR = 'QA'
ROMANIA = 'RO'
RUSSIA = 'RU'
RWANDA = 'RW'
SAINT_KITTS_AND_NEVIS = 'KN'
SAINT_LUCIA = 'LC'
SAINT_VINCENT_AND_THE_GRENADINES = 'VC'
SAMOA = 'WS'
SAN_MARINO = 'SM'
SAO_TOME_AND_PRINCIPE = 'ST'
SAUDI_ARABIA = 'SA'
SENEGAL = 'SN'
SERBIA = 'RS'
SEYCHELLES = 'SC'
SIERRA_LEONE = 'SL'
SINGAPORE = 'SG'
SLOVAKIA = 'SK'
SLOVENIA = 'SI'
SOLOMON_ISLANDS = 'SB'
SOMALIA = 'SO'
SOUTH_AFRICA = 'ZA'
SOUTH_SUDAN = 'SS'
SPAIN = 'ES'
SRI_LANKA = 'LK'
SUDAN = 'SD'
SURINAME = 'SR'
SWEDEN = 'SE'
SWITZERLAND = 'CH'
SYRIA = 'SY'
TAIWAN = 'TW'
TAJIKISTAN = 'TJ'
TANZANIA = 'TZ'
THAILAND = 'TH'
TIMOR_LESTE = 'TL'
TOGO = 'TG'
TONGA = 'TO'
TRINIDAD_AND_TOBAGO = 'TT'
TUNISIA = 'TN'
TURKEY = 'TR'
TURKMENISTAN = 'TM'
TUVALU = 'TV'
UGANDA = 'UG'
UKRAINE = 'UA'
UNITED_ARAB_EMIRATES = 'AE'
UNITED_KINGDOM = 'GB'
UNITED_STATES = 'US'
URUGUAY = 'UY'
UZBEKISTAN = 'UZ'
VANUATU = 'VU'
VENEZUELA = 'VE'
VIETNAM = 'VN'
YEMEN = 'YE'
ZAMBIA = 'ZM'
ZIMBABWE = 'ZW'

COUNTRY_CHOICES = [
    (AFGHANISTAN, 'Afghanistan'),
    (ALBANIA, 'Albania'),
    (ALGERIA, 'Algeria'),
    (ANDORRA, 'Andorra'),
    (ANGOLA, 'Angola'),
    (ANTIGUA_AND_BARBUDA, 'Antigua and Barbuda'),
    (ARGENTINA, 'Argentina'),
    (ARMENIA, 'Armenia'),
    (AUSTRALIA, 'Australia'),
    (AUSTRIA, 'Austria'),
    (AZERBAIJAN, 'Azerbaijan'),
    (BAHAMAS, 'Bahamas'),
    (BAHRAIN, 'Bahrain'),
    (BANGLADESH, 'Bangladesh'),
    (BARBADOS, 'Barbados'),
    (BELARUS, 'Belarus'),
    (BELGIUM, 'Belgium'),
    (BELIZE, 'Belize'),
    (BENIN, 'Benin'),
    (BHUTAN, 'Bhutan'),
    (BOLIVIA, 'Bolivia'),
    (BOSNIA_AND_HERZEGOVINA, 'Bosnia and Herzegovina'),
    (BOTSWANA, 'Botswana'),
    (BRAZIL, 'Brazil'),
    (BRUNEI, 'Brunei'),
    (BULGARIA, 'Bulgaria'),
    (BURKINA_FASO, 'Burkina Faso'),
    (BURUNDI, 'Burundi'),
    (CABO_VERDE, 'Cabo Verde'),
    (CAMBODIA, 'Cambodia'),
    (CAMEROON, 'Cameroon'),
    (CANADA, 'Canada'),
    (CENTRAL_AFRICAN_REPUBLIC, 'Central African Republic'),
    (CHAD, 'Chad'),
    (CHILE, 'Chile'),
    (CHINA, 'China'),
    (COLOMBIA, 'Colombia'),
    (COMOROS, 'Comoros'),
    (CONGO, 'Congo'),
    (COSTA_RICA, 'Costa Rica'),
    (CROATIA, 'Croatia'),
    (CUBA, 'Cuba'),
    (CYPRUS, 'Cyprus'),
    (CZECHIA, 'Czechia'),
    (DENMARK, 'Denmark'),
    (DJIBOUTI, 'Djibouti'),
    (DOMINICA, 'Dominica'),
    (DOMINICAN_REPUBLIC, 'Dominican Republic'),
    (ECUADOR, 'Ecuador'),
    (EGYPT, 'Egypt'),
    (EL_SALVADOR, 'El Salvador'),
    (EQUATORIAL_GUINEA, 'Equatorial Guinea'),
    (ERITREA, 'Eritrea'),
    (ESTONIA, 'Estonia'),
    (ESWATINI, 'Eswatini'),
    (ETHIOPIA, 'Ethiopia'),
    (FIJI, 'Fiji'),
    (FINLAND, 'Finland'),
    (FRANCE, 'France'),
    (GABON, 'Gabon'),
    (GAMBIA, 'Gambia'),
    (GEORGIA, 'Georgia'),
    (GERMANY, 'Germany'),
    (GHANA, 'Ghana'),
    (GREECE, 'Greece'),
    (GRENADA, 'Grenada'),
    (GUATEMALA, 'Guatemala'),
    (GUINEA, 'Guinea'),
    (GUINEA_BISSAU, 'Guinea-Bissau'),
    (GUYANA, 'Guyana'),
    (HAITI, 'Haiti'),
    (HOLY_SEE, 'Holy See'),
    (HONDURAS, 'Honduras'),
    (HUNGARY, 'Hungary'),
    (ICELAND, 'Iceland'),
    (INDIA, 'India'),
    (INDONESIA, 'Indonesia'),
    (IRAN, 'Iran'),
    (IRAQ, 'Iraq'),
    (IRELAND, 'Ireland'),
    (ISRAEL, 'Israel'),
    (ITALY, 'Italy'),
    (JAMAICA, 'Jamaica'),
    (JAPAN, 'Japan'),
    (JORDAN, 'Jordan'),
    (KAZAKHSTAN, 'Kazakhstan'),
    (KENYA, 'Kenya'),
    (KIRIBATI, 'Kiribati'),
    (KOREA_NORTH, 'Korea (North)'),
    (KOREA_SOUTH, 'Korea (South)'),
    (KOSOVO, 'Kosovo'),
    (KUWAIT, 'Kuwait'),
    (KYRGYZSTAN, 'Kyrgyzstan'),
    (LAOS, 'Laos'),
    (LATVIA, 'Latvia'),
    (LEBANON, 'Lebanon'),
    (LESOTHO, 'Lesotho'),
    (LIBERIA, 'Liberia'),
    (LIBYA, 'Libya'),
    (LIECHTENSTEIN, 'Liechtenstein'),
    (LITHUANIA, 'Lithuania'),
    (LUXEMBOURG, 'Luxembourg'),
    (MADAGASCAR, 'Madagascar'),
    (MALAWI, 'Malawi'),
    (MALAYSIA, 'Malaysia'),
    (MALDIVES, 'Maldives'),
    (MALI, 'Mali'),
    (MALTA, 'Malta'),
    (MARSHALL_ISLANDS, 'Marshall Islands'),
    (MAURITANIA, 'Mauritania'),
    (MAURITIUS, 'Mauritius'),
    (MEXICO, 'Mexico'),
    (MICRONESIA, 'Micronesia'),
    (MOLDOVA, 'Moldova'),
    (MONACO, 'Monaco'),
    (MONGOLIA, 'Mongolia'),
    (MONTENEGRO, 'Montenegro'),
    (MOROCCO, 'Morocco'),
    (MOZAMBIQUE, 'Mozambique'),
    (MYANMAR, 'Myanmar'),
    (NAMIBIA, 'Namibia'),
    (NAURU, 'Nauru'),
    (NEPAL, 'Nepal'),
    (NETHERLANDS, 'Netherlands'),
    (NEW_ZEALAND, 'New Zealand'),
    (NICARAGUA, 'Nicaragua'),
    (NIGER, 'Niger'),
    (NIGERIA, 'Nigeria'),
    (NORTH_MACEDONIA, 'North Macedonia'),
    (NORWAY, 'Norway'),
    (OMAN, 'Oman'),
    (PAKISTAN, 'Pakistan'),
    (PALAU, 'Palau'),
    (PALESTINE, 'Palestine'),
    (PANAMA, 'Panama'),
    (PAPUA_NEW_GUINEA, 'Papua New Guinea'),
    (PARAGUAY, 'Paraguay'),
    (PERU, 'Peru'),
    (PHILIPPINES, 'Philippines'),
    (POLAND, 'Poland'),
    (PORTUGAL, 'Portugal'),
    (QATAR, 'Qatar'),
    (ROMANIA, 'Romania'),
    (RUSSIA, 'Russia'),
    (RWANDA, 'Rwanda'),
    (SAINT_KITTS_AND_NEVIS, 'Saint Kitts and Nevis'),
    (SAINT_LUCIA, 'Saint Lucia'),
    (SAINT_VINCENT_AND_THE_GRENADINES, 'Saint Vincent and the Grenadines'),
    (SAMOA, 'Samoa'),
    (SAN_MARINO, 'San Marino'),
    (SAO_TOME_AND_PRINCIPE, 'Sao Tome and Principe'),
    (SAUDI_ARABIA, 'Saudi Arabia'),
    (SENEGAL, 'Senegal'),
    (SERBIA, 'Serbia'),
    (SEYCHELLES, 'Seychelles'),
    (SIERRA_LEONE, 'Sierra Leone'),
    (SINGAPORE, 'Singapore'),
    (SLOVAKIA, 'Slovakia'),
    (SLOVENIA, 'Slovenia'),
    (SOLOMON_ISLANDS, 'Solomon Islands'),
    (SOMALIA, 'Somalia'),
    (SOUTH_AFRICA, 'South Africa'),
    (SOUTH_SUDAN, 'South Sudan'),
    (SPAIN, 'Spain'),
    (SRI_LANKA, 'Sri Lanka'),
    (SUDAN, 'Sudan'),
    (SURINAME, 'Suriname'),
    (SWEDEN, 'Sweden'),
    (SWITZERLAND, 'Switzerland'),
    (SYRIA, 'Syria'),
    (TAIWAN, 'Taiwan'),
    (TAJIKISTAN, 'Tajikistan'),
    (TANZANIA, 'Tanzania'),
    (THAILAND, 'Thailand'),
    (TIMOR_LESTE, 'Timor-Leste'),
    (TOGO, 'Togo'),
    (TONGA, 'Tonga'),
    (TRINIDAD_AND_TOBAGO, 'Trinidad and Tobago'),
    (TUNISIA, 'Tunisia'),
    (TURKEY, 'Turkey'),
    (TURKMENISTAN, 'Turkmenistan'),
    (TUVALU, 'Tuvalu'),
    (UGANDA, 'Uganda'),
    (UKRAINE, 'Ukraine'),
    (UNITED_ARAB_EMIRATES, 'United Arab Emirates'),
    (UNITED_KINGDOM, 'United Kingdom'),
    (UNITED_STATES, 'United States'),
    (URUGUAY, 'Uruguay'),
    (UZBEKISTAN, 'Uzbekistan'),
    (VANUATU, 'Vanuatu'),
    (VENEZUELA, 'Venezuela'),
    (VIETNAM, 'Vietnam'),
    (YEMEN, 'Yemen'),
    (ZAMBIA, 'Zambia'),
    (ZIMBABWE, 'Zimbabwe'),
]