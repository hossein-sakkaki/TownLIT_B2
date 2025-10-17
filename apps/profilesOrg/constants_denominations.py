# apps/profilesOrg/constants_denominations.py

# --- Main branches (required) ---
ROMAN_CATHOLICISM = 'roman_catholicism'
EASTERN_ORTHODOXY = 'eastern_orthodoxy'
ORIENTAL_ORTHODOXY = 'oriental_orthodoxy'      # fix snake_case
CHURCH_OF_THE_EAST = 'church_of_the_east'
PROTESTANTISM = 'protestantism'
OLD_CATHOLICISM = 'old_catholicism'

CHURCH_BRANCH_CHOICES = [
    (ROMAN_CATHOLICISM, 'Catholic (Roman & Eastern Catholic in communion)'),
    (EASTERN_ORTHODOXY, 'Eastern Orthodoxy'),
    (ORIENTAL_ORTHODOXY, 'Oriental Orthodoxy'),
    (CHURCH_OF_THE_EAST, 'Church of the East'),
    (PROTESTANTISM, 'Protestant'),
    (OLD_CATHOLICISM, 'Old Catholic'),
]

# --- Protestant families (optional) ---
LUTHERANISM = 'lutheranism'
CALVINISM_OR_REFORMED = 'calvinism_or_reformed'
ANGLICANISM = 'anglicanism'
METHODISM = 'methodism'
BAPTIST = 'baptist'  # fixed
PRESBYTERIANISM = 'presbyterianism'
PENTECOSTALISM = 'pentecostalism'
ADVENTISM = 'adventism'
ANABAPTISM = 'anabaptism'
CONGREGATIONALISM = 'congregationalism'
PIETIST_MORAVIAN = 'pietist_moravian'
QUAKER_FRIENDS = 'quaker_friends'
RESTORATIONIST_STONE_CAMPBELL = 'restorationist_stone_campbell'
WESLEYAN_HOLINESS = 'wesleyan_holiness'
EVANGELICAL_NONDENOM = 'evangelical_nondenominational'
CHARISMATIC_NONDENOM = 'charismatic_nondenominational'

PROTESTANT_FAMILY_CHOICES = [
    (ANGLICANISM, 'Anglican'),
    (LUTHERANISM, 'Lutheran'),
    (CALVINISM_OR_REFORMED, 'Reformed/Calvinist'),
    (PRESBYTERIANISM, 'Presbyterian'),
    (CONGREGATIONALISM, 'Congregational'),
    (METHODISM, 'Methodist/Wesleyan'),
    (WESLEYAN_HOLINESS, 'Wesleyan Holiness'),
    (BAPTIST, 'Baptist'),
    (ANABAPTISM, 'Anabaptist (Mennonite/Amish/Hutterite)'),
    (PIETIST_MORAVIAN, 'Pietist/Moravian'),
    (QUAKER_FRIENDS, 'Friends (Quaker)'),
    (RESTORATIONIST_STONE_CAMPBELL, 'Restorationist (Stone-Campbell)'),
    (ADVENTISM, 'Adventist'),
    (PENTECOSTALISM, 'Pentecostal'),
    (CHARISMATIC_NONDENOM, 'Charismatic (Non-denominational)'),
    (EVANGELICAL_NONDENOM, 'Evangelical (Non-denominational)'),
]

# --- Catholic families (optional, in-communion with Rome) ---
EASTERN_CATHOLIC_CHURCHES = 'eastern_catholic_churches'  # umbrella for Byzantine/Alexandrian/etc.
LATIN_RITE = 'latin_rite'
BYZANTINE_CATHOLIC = 'byzantine_catholic'
ALEXANDRIAN_COPTIC_CATHOLIC = 'alexandrian_coptic_catholic'
ANTIOCHIAN_WEST_SYRIAC_CATHOLIC = 'antiochian_west_syriac_catholic'
EAST_SYRIAC_CHALDEAN_CATHOLIC = 'east_syriac_chaldean_catholic'
ARMENIAN_CATHOLIC = 'armenian_catholic'

CATHOLIC_FAMILY_CHOICES = [
    (LATIN_RITE, 'Catholic – Latin (Roman) Rite'),
    (BYZANTINE_CATHOLIC, 'Catholic – Byzantine (Eastern Catholic)'),
    (ALEXANDRIAN_COPTIC_CATHOLIC, 'Catholic – Alexandrian/Coptic Catholic'),
    (ANTIOCHIAN_WEST_SYRIAC_CATHOLIC, 'Catholic – Antiochian/West Syriac (Syriac/Maronite)'),
    (EAST_SYRIAC_CHALDEAN_CATHOLIC, 'Catholic – East Syriac (Chaldean/Syro-Malabar)'),
    (ARMENIAN_CATHOLIC, 'Catholic – Armenian Catholic'),
    (EASTERN_CATHOLIC_CHURCHES, 'Catholic – Eastern Catholic (General)'),
]

# --- Eastern Orthodox families (optional) ---
EO_GREEK = 'eo_greek'
EO_RUSSIAN = 'eo_russian'
EO_SERBIAN = 'eo_serbian'
EO_ROMANIAN = 'eo_romanian'
EO_BULGARIAN = 'eo_bulgarian'
EO_GEORGIAN = 'eo_georgian'
EO_ANTIOCHIAN = 'eo_antiochian'
EO_OCA = 'eo_oca'
EO_OTHER_AUTOCEPHALOUS = 'eo_other_autocephalous'

EASTERN_ORTHODOX_FAMILY_CHOICES = [
    (EO_GREEK, 'Eastern Orthodox – Greek'),
    (EO_RUSSIAN, 'Eastern Orthodox – Russian'),
    (EO_SERBIAN, 'Eastern Orthodox – Serbian'),
    (EO_ROMANIAN, 'Eastern Orthodox – Romanian'),
    (EO_BULGARIAN, 'Eastern Orthodox – Bulgarian'),
    (EO_GEORGIAN, 'Eastern Orthodox – Georgian'),
    (EO_ANTIOCHIAN, 'Eastern Orthodox – Antiochian'),
    (EO_OCA, 'Eastern Orthodox – Orthodox Church in America'),
    (EO_OTHER_AUTOCEPHALOUS, 'Eastern Orthodox – Other Autocephalous'),
]

# --- Oriental Orthodox families (optional) ---
OO_COPTIC = 'oo_coptic'
OO_ARMENIAN_APOSTOLIC = 'oo_armenian_apostolic'
OO_SYRIAC = 'oo_syriac'
OO_ETHIOPIAN = 'oo_ethiopian'
OO_ERITREAN = 'oo_eritrean'
OO_MALANKARA_INDIAN = 'oo_malankara_indian'

ORIENTAL_ORTHODOX_FAMILY_CHOICES = [
    (OO_COPTIC, 'Oriental Orthodox – Coptic'),
    (OO_ARMENIAN_APOSTOLIC, 'Oriental Orthodox – Armenian Apostolic'),
    (OO_SYRIAC, 'Oriental Orthodox – Syriac'),
    (OO_ETHIOPIAN, 'Oriental Orthodox – Ethiopian'),
    (OO_ERITREAN, 'Oriental Orthodox – Eritrean'),
    (OO_MALANKARA_INDIAN, 'Oriental Orthodox – Malankara (Indian)'),
]

# --- Church of the East families (optional) ---
COE_ASSYRIAN = 'coe_assyrian'
COE_ANCIENT = 'coe_ancient'

CHURCH_OF_THE_EAST_FAMILY_CHOICES = [
    (COE_ASSYRIAN, 'Church of the East – Assyrian'),
    (COE_ANCIENT, 'Church of the East – Ancient Church of the East'),
]

# --- Old Catholic families (optional) ---
OC_UTRECHT = 'oc_union_of_utrecht'
OC_OTHER = 'oc_other_old_catholic'

OLD_CATHOLIC_FAMILY_CHOICES = [
    (OC_UTRECHT, 'Old Catholic – Union of Utrecht'),
    (OC_OTHER, 'Old Catholic – Other Old Catholic'),
]

# --- Aggregated "all families" for field choices ---
CHURCH_FAMILY_CHOICES_ALL = (
    PROTESTANT_FAMILY_CHOICES
    + CATHOLIC_FAMILY_CHOICES
    + EASTERN_ORTHODOX_FAMILY_CHOICES
    + ORIENTAL_ORTHODOX_FAMILY_CHOICES
    + CHURCH_OF_THE_EAST_FAMILY_CHOICES
    + OLD_CATHOLIC_FAMILY_CHOICES
)

# --- Constraint map: which families belong to which branch ---
FAMILIES_BY_BRANCH = {
    PROTESTANTISM: {k for k, _ in PROTESTANT_FAMILY_CHOICES},
    ROMAN_CATHOLICISM: {k for k, _ in CATHOLIC_FAMILY_CHOICES},
    EASTERN_ORTHODOXY: {k for k, _ in EASTERN_ORTHODOX_FAMILY_CHOICES},
    ORIENTAL_ORTHODOXY: {k for k, _ in ORIENTAL_ORTHODOX_FAMILY_CHOICES},
    CHURCH_OF_THE_EAST: {k for k, _ in CHURCH_OF_THE_EAST_FAMILY_CHOICES},
    OLD_CATHOLICISM: {k for k, _ in OLD_CATHOLIC_FAMILY_CHOICES},
}
