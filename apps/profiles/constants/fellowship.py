# apps/profiles/constants/fellowship.py


# Fellowship Relationship Choices ----------------------------------------------------------------------
HUSBAND = 'Husband'
WIFE = 'Wife'
FATHER = 'Father'
MOTHER = 'Mother'
SON = 'Son'
DAUGHTER = 'Daughter'
CONFIDANT = 'Confidant'
PASTOR = 'Pastor' 
MENTOR = 'Mentor'
FELLOWSHIP_RELATIONSHIP_CHOICES = [
    (HUSBAND, 'He is my Husband'),
    (WIFE, 'She is my Wife'),
    (FATHER, 'He is my Father'),
    (MOTHER, 'She is my Mother'),
    (SON, 'He is my Son'),
    (DAUGHTER, 'She is my Daughter'),
    (CONFIDANT, 'My Trusted Confidant'),
    (PASTOR, 'My Spiritual Pastor'),
    (MENTOR, 'My Mentor and Guide'),
]


# Reciprocal Fellowship Relationship Choices --------------------------------------------------------
FATHER = 'Father'
MOTHER = 'Mother'
SON = 'Son'
DAUGHTER = 'Daughter'
HUSBAND = 'Husband'
WIFE = 'Wife'
CONFIDANT = 'Confidant'
PASTOR = 'Pastor'
MENTOR = 'Mentor'
DISCIPLE = 'Disciple'
MENTEE = 'Mentee'
ENTRUSTED = 'Entrusted'
RECIPROCAL_FELLOWSHIP_CHOICES = [
    (FATHER, 'Father'),
    (MOTHER, 'Mother'),
    (SON, 'Son'),
    (DAUGHTER, 'Daughter'),
    (HUSBAND, 'Husband'),
    (WIFE, 'Wife'),
    (CONFIDANT, 'Confidant'),
    (PASTOR, 'Pastor'),
    (MENTOR, 'Mentor'),
    (DISCIPLE, 'Disciple'),
    (MENTEE, 'Mentee'),
    (ENTRUSTED, 'Entrusted'),
]

# MAP
RECIPROCAL_FELLOWSHIP_MAP = {
    'Father': 'Son',
    'Mother': 'Daughter',
    'Son': 'Father',
    'Daughter': 'Mother',
    'Husband': 'Wife',
    'Wife': 'Husband',
    'Confidant': 'Entrusted',
    'Pastor': 'Disciple',
    'Mentor': 'Mentee',
    'Disciple': 'Pastor',
    'Mentee': 'Mentor',
    'Entrusted': 'Confidant',
}


# Family status Choices -------------------------------------------------------------------------------
PENDING = 'Pending'
ACCEPTED = 'Accepted'
DECLINED = 'Declined'
CANCELLED = 'Cancelled'
FELLOWSHIP_STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (ACCEPTED, 'Accepted'),
    (DECLINED, 'Declined'),
    (CANCELLED, 'Cancelled'),
]
