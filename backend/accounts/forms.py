from allauth.account.forms import ResetPasswordForm
from django.contrib.auth import get_user_model


class PrimaryEmailResetForm(ResetPasswordForm):
    def clean_email(self):
        email = super().clean_email()
        # Recovery proves mailbox access through the signed, single-use link.
        # An added, unverified alias must never recover somebody else's account.
        self.users = list(get_user_model().objects.filter(email__iexact=email, is_active=True))
        return email
