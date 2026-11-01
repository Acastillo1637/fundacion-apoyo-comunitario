from rest_framework import serializers
from volunteers.serializers import StrictSerializer


class UploadSerializer(StrictSerializer):
    document_type = serializers.IntegerField(min_value=1)
    file = serializers.FileField(allow_empty_file=False)


class ReviewSerializer(StrictSerializer):
    decision = serializers.ChoiceField(choices=['validated', 'rejected'])
    observation = serializers.CharField(max_length=1000, allow_blank=True, default='')
    expires_on = serializers.DateField(allow_null=True, default=None)

    def validate(self, attrs):
        if attrs['decision'] == 'rejected' and not attrs['observation'].strip():
            raise serializers.ValidationError({'observation': 'Indica el motivo del rechazo.'})
        if attrs['decision'] == 'rejected' and attrs['expires_on']:
            raise serializers.ValidationError({'expires_on': 'No corresponde vencimiento para un rechazo.'})
        return attrs
