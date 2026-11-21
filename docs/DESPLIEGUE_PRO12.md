# Hosting, despliegue y recuperación

Todavía no hay proveedor contratado. La instalación de referencia usa Linux, Nginx, Gunicorn y systemd. No se instaló en un servidor externo ni se contrató un servicio. PostgreSQL permanece en Supabase: no necesitas exportarlo al hosting para usar la aplicación.

## Requisitos que debe confirmar el proveedor

- Python 3.13 persistente con WSGI, entorno virtual, instalación de `backend/requirements.production.lock`, comandos administrativos y acceso a logs por SSH o un procedimiento administrado equivalente.
- Frontend compilado y estáticos Django bajo el mismo dominio HTTPS; `/api/`, `/accounts/` y `/admin/` dirigidos al backend. Alojar solamente HTML/PHP no cubre estas necesidades.
- Conexiones salientes hacia Supabase por TLS, Geoapify y SMTP seguro; dominio, certificado y configuración del proxy.
- Documentos privados en almacenamiento persistente fuera de la web, con copia externa. Compartir PostgreSQL no comparte archivos: deben trasladarse y verificarse por separado.
- ClamAV interno con firmas actualizadas o capacidad de instalarlo. No exponer el puerto 3310 a internet. Las cargas fallan de forma cerrada cuando no puede analizarse un archivo.
- Recursos para aplicación y antivirus. ClamAV recomienda al menos 3 GiB de RAM en Linux con sus firmas estándar, más los recursos de las otras aplicaciones. [Requisitos oficiales](https://docs.clamav.net/).

Un VPS con administración permite instalar esta arquitectura. Un hosting compartido solo sirve si el proveedor confirma todas las capacidades; tener cPanel o SSL por sí solo no lo demuestra. No se afirma compatible un plan sin revisarlo.

## Paquete para subir

Desde un checkout limpio, con dependencias locales instaladas:

```powershell
.venv\Scripts\python.exe scripts/build-release.py
```

Genera `backups/releases/fundacion-COMMIT.zip` y `.zip.sha256`. Compila React y recopila estáticos con configuración temporal aislada, sin consultar Supabase. Incluye backend, frontend compilado, estáticos, dependencias fijadas, scripts, plantillas, documentación y `RELEASE_MANIFEST.json` con hashes.

Excluye `.env.shared`, archivos `.env` reales, base SQLite, backups, documentos privados, claves/certificados locales, entorno virtual y `node_modules`. Las dependencias Python se instalan en Linux destino. No reemplaza un ZIP existente del mismo commit. El paquete no es una copia de seguridad de datos.

## Configuración privada

Copiar `.env.example` a `/etc/fundacion/backend.env`, propiedad del usuario del servicio y modo `600`, fuera de la web. Completar dominio/hosts HTTPS, conexión Supabase/TLS, SMTP, remitente autorizado, ruta privada, ClamAV y texto de conservación aprobado.

**Si conservas la base actual, conserva también su `DJANGO_SECRET_KEY` privada.** Cambiarla sin un procedimiento de rotación afecta firmas/sesiones y puede afectar secretos 2FA cifrados. No generar otra simplemente por pasar al hosting; no enviarla por chat o Git.

SMTP/587: `EMAIL_USE_TLS=true`, `EMAIL_USE_SSL=false`. TLS implícito/465: invertir los valores. No activar ambos. El proveedor debe autorizar `DEFAULT_FROM_EMAIL` y entregar los registros SPF/DKIM/DMARC correspondientes. No se inventaron registros DNS ni credenciales. [Configuración Django](https://docs.djangoproject.com/en/5.2/ref/settings/#email-use-tls).

## Instalación de referencia

Verificar el SHA-256 del ZIP antes de extraerlo en el directorio de instalación. Crear usuario de servicio y directorio privado persistente con permisos exclusivos, fuera del árbol público y de las carpetas reemplazadas al actualizar. Conservar la instalación anterior y sus datos hasta comprobar la nueva.

Ejemplo, ajustando rutas al plan real y ejecutando comandos Django como usuario `fundacion`:

```bash
python3.13 -m venv /srv/fundacion/.venv
/srv/fundacion/.venv/bin/pip install -r /srv/fundacion/backend/requirements.production.lock
cd /srv/fundacion
.venv/bin/python scripts/production-manage.py --env-file /etc/fundacion/backend.env check --deploy
.venv/bin/python scripts/production-manage.py --env-file /etc/fundacion/backend.env preflight_production
.venv/bin/python scripts/production-manage.py --env-file /etc/fundacion/backend.env migrate --plan
```

El wrapper lee exclusivamente variables admitidas, rechaza duplicados y no evalúa expresiones de shell. No realiza acciones implícitas. Antes de aplicar migraciones, generar/verificar respaldo de base y documentos según [el procedimiento de recuperación](#respaldo-y-recuperación-en-windows), revisar el plan y ejecutar `migrate` explícitamente con el mismo wrapper. No importar ni sobrescribir las tablas de Supabase. `setup_roles` solo se ejecuta explícitamente si la instalación lo necesita; no recrear cuentas existentes.

El ZIP trae estáticos; se pueden regenerar con `collectstatic --noinput` mediante el wrapper. Con servicios configurados:

```bash
.venv/bin/python scripts/production-manage.py --env-file /etc/fundacion/backend.env preflight_production --services
```

El diagnóstico JSON devuelve código distinto de cero ante bloqueos: configuración, modo producción, frontend, estáticos, directorio privado, CA configurada, conexión PostgreSQL, migraciones pendientes, handshake/autenticación SMTP y respuesta PONG de ClamAV. `--strict` considera también los avisos como bloqueos. Ejecutarlo con la identidad real del servicio. No imprime claves, modifica datos, crea archivos de prueba ni envía correos. El éxito no acredita entrega SMTP, DNS, certificado público, firmas del antivirus o restauración de copias.

Adaptar `deploy/fundacion.service.example` y `deploy/nginx.conf.example` a dominio, rutas y certificados reales. Revisar conflictos con otros sitios por `default_server`. La plantilla rechaza hosts HTTP inesperados, no expone documentos privados, da 404 a assets inexistentes y diferencia caché larga de assets con hash frente a `index.html`. CI comprueba sintaxis con certificados ficticios descartables; nunca usarlos en producción.

Validar `nginx -t` antes de habilitar la configuración. Gunicorn escucha localhost; ClamAV debe ser interno. Dominio, certificado, firewall, credenciales y límites se verifican en el hosting real. No usar `runserver` ni Vite como servidores públicos.

## Comprobación final en destino

1. `/api/health/live/` y `/api/health/ready/` por HTTPS.
2. Login/logout, roles, CSRF y recuperación de contraseña con entrega real a una cuenta autorizada.
3. Carga analizada y descarga privada; rechazo desde otro usuario y sin sesión. Verificar archivos existentes trasladados.
4. Matching, mapa, ubicación y enlaces WhatsApp con datos de prueba; abrir un enlace no significa enviar un mensaje.
5. Copia externa verificada, restauración en destino separado y supervisión de espacio, servicio, SMTP y antivirus.

Siguen pendientes datos reales: proveedor/plan, dominio, SMTP, credenciales/CA, traslado de documentos, política institucional y operación de copias. No se desactivaron controles para simular una publicación terminada.

Fuentes consultadas el 21-11-2026: [despliegue Django 5.2](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [SMTP Django](https://docs.djangoproject.com/en/5.2/ref/settings/#email-use-ssl) y [ClamAV](https://docs.clamav.net/).

Validación de la preparación inicial (commit `f7aa5c9`): 326 pruebas backend satisfactorias en PostgreSQL aislado, sin omisiones; once corresponden al diagnóstico, configuración y empaquetado. Django check y detección de migraciones sin cambios pendientes. Las pruebas de servicios usan dobles de prueba: no acreditan un proveedor SMTP, antivirus o hosting real. Consultar [validación vigente](VALIDACION_SEGURIDAD_PRO12.md).

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
