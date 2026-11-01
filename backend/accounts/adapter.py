from allauth.account.adapter import DefaultAccountAdapter


class FoundationAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Solo el endpoint controlado crea perfiles y recoge consentimientos.
        return False
