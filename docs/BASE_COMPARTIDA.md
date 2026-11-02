# Una base de datos para Amaro y Almendra

PostgreSQL administrado en Supabase es la base de datos definitiva del proyecto. Actualmente se utiliza como base compartida del equipo; el hosting también se conectará a Supabase. Django conserva usuarios, contraseñas, roles y reglas de negocio; no se cambia la autenticación a Supabase Auth. Consulta [la decisión de arquitectura y el texto para el informe](ARQUITECTURA_BD.md).

## 1. Crear el proyecto

1. Crea un proyecto en tu cuenta de Supabase y guarda su contraseña de base de datos.
2. Abre **Connect** y selecciona **Transaction pooler**, puerto **6543**. Copia los valores de host, database y user que muestra tu proyecto. Los scripts también admiten Session pooler (5432), pero la web compartida usa transacciones para evitar agotar las conexiones disponibles.
3. Copia `config/shared-database.env.example` a `.env.shared` en la raíz del proyecto. Completa los datos. No son la clave anon/public ni service_role: es la conexión PostgreSQL del backend.
4. Genera una clave privada una sola vez con el comando de la plantilla. Ambos equipos deben usar la misma `DJANGO_SECRET_KEY`. Comparte credenciales por un canal privado; nunca mediante el repositorio ni capturas.

`.env.shared` está excluido de Git. La plantilla no contiene credenciales. Los scripts leen valores de texto y no ejecutan el contenido del archivo.

## 2. Preparar las tablas — solo una persona

Con el proyecto nuevo y vacío, ejecuta desde la raíz:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 migrate
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 setup_roles
```

Estos comandos crean la estructura, no copian los datos de SQLite. Para importar una base local con las migraciones vigentes y sin archivos privados ni factores MFA, se dispone del comando:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 import_local_database
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 import_local_database --apply
```

El primer comando prepara un respaldo privado y comprueba el destino sin escribir en Supabase. El segundo crea otro respaldo consistente e importa en una transacción. Requiere un destino sin datos de aplicación; se cancela si encuentra registros. Conserva identificadores, hashes de contraseña, relaciones, permisos y correos verificados; reinicia las secuencias y compara conteos y contenido serializado antes de confirmar. No copia sesiones ni contadores temporales. Los respaldos contienen datos sensibles y quedan en `backups/`, excluido de Git.

No vuelvas a ejecutar la importación después de que haya terminado. No borres ni sobrescribas la base local. Si hay factores MFA o documentos cargados, el comando se detiene para preparar su traslado por separado.

## 3. Trabajar con los mismos datos — ambos equipos

Cada equipo necesita el mismo código y su `.env.shared` privado. Inicia Django con:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-shared-backend.ps1
```

React se inicia como siempre, desde `frontend` con `npm run dev`. Cada persona usa su propia cuenta dentro de la aplicación. Los cambios de usuarios, solicitudes, actividades y demás registros se guardan en la misma base.

`start-backend.ps1` también detecta `.env.shared` automáticamente y usa Supabase si existe. Si no existe, mantiene el inicio local con SQLite. `manage-local.ps1` siempre selecciona SQLite para las pruebas aisladas; no lo uses para administrar los datos compartidos. No ejecutes la suite de pruebas sobre Supabase: los permisos de la base y los datos compartidos no son un entorno de pruebas desechable.

Coordinen las migraciones: actualicen el código y una sola persona ejecuta `manage-shared.ps1 migrate`. Los scripts de inicio compartido no aplican migraciones automáticamente.

Si ya tenían configurado el puerto 5432, cambien únicamente `POSTGRES_PORT=6543` en cada `.env.shared` privado y reinicien Django con el script anterior. El host y las credenciales del mismo pooler se conservan. No se crea otra base ni se vuelven a importar los datos. Django devuelve las conexiones a un pool local de entre 1 y 4 conexiones por proceso al terminar cada petición; los cursores de servidor y las sentencias preparadas están desactivados para el modo por transacciones. Esto evita el error `EMAXCONNSESSION: max clients reached in session mode` observado al abrir varias vistas.

## 4. Documentos y correo

La base guarda referencias a los documentos; sus PDF e imágenes siguen en el almacenamiento privado de cada backend. Compartir PostgreSQL no comparte esos archivos. Para que ambos consulten los mismos documentos, el próximo paso es un backend de pruebas común con almacenamiento privado compartido, o integrar almacenamiento de objetos privado. No expongas la carpeta como archivos públicos.

Los mensajes de correo siguen saliendo en la terminal del equipo que ejecutó la acción. Compartir la base no configura SMTP ni publica la web.

## 5. Conectar el hosting a la base definitiva

La decisión aprobada es conservar PostgreSQL en Supabase. No se exportará la base para instalarla en el hosting. El servidor web recibirá las variables privadas de conexión al proyecto Supabase del entorno de producción, además de su configuración HTTPS, dominio, correo y almacenamiento privado.

Los scripts `start-shared-backend.ps1` y `manage-shared.ps1` son herramientas de desarrollo: fuerzan DEBUG y el correo de consola. No se usan para ejecutar producción. La plantilla `.env.example` documenta las variables que deberá cargar el servicio del backend en el hosting.

Antes de publicar, separar el entorno de pruebas del entorno de producción, configurar una cuenta de conexión con permisos mínimos y preparar respaldo y restauración de PostgreSQL y de los archivos privados. Las exportaciones lógicas mediante `pg_dump` quedan como herramienta de respaldo o recuperación, no como un traslado obligatorio al hosting. No se deben copiar indiscriminadamente los roles/esquemas internos administrados por Supabase.

Estado al 1 de noviembre de 2026: se conectó el proyecto configurado en `.env.shared` y se importaron 3 usuarios, 1 perfil de voluntario, 3 direcciones de correo, 9 registros de auditoría y los catálogos locales (1 tipo documental, 4 habilidades y 2 profesiones). Se compararon conteos y contenido tras la importación. No había documentos privados ni factores MFA para trasladar. SQLite se conservó intacto.

Referencias: [conexión PostgreSQL de Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres), [respaldos](https://supabase.com/docs/guides/platform/backups).

Después de actualizar esta versión, ejecuta `.venv\Scripts\python.exe -m pip install -r backend/requirements.lock` y reinicia Django. El pool acotado reutiliza las conexiones cifradas entre peticiones y evita repetir su apertura en cada clic. Los paneles conservan la última respuesta únicamente en la memoria del componente de la sesión y la actualizan al volver a abrirlos; no se guardan datos privados en localStorage.
