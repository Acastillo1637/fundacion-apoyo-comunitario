from collections.abc import Mapping

from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping) and set(data) - set(self.fields):
            raise serializers.ValidationError({'non_field_errors': ['La solicitud contiene campos no editables.']})
        return super().to_internal_value(data)


class QualificationsSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    skills = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=50)
    professions = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=20)

    def validate(self, attrs):
        for name in ['skills', 'professions']:
            if len(attrs[name]) != len(set(attrs[name])):
                raise serializers.ValidationError({name: 'No se permiten elementos repetidos.'})
        return attrs


class SlotSerializer(StrictSerializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField(input_formats=['%H:%M'], format='%H:%M')
    end_time = serializers.TimeField(input_formats=['%H:%M'], format='%H:%M')

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError('El término debe ser posterior al inicio, dentro del mismo día.')
        return attrs


class AvailabilitySerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    slots = SlotSerializer(many=True, max_length=42)
    unavailable_dates = serializers.ListField(child=serializers.DateField(), max_length=60)

    def validate(self, attrs):
        ordered = sorted(attrs['slots'], key=lambda slot: (slot['weekday'], slot['start_time']))
        for previous, current in zip(ordered, ordered[1:]):
            if previous['weekday'] == current['weekday'] and current['start_time'] < previous['end_time']:
                raise serializers.ValidationError({'slots': 'Hay franjas superpuestas en un mismo día.'})
        dates = attrs['unavailable_dates']
        if len(dates) != len(set(dates)):
            raise serializers.ValidationError({'unavailable_dates': 'Hay fechas repetidas.'})
        attrs['slots'] = ordered
        return attrs
