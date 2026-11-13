from django.db.models import prefetch_related_objects


def role_names(user):
    if not user.is_authenticated:
        return []
    # Django invalidates this instance's prefetch when its groups are changed.
    prefetch_related_objects([user], 'groups')
    return [group.name for group in user.groups.all()]


def is_volunteer(user):
    return user.is_authenticated and 'Voluntario' in role_names(user)


def is_requester(user):
    return user.is_authenticated and 'Solicitante' in role_names(user)


def portal_access(user):
    result = []
    if user.has_perm('accounts.manage_accounts') or user.has_perm('volunteers.change_skill'):
        result.append('administration')
    if user.has_perm('activities.manage_operations') or user.has_perm('documents.review_volunteerdocument'):
        result.append('operations')
    if is_volunteer(user):
        result.append('volunteer')
    if is_requester(user):
        result.append('requester')
    return result


def can_access_portal(user, portal):
    """Check the requested space without loading unrelated role memberships."""
    if portal == 'administration':
        return user.has_perm('accounts.manage_accounts') or user.has_perm('volunteers.change_skill')
    if portal == 'operations':
        return user.has_perm('activities.manage_operations') or user.has_perm('documents.review_volunteerdocument')
    if portal == 'volunteer':
        return is_volunteer(user)
    if portal == 'requester':
        return is_requester(user)
    return False
