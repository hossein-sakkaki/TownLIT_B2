from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    
    def ready(self):
        import apps.notifications.signals.comment_signals
        import apps.notifications.signals.reaction_signals
        import apps.notifications.signals.friendship_signals 
        import apps.notifications.signals.fellowship_signals
        import apps.notifications.signals.common_signals
        import apps.notifications.signals.messages_signals
        import apps.notifications.signals.testimony_signals


