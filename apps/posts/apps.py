from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.posts'

    def ready(self):
        from apps.posts.signals import moment_media_cleanup
        from apps.posts.signals import testimony_media_cleanup