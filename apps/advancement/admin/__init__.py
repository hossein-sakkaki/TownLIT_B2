# apps/advancement/admin/__init__.py

from apps.advancement.admin.site import advancement_admin_site

# Import model classes
from apps.advancement.models import (
    LegalEntity,
    ExternalEntity,
    Opportunity,
    Commitment,
    StrategicScore,
    InteractionLog,
    Tag,
    TagCategory,
)

# Import admin classes
from .legal_entity_admin import LegalEntityAdmin
from .external_entity_admin import ExternalEntityAdmin
from .opportunity_admin import OpportunityAdmin
from .commitment_admin import CommitmentAdmin
from .scoring_admin import StrategicScoreAdmin
from .interaction_admin import InteractionLogAdmin
from .tagging_admin import TagAdmin, TagCategoryAdmin

# Register to dedicated admin site
advancement_admin_site.register(LegalEntity, LegalEntityAdmin)
advancement_admin_site.register(ExternalEntity, ExternalEntityAdmin)
advancement_admin_site.register(Opportunity, OpportunityAdmin)
advancement_admin_site.register(Commitment, CommitmentAdmin)
advancement_admin_site.register(StrategicScore, StrategicScoreAdmin)
advancement_admin_site.register(InteractionLog, InteractionLogAdmin)
advancement_admin_site.register(Tag, TagAdmin)
advancement_admin_site.register(TagCategory, TagCategoryAdmin)