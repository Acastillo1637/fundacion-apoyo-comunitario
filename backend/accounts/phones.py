import re

from rest_framework import serializers


def chilean_mobile(value):
    raw = str(value).strip()
    if re.search(r'[^+0-9 ()-]', raw) or raw.count('+') > 1 or ('+' in raw and not raw.startswith('+')):
        raise serializers.ValidationError('Ingresa un celular chileno de 9 dígitos que comience con 9.')
    digits = re.sub(r'[^0-9]', '', raw)
    if digits.startswith('0056') and not raw.startswith('+'):
        digits = digits[2:]
    if re.fullmatch(r'9[0-9]{8}', digits) and not raw.startswith('+'):
        digits = '56' + digits
    if not re.fullmatch(r'569[0-9]{8}', digits):
        raise serializers.ValidationError('Ingresa un celular chileno de 9 dígitos que comience con 9. El código +56 se agrega automáticamente.')
    return '+' + digits


class ChileanMobileField(serializers.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=12, **kwargs)

    def to_internal_value(self, value):
        return chilean_mobile(super().to_internal_value(value))
