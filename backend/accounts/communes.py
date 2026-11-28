"""Local commune catalogue: DIPRES SIGFE Global 2026, pages 13–24.

Source: https://dipres.gob.cl/590/articles-393849_doc_pdf.pdf
Retrieved 2026-11-27. No external requests during profile validation.
"""
import json
import unicodedata
from pathlib import Path

from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def commune_key(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.strip().casefold())
                   if not unicodedata.combining(c))


COMMUNES = tuple(json.loads(Path(__file__).with_name('communes.json').read_text(encoding='utf-8')))
COMMUNE_NAMES = {commune_key(name): name for name in COMMUNES}


def validate_commune(value):
    name = COMMUNE_NAMES.get(commune_key(value))
    if name is None:
        raise serializers.ValidationError('Selecciona una comuna válida de la lista.')
    return name


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def catalogue(request):
    return Response({'communes': COMMUNES})
