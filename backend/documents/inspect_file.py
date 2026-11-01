"""Inspección aislada: no importa Django ni recibe rutas elegidas por usuarios."""
import io
import sys
import warnings


MAX_BYTES = 10 * 1024 * 1024


def inspect(data, extension):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Tamaño no permitido.')
    if extension in ['.png', '.jpg', '.jpeg']:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = 16_000_000
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        expected = 'PNG' if extension == '.png' else 'JPEG'
        with Image.open(io.BytesIO(data)) as image:
            if image.format != expected or image.width * image.height > 16_000_000:
                raise ValueError('La imagen no coincide con el formato permitido.')
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
        return
    if extension != '.pdf' or not data.startswith(b'%PDF-'):
        raise ValueError('Formato no permitido.')
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 50:
        raise ValueError('PDF cifrado, vacío o de más de 50 páginas.')
    # Conservamos el original para no invalidar firmas; rechazamos contenido activo.
    forbidden = {'/JavaScript', '/JS', '/OpenAction', '/AA', '/Launch', '/EmbeddedFile', '/EmbeddedFiles', '/EF', '/RichMedia', '/XFA', '/SubmitForm', '/ImportData', '/GoToR', '/GoToE', '/Rendition', '/Sound', '/Movie'}
    stack = [reader.trailer]
    seen = set()
    budget = 20000
    while stack:
        budget -= 1
        if budget < 0:
            raise ValueError('PDF demasiado complejo.')
        item = stack.pop()
        if isinstance(item, IndirectObject):
            key = (item.idnum, item.generation)
            if key in seen:
                continue
            seen.add(key)
            item = item.get_object()
        if isinstance(item, DictionaryObject):
            if forbidden.intersection(item.keys()) or str(item.get('/S', '')) in forbidden or str(item.get('/Type', '')) in forbidden:
                raise ValueError('PDF con acciones o adjuntos no permitidos.')
            stack.extend(item.values())
        elif isinstance(item, ArrayObject):
            stack.extend(item)


if __name__ == '__main__':
    try:
        if sys.platform != 'win32':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
            resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        inspect(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1])
    except Exception:
        # No emitimos datos extraídos del documento ni detalles del parser.
        sys.exit(1)
