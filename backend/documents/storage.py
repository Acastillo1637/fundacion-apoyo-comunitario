import hashlib
import socket
import struct
import subprocess
import sys
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from rest_framework.exceptions import APIException, ValidationError


class ScannerUnavailable(APIException):
    status_code = 503
    default_detail = 'El análisis de archivos no está disponible. Intenta cargar el documento más tarde.'


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_DOCUMENT_ROOT, file_permissions_mode=0o600, directory_permissions_mode=0o700)


def check_antimalware(data):
    if not settings.CLAMAV_HOST:
        if settings.DOCUMENT_SCAN_REQUIRED or not settings.DEBUG:
            raise ScannerUnavailable()
        return 'not_scanned'
    try:
        with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=10) as scanner:
            scanner.settimeout(10)
            scanner.sendall(b'zINSTREAM\0')
            for offset in range(0, len(data), 65536):
                chunk = data[offset:offset + 65536]
                scanner.sendall(struct.pack('!I', len(chunk)) + chunk)
            scanner.sendall(struct.pack('!I', 0))
            response = b''
            while b'\0' not in response and len(response) < 4096:
                chunk = scanner.recv(4096)
                if not chunk:
                    break
                response += chunk
    except OSError as exc:
        raise ScannerUnavailable() from exc
    result = response.rstrip(b'\0\r\n')
    if result.endswith(b' FOUND'):
        raise ValidationError('El archivo fue rechazado por el análisis antimalware.')
    if result != b'stream: OK':
        raise ScannerUnavailable()
    return 'clean'


def validate_upload(upload):
    extension = Path(upload.name).suffix.lower()
    types = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
    if extension not in types or upload.content_type != types[extension]:
        raise ValidationError('Solo se admiten PDF, JPEG y PNG con extensión y tipo correctos.')
    if upload.size > settings.DOCUMENT_MAX_BYTES or upload.size <= 0:
        raise ValidationError('El archivo debe contener datos y pesar como máximo 10 MB.')
    data = upload.read(settings.DOCUMENT_MAX_BYTES + 1)
    if not data or len(data) > settings.DOCUMENT_MAX_BYTES:
        raise ValidationError('El archivo supera el tamaño permitido.')
    scan_status = check_antimalware(data)
    try:
        result = subprocess.run(
            [sys.executable, '-I', str(Path(__file__).with_name('inspect_file.py')), extension],
            input=data, capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationError('No se pudo comprobar el contenido del archivo dentro del límite permitido.') from exc
    if result.returncode:
        raise ValidationError('El archivo no es válido, está cifrado o contiene elementos no permitidos.')
    return data, types[extension], extension, scan_status


def save_file(data, extension):
    key = f'{uuid.uuid4().hex}{extension}'
    storage = private_storage()
    name = storage.save(key, ContentFile(data))
    return name, hashlib.sha256(data).hexdigest()
