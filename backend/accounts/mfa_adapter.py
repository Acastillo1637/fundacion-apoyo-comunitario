import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from allauth.mfa.adapter import DefaultMFAAdapter


class FoundationMFAAdapter(DefaultMFAAdapter):
    def cipher(self):
        key = hashlib.sha256(('foundation-mfa-v1:' + settings.SECRET_KEY).encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, text):
        return 'fac1:' + self.cipher().encrypt(text.encode()).decode()

    def decrypt(self, encrypted_text):
        # Existing allauth records keep working; no mass rewrite or new factors.
        if not encrypted_text.startswith('fac1:'):
            return encrypted_text
        return self.cipher().decrypt(encrypted_text[5:].encode()).decode()
