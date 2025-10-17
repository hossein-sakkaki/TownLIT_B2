from apps.moderation.constants import (
    COLLABORATION_TYPE_CHOICES, COLLABORATION_MODE_CHOICES,
    COLLABORATION_AVAILABILITY_CHOICES, HEAR_ABOUT_US_CHOICES
)

from apps.conversation.constants import (
    MESSAGE_POLICY_CHOICES,
    DELETE_POLICY_CHOICES,
)

# Import accounts_costants
from apps.accounts.constants import (
    SOCIAL_MEDIA_CHOICES,
    GENDER_CHOICES,
    USER_LABEL_CHOICES,
    ADDRESS_TYPE_CHOICES,
)

from apps.main.constants import (
    TERMS_AND_POLICIES_CHOICES,
    LOG_ACTION_CHOICES,
)

# Import profiles_constants
from apps.profiles.constants import (
    FRIENDSHIP_STATUS_CHOICES,
    FELLOWSHIP_RELATIONSHIP_CHOICES,
    RECIPROCAL_FELLOWSHIP_CHOICES,
    FELLOWSHIP_STATUS_CHOICES,
    MIGRATION_CHOICES,
    IDENTITY_VERIFICATION_STATUS_CHOICES,
    CUSTOMER_DEACTIVATION_REASON_CHOICES,
    EDUCATION_DOCUMENT_TYPE_CHOICES,
    EDUCATION_DEGREE_CHOICES,
    SPIRITUAL_MINISTRY_CHOICES,
)

from apps.profilesOrg.constants_denominations import (
    CHURCH_BRANCH_CHOICES, CHURCH_FAMILY_CHOICES_ALL, FAMILIES_BY_BRANCH
)

# Import organizations
from apps.profilesOrg.constants import (
    ORGANIZATION_TYPE_CHOICES,
    ACCESS_LEVEL_CHOICES,
    PRICE_TYPE_CHOICES,
    INSTITUTION_TYPE_CHOICES,
    VOTING_TYPE_CHOICES,
    VOTING_RESULT_CHOICES,
    COUNSELING_SERVICE_CHOICES,
    WORSHIP_STYLE_CHOICES,
    LANGUAGE_CHOICES,
    PROGRAM_NAME_CHOICES,
    COUNTRY_CHOICES,
    TIMEZONE_CHOICES,
    CHURCH_DENOMINATIONS_CHOICES,
    ORGANIZATION_SERVICE_CATEGORY_CHOICES,
    
)

# Import Gift
from apps.profiles.gift_constants import GIFT_LANGUAGE_CHOICES, GIFT_ANSWER_LABELS

# Import payments
from apps.payment.constants import (
    PAYMENT_STATUS_CHOICES,
    SUBSCRIPTION_TYPE_CHOICES,
    SUBSCRIPTION_PRICING_TYPE_CHOICES,
    ADVERTISEMENT_TYPE_CHOICES,
    PRICING_TYPE_CHOICES,
    DURATION_CHOICES,
    BILLING_CYCLE_CHOICES,
)

# Import posts
from apps.posts.constants import (
    SERVICE_EVENT_CHOICES,
    CHILDREN_EVENT_TYPE_CHOICES,
    YOUTH_EVENT_TYPE_CHOICES,
    WOMEN_EVENT_TYPE_CHOICES,
    MEN_EVENT_TYPE_CHOICES,
    MEDIA_CONTENT_CHOICES,
    LITERARY_CATEGORY_CHOICES,
    RESOURCE_TYPE_CHOICES,
    COPYRIGHT_CHOICES,
    DAYS_OF_WEEK_CHOICES,
    FREQUENCY_CHOICES,
    REACTION_TYPE_CHOICES,
    DELIVERY_METHOD_CHOICES,
)

# Import sanctuary_constants
from apps.sanctuary.constants import (
    POST_REPORT_CHOICES,
    ACCOUNT_REPORT_CHOICES,
    ORGANIZATION_REPORT_CHOICES,
    POST_ADMIN_REVIEW_CATEGORIES,
    ACCOUNT_ADMIN_REVIEW_CATEGORIES,
    ORGANIZATION_ADMIN_REVIEW_CATEGORIES,
    SENSITIVE_CATEGORIES,
    REQUEST_TYPE_CHOICES,
    REQUEST_STATUS_CHOICES,
    REVIEW_STATUS_CHOICES,
    OUTCOME_CHOICES,
)

# Import store_constants
from apps.store.store_constants import (
    STORE_PRODUCT_CATEGORY_CHOICES,
    CURRENCY_CHOICES,
)

# Import orders_constants
from apps.orders.constants import (
    ORDER_STATUS_CHOICES,
    DELIVERY_ORDER_STATUS_CHOICES,
    RETURN_ORDER_STATUS_CHOICES,
)

from apps.products.constants import SELLING_TYPE_CHOICES


# Centralized CHOICES_MAP
CHOICES_MAP = {
    # General constants
    'gender': GENDER_CHOICES,
    'delivery_method': DELIVERY_METHOD_CHOICES,
    'selling_type': SELLING_TYPE_CHOICES,
    'address_type': ADDRESS_TYPE_CHOICES,
    'copyright': COPYRIGHT_CHOICES,
    'timezones': TIMEZONE_CHOICES,
    'days_of_week': DAYS_OF_WEEK_CHOICES,
    'frequency': FREQUENCY_CHOICES,
    'message_policy': MESSAGE_POLICY_CHOICES,
    'reaction_type': REACTION_TYPE_CHOICES,
    'church_denominations': CHURCH_DENOMINATIONS_CHOICES,
    'user_label': USER_LABEL_CHOICES,
    'organization_service_category': ORGANIZATION_SERVICE_CATEGORY_CHOICES,
    'spiritual_ministry': SPIRITUAL_MINISTRY_CHOICES,
    'terms_and_policies': TERMS_AND_POLICIES_CHOICES,
    'log_action': LOG_ACTION_CHOICES,
    
    # Moderation
    'collaboration_type' :COLLABORATION_TYPE_CHOICES, 
    'collaboration_mode' :COLLABORATION_MODE_CHOICES,
    'collaboration_availability': COLLABORATION_AVAILABILITY_CHOICES,
    'how_found_us': HEAR_ABOUT_US_CHOICES,
    
    # Account constants
    'social_media': SOCIAL_MEDIA_CHOICES,

    # Profiles constants
    'friendship_status': FRIENDSHIP_STATUS_CHOICES,
    'fellowship_status': FELLOWSHIP_STATUS_CHOICES,
    'fellowship_relationship': FELLOWSHIP_RELATIONSHIP_CHOICES,
    'reciprocal_fellowship_relationship': RECIPROCAL_FELLOWSHIP_CHOICES,
    'migration_choices': MIGRATION_CHOICES,
    'identity_verification_status': IDENTITY_VERIFICATION_STATUS_CHOICES,
    'customer_deactivation_reason': CUSTOMER_DEACTIVATION_REASON_CHOICES,
    'education_document_type': EDUCATION_DOCUMENT_TYPE_CHOICES,
    'education_degree': EDUCATION_DEGREE_CHOICES,

    # Organizations constants
    "church_denominations_branch": CHURCH_BRANCH_CHOICES,
    "church_denominations_family": CHURCH_FAMILY_CHOICES_ALL,
    # 'organization_type': ORGANIZATION_TYPE_CHOICES,
    'access_level': ACCESS_LEVEL_CHOICES,
    'price_type': PRICE_TYPE_CHOICES,
    'institution_type': INSTITUTION_TYPE_CHOICES,
    'voting_type': VOTING_TYPE_CHOICES,
    'voting_result': VOTING_RESULT_CHOICES,
    'counseling_service': COUNSELING_SERVICE_CHOICES,
    'worship_style': WORSHIP_STYLE_CHOICES,
    'language': LANGUAGE_CHOICES,
    'program_name': PROGRAM_NAME_CHOICES,
    'country': COUNTRY_CHOICES,
    
    # Gift Constants
    'gift_language_choices': GIFT_LANGUAGE_CHOICES,
    "gift_answer_labels": GIFT_ANSWER_LABELS,

    # Payments constants
    'payment_status': PAYMENT_STATUS_CHOICES,
    'subscription_type': SUBSCRIPTION_TYPE_CHOICES,
    'subscription_pricing_type': SUBSCRIPTION_PRICING_TYPE_CHOICES,
    'advertisement_type': ADVERTISEMENT_TYPE_CHOICES,
    'pricing_type': PRICING_TYPE_CHOICES,
    'duration': DURATION_CHOICES,
    'billing_cycle': BILLING_CYCLE_CHOICES,

    # Posts constants
    'service_event': SERVICE_EVENT_CHOICES,
    'children_event_type': CHILDREN_EVENT_TYPE_CHOICES,
    'youth_event_type': YOUTH_EVENT_TYPE_CHOICES,
    'women_event_type': WOMEN_EVENT_TYPE_CHOICES,
    'men_event_type': MEN_EVENT_TYPE_CHOICES,
    'media_content': MEDIA_CONTENT_CHOICES,
    'literary_category': LITERARY_CATEGORY_CHOICES,
    'resource_type': RESOURCE_TYPE_CHOICES,

    # Sanctuary constants
    'post_report': POST_REPORT_CHOICES,
    'account_report': ACCOUNT_REPORT_CHOICES,
    'organization_report': ORGANIZATION_REPORT_CHOICES,
    'request_type': REQUEST_TYPE_CHOICES,
    'request_status': REQUEST_STATUS_CHOICES,
    'review_status': REVIEW_STATUS_CHOICES,
    'outcome': OUTCOME_CHOICES,
    'sensitive_categories': SENSITIVE_CATEGORIES,
    'post_admin_review_categories': POST_ADMIN_REVIEW_CATEGORIES,
    'account_admin_review_categories': ACCOUNT_ADMIN_REVIEW_CATEGORIES,
    'organization_admin_review_categories': ORGANIZATION_ADMIN_REVIEW_CATEGORIES,

    # Store constants
    'store_product_category': STORE_PRODUCT_CATEGORY_CHOICES,
    'currency': CURRENCY_CHOICES,

    # Orders constants
    'order_status': ORDER_STATUS_CHOICES,
    'delivery_order_status': DELIVERY_ORDER_STATUS_CHOICES,
    'return_order_status': RETURN_ORDER_STATUS_CHOICES,
}
