from rest_framework import serializers
from volunteers.serializers import StrictSerializer

ROLE_NAMES = ['Voluntario', 'Solicitante', 'Secretaría', 'Administrador general']


class CreateAccountSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=ROLE_NAMES), min_length=1, max_length=4)
    reason = serializers.CharField(min_length=8, max_length=1000)

    def validate_roles(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('No repitas roles.')
        return value


class UpdateAccountSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    first_name = serializers.CharField(max_length=80, required=False)
    last_name = serializers.CharField(max_length=80, required=False)
    is_active = serializers.BooleanField(required=False)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=ROLE_NAMES), min_length=1, max_length=4, required=False)
    reason = serializers.CharField(min_length=8, max_length=1000)

    def validate(self, attrs):
        if not set(attrs).intersection({'first_name', 'last_name', 'is_active', 'roles'}):
            raise serializers.ValidationError('Indica al menos un campo para modificar.')
        if 'roles' in attrs and len(attrs['roles']) != len(set(attrs['roles'])):
            raise serializers.ValidationError({'roles': 'No repitas roles.'})
        return attrs


class AccessEmailSerializer(StrictSerializer):
    reason = serializers.CharField(min_length=8, max_length=1000)


class OnboardingSerializer(StrictSerializer):
    adult = serializers.BooleanField()
    privacy = serializers.BooleanField()
    whatsapp = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not attrs['adult'] or not attrs['privacy']:
            raise serializers.ValidationError('Debes confirmar mayoría de edad y tratamiento de tus datos.')
        return attrs
