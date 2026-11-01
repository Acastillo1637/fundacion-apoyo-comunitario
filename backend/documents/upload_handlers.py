from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler, StopUpload


class BoundedUploadHandler(FileUploadHandler):
    """Corta cargas excesivas antes de guardarlas completas en disco temporal."""
    def __init__(self, request=None):
        super().__init__(request)
        self.received = 0
        self.file_count = 0

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.file_count += 1
        if self.file_count > 1:
            self.request.document_upload_rejected = True
            raise StopUpload(connection_reset=True)

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > settings.DOCUMENT_MAX_BYTES:
            self.request.document_upload_rejected = True
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None
