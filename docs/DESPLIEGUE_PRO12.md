> Actualización 21-11-2026: [preparación del hosting y paquete verificable](PREPARAR_HOSTING.md), SMTP STARTTLS/587 o TLS implícito/465, wrapper de comandos con entorno privado y diagnóstico `preflight_production --services`. El proveedor sigue sin contratarse; no se ha publicado.

# Operación y despliegue

## Estado

Supabase PostgreSQL es la base definitiva. Django conserva autenticación, permisos y migraciones. Los archivos privados están en disco del backend; no en la base ni en Supabase Storage. Compartir la base no comparte los archivos físicos: ambos desarrolladores necesitan el mismo almacenamiento privado autorizado o una copia privada de esos archivos. No se habilitó ningún servicio pagado ni se publicó una web durante esta entrega.

El hosting necesita Python 3.13 con proceso WSGI persistente, proxy HTTPS, conexión saliente PostgreSQL/SMTP, volumen privado persistente y ClamAV accesible en red interna. Un hosting únicamente estático o PHP no ejecuta Django. React puede servirse como estáticos, preferentemente bajo el mismo dominio que la API para no necesitar CORS abierto.

## Instalación Linux de referencia

Los archivos `deploy/*.example` son plantillas, no configuración aplicada. Sustituir dominio, rutas, usuario del servicio y certificados. Preparar una cuenta de servicio sin privilegios y un volumen `/var/lib/fundacion/documents` con permisos exclusivos del backend. El usuario de Nginx solo lee React y estáticos; nunca documentos.

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r backend/requirements.production.lock
npm --prefix frontend ci
npm --prefix frontend run build
```

El servidor debe cargar las variables de `.env.example` mediante su gestor de secretos/servicios. Django no lee automáticamente ese archivo. Guardar el archivo real fuera del checkout, con permisos 600, sin incorporarlo a Git. Cargarlo también en la consola administrativa antes de los comandos siguientes, sin imprimir sus valores.

Requisitos de configuración:

- `DJANGO_DEBUG=false`, clave única privada, `PUBLIC_APP_URL=https://dominio-real`, `DJANGO_ALLOWED_HOSTS=dominio-real`; orígenes CSRF HTTPS explícitos. No usar `*` ni habilitar CORS indiscriminadamente.
- Supabase por TLS. Preferir `POSTGRES_SSLMODE=verify-full` con `POSTGRES_SSLROOTCERT` del proveedor. `require` cifra pero no proporciona la misma verificación explícita de identidad. Confirmar compatibilidad del hostname del endpoint y CA en el hosting.
- Pooler Supabase transaccional para la aplicación según BASE_COMPARTIDA; herramientas de respaldo usan conexión de sesión/directa. Dimensionar trabajadores/pool respecto del límite del proyecto. Comenzar con un trabajador y cuatro hilos; medir antes de ampliar.
- SMTP real, remitente autorizado y configuración DNS que indique el proveedor. En local el backend de consola no envía a Gmail. La recuperación real sigue pendiente hasta configurar SMTP.
- `PRIVATE_DOCUMENT_ROOT=/var/lib/fundacion/documents`; copia externa cifrada, sin acceso público. ClamAV interno con firmas actualizadas: en producción los uploads fallan de forma cerrada si no se puede analizar.
- `DATA_RETENTION_NOTICE` institucional aprobado. No se ha fijado aún el plazo. Las solicitudes de privacidad se notifican a todos los administradores activos dentro de la web; no dependen de un correo único.
- `DJANGO_TRUST_PROXY=true` solamente detrás del proxy propio que sobrescribe `X-Forwarded-Proto`. Bloquear acceso público al puerto WSGI; solo Nginx escucha internet. Con la configuración de ejemplo, el servicio escucha en localhost.
- Mantener la búsqueda externa de lugares desactivada hasta aceptación administrativa consciente; revisar políticas OSM y capacidad. Se puede usar el mapa/las coordenadas sin geocodificación.

Antes del cambio de versión, generar respaldo de base y documentos, verificar su manifiesto y probar recuperación en un destino separado. Después:

```bash
.venv/bin/python backend/manage.py check --deploy --fail-level WARNING
.venv/bin/python backend/manage.py migrate --plan
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py collectstatic --noinput
```

La comprobación de despliegue falla si faltan dominio HTTPS, conservación, SMTP, antivirus o separación de archivos privados; los avisos estándar de Django también deben revisarse. No silenciar esos controles para publicar. Crear el servicio desde la plantilla solo después de revisar rutas/permisos, instalar certificado y validar `nginx -t`. Verificar desde un dispositivo externo login, CSRF, descarga privada, subida analizada y recuperación por correo. No usar `runserver` ni Vite como servidores públicos.

## Respaldo y recuperación en Windows

Requiere clientes PostgreSQL 17 compatibles en PATH. El respaldo es un dump del esquema `public`; no incluye las tablas internas de Supabase ni autenticación de otro producto.

```powershell
./scripts/backup-database.ps1 -SharedDevelopment -OutputDirectory 'D:/respaldo-privado' -PrivateDocumentsPath 'D:/ruta/privada/documentos'
```

No reutilizar la ruta de ejemplo sin sustituirla. Se genera dump custom, ZIP opcional de documentos y manifiesto SHA-256. No subirlos a GitHub: contienen datos personales. Verificar los hashes y guardar una copia cifrada fuera del servidor. La periodicidad, retención, RPO/RTO y responsables operativos aún deben aprobarse; no existe una tarea programada de respaldo instalada.

Para recuperación, crear una **base nueva vacía** y configurar por separado `RESTORE_POSTGRES_HOST`, `RESTORE_POSTGRES_PORT`, `RESTORE_POSTGRES_DB`, `RESTORE_POSTGRES_USER`, `RESTORE_POSTGRES_PASSWORD`, `RESTORE_POSTGRES_SSLMODE` y, si corresponde, `RESTORE_POSTGRES_SSLROOTCERT`. No apuntar a la base activa:

```powershell
./scripts/restore-empty-database.ps1 -BackupFile 'D:/respaldo-privado/database-FECHA.dump' -ConfirmEmptyTarget
```

Se rechazan destinos con tablas. La restauración es transaccional, sin `--clean`, sin borrar el esquema `public` y sin sobrescribir propietarios. Restaurar el ZIP de documentos en un directorio privado nuevo, verificar hashes y rutas, permisos, migraciones, conteos y una descarga autorizada. Cambiar el destino de la aplicación solo después de esa revisión; conservar la base anterior como recuperación. No revertir migraciones con pérdida de datos para deshacer un despliegue.

La prueba local realizada restauró 49 tablas con contenido idéntico y un archivo ficticio idéntico; rechazó una segunda restauración sobre el destino poblado. No se restauraron ni borraron datos en Supabase.

## Salud, observabilidad y continuidad

`/api/health/live/` comprueba proceso; `/api/health/ready/` comprueba PostgreSQL. Respuestas mínimas y sin secretos. Con HTTPS obligatorio, el monitor debe usar HTTPS o una cabecera del proxy confiable. Alertar por 503, errores 5xx, latencias, conexiones, almacenamiento, antivirus y fallos SMTP. No registrar contraseñas, tokens, cuerpos de formularios ni documentos en logs.

Los historiales guardan cambios administrativos, asignaciones, contactos y privacidad. Las notificaciones son internas: no equivalen a correo entregado ni WhatsApp leído. Preservar la clave Django durante despliegues regulares; rotarla requiere un procedimiento separado porque afecta sesiones y firmas.
