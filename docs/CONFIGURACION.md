# Configuración de entornos

Django lee variables del proceso, no carga archivos `.env` automáticamente. Ninguna clave privada debe llegar al frontend, llevar prefijo `VITE_`, imprimirse en capturas o subirse a Git.

## Elegir la plantilla correcta

| Uso | Plantilla versionada | Archivo privado / lector |
|---|---|---|
| Desarrollo compartido en Windows | `config/shared-database.env.example` | `.env.shared` en la raíz; scripts `load-shared-env.ps1`, inicio y administración compartidos |
| Hosting | `.env.example` | Fuera de la web, p. ej. `/etc/fundacion/backend.env`; systemd/hosting o `scripts/production-manage.py --env-file` |
| Local/pruebas aisladas | No requiere archivo privado | `manage-local.ps1` configura SQLite temporalmente; CI configura PostgreSQL desechable |

`.env.example` es la **única plantilla de producción**. No es un archivo de credenciales listo para arrancar y no se debe copiar a `.env.shared`. El lector compartido admite un conjunto acotado de claves y fija DEBUG, URL local y correo de consola; rechaza variables de producción no admitidas.

## Desarrollo compartido

Completar `POSTGRES_HOST`, `POSTGRES_PORT` (6543 pooler transaccional o 5432 sesión), `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE` y `DJANGO_SECRET_KEY`. `GEOAPIFY_API_KEY` es opcional para el cálculo por dirección. El script exige SSL y una clave Django privada de al menos 50 caracteres.

Ambos equipos usan la misma base y clave Django. Si ya existen datos, conservar la clave: firmas, sesiones y secretos 2FA cifrados dependen de ella. El comando para generarla se usa **una sola vez al crear un entorno nuevo**, no para sustituir la clave de una base existente. Consultar [base compartida](BASE_COMPARTIDA.md) antes de importar o migrar.

## Producción

Completar las variables de `.env.example` y ejecutar los controles descritos en [despliegue](DESPLIEGUE_PRO12.md). Los valores vacíos no son credenciales válidas ni una aprobación institucional.

| Variables | Propósito |
|---|---|
| `DJANGO_DEBUG`, `DJANGO_SECRET_KEY` | DEBUG debe ser `false`; clave privada conservada si se mantiene la base actual. |
| `FOUNDATION_NAME` | Nombre institucional; valor predeterminado de la aplicación. |
| `DJANGO_ALLOWED_HOSTS` | Nombres de host explícitos, sin esquema, separados por coma; nunca `*`. |
| `PUBLIC_APP_URL` | Origen HTTPS público, sin usuario/contraseña, ruta, consulta o fragmento. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS propios cuando corresponda; no abre CORS. |
| `DJANGO_TRUST_PROXY` | `true` solo detrás del proxy propio que sobrescribe `X-Forwarded-Proto`; backend inaccesible directamente desde internet. |
| `DATABASE_ENGINE` | `postgresql`; Supabase sigue siendo la base definitiva. |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Conexión PostgreSQL del backend, no claves anon/service_role de Supabase Auth. |
| `POSTGRES_SSLMODE`, `POSTGRES_SSLROOTCERT` | Exigir TLS; `verify-full` y CA del proveedor para comprobar identidad. La ruta de CA debe existir en el servidor. |
| `EMAIL_BACKEND` | Backend SMTP en producción; consola en desarrollo. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Datos del proveedor. Ambos campos de autenticación se completan juntos, salvo relay expresamente autorizado sin autenticación. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | STARTTLS/587: `true/false`. TLS implícito/465: `false/true`. Nunca ambos activos. |
| `DEFAULT_FROM_EMAIL` | Remitente autorizado real; admite nombre visible. No usar los remitentes de ejemplo. |
| `PRIVATE_DOCUMENT_ROOT` | Ruta absoluta privada y persistente, fuera de frontend/estáticos. Los archivos requieren copia/traslado separado. |
| `CLAMAV_HOST`, `CLAMAV_PORT` | Antivirus accesible internamente; producción no permite omitir el análisis. |
| `GEOAPIFY_API_KEY` | Opcional para calcular referencia por domicilio con autorización; solo backend. Sin clave sigue disponible la referencia manual. |
| `MAP_TILE_URL` | Fondo del mapa; valor predeterminado OpenStreetMap con atribución. |
| `GEOCODING_URL`, `GEOCODING_USER_AGENT` | Búsqueda pública de lugares, independiente de Geoapify. Requiere habilitación administrativa y no admite domicilios particulares. |
| `DATA_RETENTION_NOTICE` | Texto/plazo aprobado por la fundación. No inventar una política para superar el control. |

El wrapper de producción acepta únicamente nombres admitidos, rechaza duplicados y no evalúa comandos ni expansiones de shell. En Linux exige permisos `600` o más restrictivos. No usar `export`, comandos, sustituciones ni continuaciones de línea; usar valores literales `NOMBRE=valor` y comillas completas cuando corresponda. No cambiar la configuración privada existente durante una limpieza del repositorio.

## Herramientas separadas

- `BACKEND_PROXY_TARGET` pertenece al servidor Vite de desarrollo; por defecto apunta a `http://127.0.0.1:8000`. No es una variable de Django ni un secreto para el navegador.
- `RESTORE_POSTGRES_*` pertenece a la restauración sobre una base **nueva y vacía**. No sustituye `POSTGRES_*` ni debe apuntar al destino activo. Ver [recuperación](DESPLIEGUE_PRO12.md#respaldo-y-recuperación-en-windows).
- Los scripts no contratan servicios, inventan credenciales ni envían correos al comprobar configuración. `preflight_production --services` abre las conexiones configuradas, pero no comprueba entrega de correo.
