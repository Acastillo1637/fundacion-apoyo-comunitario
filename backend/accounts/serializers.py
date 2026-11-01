from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    password = serializers.CharField(write_only=True, max_length=256, trim_whitespace=False)
    adult = serializers.BooleanField()
    privacy = serializers.BooleanField()
    whatsapp = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not attrs['adult'] or not attrs['privacy']:
            raise serializers.ValidationError('Debes ser mayor de edad y aceptar el aviso de privacidad.')
        user = get_user_model()(email=attrs['email'], first_name=attrs['first_name'], last_name=attrs['last_name'])
        try:
            validate_password(attrs['password'], user)
        except ValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages}) from exc
        return attrs


class ProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    phone = serializers.RegexField(r'^\+?[0-9 ()-]{7,20}$', allow_blank=True)
    commune = serializers.CharField(max_length=80, allow_blank=True)
