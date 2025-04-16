# Friendship status Choices -------------------------------------------------------------------------------
PENDING = 'pending'
ACCEPTED = 'accepted'
DECLINED = 'declined'
CANCELLED = 'cancelled'
DELETED = 'deleted'
FRIENDSHIP_STATUS_CHOICES = [
    (PENDING, 'Pending'),
    (ACCEPTED, 'Accepted'),
    (DECLINED, 'Declined'),
    (CANCELLED, 'Cancelled'),
    (DELETED, 'Deleted'),
]


# Fellowship Relationship Choices ----------------------------------------------------------------------
FATHER = 'Father'
MOTHER = 'Mother'
SON = 'Son'
DAUGHTER = 'Daughter'
HUSBAND = 'Husband'
WIFE = 'Wife'
CONFIDANT = 'Confidant'
PASTOR = 'Pastor'
MENTOR = 'Mentor'
FELLOWSHIP_RELATIONSHIP_CHOICES = [
    (FATHER, 'Father'),
    (MOTHER, 'Mother'),
    (SON, 'Son'),
    (DAUGHTER, 'Daughter'),
    (HUSBAND, 'Husband'),
    (WIFE, 'Wife'),
    (CONFIDANT, 'Confidant'),
    (PASTOR, 'Pastor'),
    (MENTOR, 'Mentor'),
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


# Migration Choices --------------------------------------------------------------------------------
GUEST_TO_MEMBER = 'guest_to_member'
MEMBER_TO_GUEST = 'member_to_guest'
MIGRATION_CHOICES = [
    (GUEST_TO_MEMBER, 'GuestUser to Member'),
    (MEMBER_TO_GUEST, 'Member to GuestUser'),
]


# Identity Verification Status Types ---------------------------------------------------------------
NOT_SUBMITTED = 'not_submitted'
PENDING_REVIEW = 'pending_review'
VERIFIED = 'verified'
REJECTED = 'rejected'
IDENTITY_VERIFICATION_STATUS_CHOICES = [
    (NOT_SUBMITTED, 'Not Submitted'),
    (PENDING_REVIEW, 'Pending Review'),
    (VERIFIED, 'Verified'),
    (REJECTED, 'Rejected'),
]


# CUSTOMER DEACTIVATION REASON Choices For CUSTOMER ----------------------------------------------------
USER_REQUEST = 'user_request'
PAYMENT_ISSUE = 'payment_issue'
ACCOUNT_SUSPENSION = 'account_suspension'
INACTIVITY = 'inactivity'
SECURITY_CONCERNS = 'security_concerns'
VIOLATION_OF_TERMS = 'violation_of_terms'
OTHER = 'other'
CUSTOMER_DEACTIVATION_REASON_CHOICES = [
    (USER_REQUEST, 'User Request'),
    (PAYMENT_ISSUE, 'Payment Issue'),
    (ACCOUNT_SUSPENSION, 'Account Suspension'),
    (INACTIVITY, 'Inactivity'),
    (SECURITY_CONCERNS, 'Security Concerns'),
    (VIOLATION_OF_TERMS, 'Violation of Terms'),
    (OTHER, 'Other'),
]


# Document Types ----------------------------------------------------------------------------------
TRANSCRIPT = 'Transcript'
DIPLOMA = 'Diploma'
CERTIFICATE = 'Certificate'
COURSE_COMPLETION_CERTIFICATE = 'Course Completion Certificate'
DEGREE_CERTIFICATE = 'Degree Certificate'
LICENSURE = 'Licensure'
ORDINATION_CERTIFICATE = 'Ordination Certificate'
EDUCATION_DOCUMENT_TYPE_CHOICES = [
    (TRANSCRIPT, 'Transcript'),
    (DIPLOMA, 'Diploma'),
    (CERTIFICATE, 'Certificate'),
    (COURSE_COMPLETION_CERTIFICATE, 'Course Completion Certificate'),
    (DEGREE_CERTIFICATE, 'Degree Certificate'),
    (LICENSURE, 'Licensure'),
    (ORDINATION_CERTIFICATE, 'Ordination Certificate'),
]


# Document Degree ---------------------------------------------------------------------------------
BACHELOR_OF_THEOLOGY = 'Bachelor of Theology (BTh)'
MASTER_OF_DIVINITY = 'Master of Divinity (MDiv)'
DOCTOR_OF_THEOLOGY = 'Doctor of Theology (ThD)'
BACHELOR_OF_ARTS = 'Bachelor of Arts (BA)'
MASTER_OF_SCIENCE = 'Master of Science (MSc)'
DOCTOR_OF_PHILOSOPHY = 'Doctor of Philosophy (PhD)'
DIPLOMA_IN_PASTORAL_MINISTRY = 'Diploma in Pastoral Ministry'
ASSOCIATE_DEGREE_BIBLICAL_STUDIES = 'Associate Degree in Biblical Studies'
ADVANCED_DIPLOMA_CHRISTIAN_COUNSELING = 'Advanced Diploma in Christian Counseling'
POSTGRADUATE_CERTIFICATE_RELIGIOUS_STUDIES = 'Postgraduate Certificate in Religious Studies'
EDUCATION_DEGREE_CHOICES = [
    (BACHELOR_OF_THEOLOGY, 'Bachelor of Theology (BTh)'),
    (MASTER_OF_DIVINITY, 'Master of Divinity (MDiv)'),
    (DOCTOR_OF_THEOLOGY, 'Doctor of Theology (ThD)'),
    (BACHELOR_OF_ARTS, 'Bachelor of Arts (BA)'),
    (MASTER_OF_SCIENCE, 'Master of Science (MSc)'),
    (DOCTOR_OF_PHILOSOPHY, 'Doctor of Philosophy (PhD)'),
    (DIPLOMA_IN_PASTORAL_MINISTRY, 'Diploma in Pastoral Ministry'),
    (ASSOCIATE_DEGREE_BIBLICAL_STUDIES, 'Associate Degree in Biblical Studies'),
    (ADVANCED_DIPLOMA_CHRISTIAN_COUNSELING, 'Advanced Diploma in Christian Counseling'),
    (POSTGRADUATE_CERTIFICATE_RELIGIOUS_STUDIES, 'Postgraduate Certificate in Religious Studies'),
]