from django.apps import AppConfig


class VolunteersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'volunteers'
    verbose_name = 'Voluntarios y catálogos'

    def ready(self):
        from . import signals  # noqa: F401
