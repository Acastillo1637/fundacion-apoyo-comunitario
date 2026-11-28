from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers
from .communes import validate_commune
from .phones import ChileanMobileField


class RegistrationSerializer(serializers.Serializer):
    account_type = serializers.ChoiceField(choices=['volunteer', 'requester'], default='volunteer')
    requester_type = serializers.ChoiceField(choices=['person', 'company', 'institution'], required=False)
    organization = serializers.CharField(max_length=150, allow_blank=True, default='')
    phone = serializers.RegexField(r'^\+?[0-9 ()-]{7,20}$', required=False, allow_blank=True)
    commune = serializers.CharField(max_length=80, allow_blank=True, default='')
    authorized_representative = serializers.BooleanField(default=False)
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
        if attrs['account_type'] == 'volunteer':
            if not attrs['whatsapp']:
                raise serializers.ValidationError({'whatsapp': 'Debes autorizar el contacto por WhatsApp para coordinar tu participación.'})
            profile = ProfileSerializer(data={name: attrs[name] for name in
                ['first_name', 'last_name', 'phone', 'commune'] if name in attrs})
            profile.is_valid(raise_exception=True)
            attrs.update(profile.validated_data)
        if attrs['account_type'] == 'requester':
            if not attrs.get('requester_type') or not attrs.get('phone'):
                raise serializers.ValidationError('Indica el tipo de solicitante y un teléfono de contacto.')
            if attrs['requester_type'] != 'person' and (not attrs['organization'] or not attrs['authorized_representative']):
                raise serializers.ValidationError('Indica la entidad y confirma que estás autorizado para representarla.')
        user = get_user_model()(email=attrs['email'], first_name=attrs['first_name'], last_name=attrs['last_name'])
        try:
            validate_password(attrs['password'], user)
        except ValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages}) from exc
        return attrs


class ProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    phone = ChileanMobileField()
    commune = serializers.CharField(max_length=80)

    def validate_commune(self, value):
        return validate_commune(value)
