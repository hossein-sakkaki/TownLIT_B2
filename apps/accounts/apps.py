from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        import apps.accounts.signals.signals
        import apps.accounts.signals.identity
        import apps.accounts.signals.trust_profile_signals
        import apps.accounts.signals.townlit_identity_dependency_signals

