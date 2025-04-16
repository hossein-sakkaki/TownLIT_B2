from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    
    def ready(self):
        import apps.notifications.signals.post_signals
        import apps.notifications.signals.comment_signals
        import apps.notifications.signals.reaction_signals
        import apps.notifications.signals.friend_signals
        import apps.notifications.signals.manager_signals
        import apps.notifications.signals.user_signals

