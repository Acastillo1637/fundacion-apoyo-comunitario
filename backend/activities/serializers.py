from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from volunteers.models import DocumentType, Skill
from volunteers.serializers import StrictSerializer


def active_choices(model, ids, field):
    if len(ids) != len(set(ids)):
        raise serializers.ValidationError({field: 'No se permiten requisitos repetidos.'})
    rows = list(model.objects.filter(pk__in=ids, is_active=True).order_by('pk'))
    if len(rows) != len(ids):
        raise serializers.ValidationError({field: 'Selecciona opciones vigentes del catálogo.'})
    return rows


class LocalScheduleSerializer(StrictSerializer):
    date = serializers.DateField()
    start_time = serializers.TimeField(input_formats=['%H:%M'])
    end_time = serializers.TimeField(input_formats=['%H:%M'])

    def validate(self, attrs):
        zone = ZoneInfo(settings.TIME_ZONE)
        times = []
        for field in ['start_time', 'end_time']:
            naive = datetime.combine(attrs['date'], attrs[field])
            first = naive.replace(tzinfo=zone, fold=0)
            second = naive.replace(tzinfo=zone, fold=1)
            if first.utcoffset() != second.utcoffset():
                raise serializers.ValidationError({field: 'Horario ambiguo o inexistente por cambio de hora. Elige otra hora.'})
            times.append(first)
        if times[0] >= times[1]:
            raise serializers.ValidationError('El término debe ser posterior al inicio dentro del mismo día.')
        if times[0] <= timezone.now():
            raise serializers.ValidationError({'date': 'La actividad debe comenzar en el futuro.'})
        attrs['starts_at'], attrs['ends_at'] = times
        for field in ['date', 'start_time', 'end_time']:
            del attrs[field]
        return attrs


class RequestSerializer(LocalScheduleSerializer):
    submission_id = serializers.UUIDField()
    requester_type = serializers.ChoiceField(choices=['person', 'company', 'institution'])
    contact_name = serializers.CharField(max_length=120)
    organization = serializers.CharField(max_length=150, allow_blank=True, default='')
    email = serializers.EmailField(max_length=254)
    phone = serializers.RegexField(r'^\+?[0-9 ()-]{7,20}$')
    description = serializers.CharField(min_length=20, max_length=3000)
    quantity = serializers.IntegerField(min_value=1, max_value=500)
    address = serializers.CharField(max_length=250)
    commune = serializers.CharField(max_length=80)
    observations = serializers.CharField(max_length=1500, allow_blank=True, default='')
    skills = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=30)
    privacy = serializers.BooleanField()
    website = serializers.CharField(max_length=200, allow_blank=True, default='')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['requester_type'] != 'person' and not attrs['organization']:
            raise serializers.ValidationError({'organization': 'Indica el nombre de la empresa o institución.'})
        if not attrs['privacy']:
            raise serializers.ValidationError({'privacy': 'Debes aceptar el tratamiento para gestionar esta solicitud.'})
        attrs['skills'] = active_choices(Skill, attrs['skills'], 'skills')
        attrs['email'] = attrs['email'].lower()
        return attrs


class PositionSerializer(StrictSerializer):
    name = serializers.CharField(max_length=100)
    capacity = serializers.IntegerField(min_value=1, max_value=500)
    required_skills = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=30)
    required_documents = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=30)

    def validate(self, attrs):
        attrs['required_skills'] = active_choices(Skill, attrs['required_skills'], 'required_skills')
        attrs['required_documents'] = active_choices(DocumentType, attrs['required_documents'], 'required_documents')
        return attrs


class EventSerializer(LocalScheduleSerializer):
    title = serializers.CharField(max_length=150)
    public_description = serializers.CharField(min_length=20, max_length=2000)
    address = serializers.CharField(max_length=250)
    commune = serializers.CharField(max_length=80)
    internal_notes = serializers.CharField(max_length=1500, allow_blank=True, default='')
    positions = PositionSerializer(many=True, min_length=1, max_length=20)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        names = [item['name'].casefold() for item in attrs['positions']]
        if len(names) != len(set(names)):
            raise serializers.ValidationError({'positions': 'Las funciones no pueden tener el mismo nombre.'})
        if sum(item['capacity'] for item in attrs['positions']) > 500:
            raise serializers.ValidationError({'positions': 'El total no puede superar 500 cupos.'})
        return attrs


class TransitionSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    status = serializers.CharField(max_length=20)
    reason = serializers.CharField(max_length=1000, allow_blank=True, default='')


class EditEventSerializer(EventSerializer):
    revision = serializers.IntegerField(min_value=0)


class PublishedEventSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(min_length=8, max_length=1000)
    title = serializers.CharField(max_length=150, required=False)
    public_description = serializers.CharField(min_length=20, max_length=2000, required=False)
    internal_notes = serializers.CharField(max_length=1500, allow_blank=True, required=False)

    def validate(self, attrs):
        if not set(attrs).intersection({'title', 'public_description', 'internal_notes'}):
            raise serializers.ValidationError('Indica al menos un dato informativo para actualizar.')
        return attrs
