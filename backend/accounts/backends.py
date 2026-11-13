from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


class OptimizedModelBackend(ModelBackend):
    """Keep Django's permission semantics, union direct and group grants in SQL."""

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        if not hasattr(user_obj, '_perm_cache'):
            fields = ('content_type__app_label', 'codename')
            permissions = Permission.objects.order_by().values_list(*fields)
            if not user_obj.is_superuser:
                permissions = permissions.filter(user=user_obj).union(
                    Permission.objects.filter(group__user=user_obj).order_by().values_list(*fields))
            user_obj._perm_cache = {f'{app}.{codename}' for app, codename in permissions}
        return user_obj._perm_cache
