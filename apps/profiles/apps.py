# apps/profiles/apps.py

from django.apps import AppConfig

class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.profiles'

    def ready(self):
        import apps.profiles.signals.signals
        import apps.profiles.signals.trust_friendship_signals
        import apps.profiles.signals.townlit_member_signals
        import apps.profiles.signals.townlit_member_m2m_signals
        import apps.profiles.signals.townlit_friendship_signals
        import apps.profiles.signals.townlit_spiritual_gifts_signals