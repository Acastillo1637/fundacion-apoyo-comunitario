def is_volunteer(user):
    return user.is_authenticated and user.groups.filter(name='Voluntario').exists()


def is_requester(user):
    return user.is_authenticated and user.groups.filter(name='Solicitante').exists()


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
