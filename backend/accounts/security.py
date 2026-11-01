from allauth.account.internal.flows.login import get_authentication_records


def portal_authenticated(request):
    records = get_authentication_records(request, request.user)
    if any(record.get('method') == 'mfa' for record in records):
        return True
    return (not request.user.authenticator_set.exists()
            and any(record.get('method') == 'password' for record in records))
