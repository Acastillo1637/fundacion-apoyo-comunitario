# Fundación Apoyo Comunitario

Plataforma web para organizar voluntarios y su participación en actividades de la fundación.

**En desarrollo.** Funcionan registro, correo, acceso, perfil, declaración de habilidades y profesiones, y disponibilidad. Todavía no está desplegada ni preparada para datos reales.

## Lo que ya funciona

- Portal responsive inspirado en Stitch.
- Registro con declaración de mayoría de edad y verificación por correo.
- Inicio/cierre de sesión y recuperación de contraseña.
- Edición del nombre, apellido, teléfono y comuna del usuario conectado.
- Selección de habilidades, profesiones y oficios desde catálogos administrables.
- Franjas semanales y fechas completas no disponibles, con validación de superposiciones.
- Catálogos con activación/desactivación y asociación de requisitos documentales.
- Permisos backend y control de segundo factor para operaciones administrativas.
- Carga privada de PDF, JPEG y PNG, con versiones, descarga autorizada y revisión documental.
- Formulario público de solicitud y verificación de correo del solicitante.
- Revisión administrativa, eventos en borrador, publicación y cancelación.
- Cupos por función, requisitos y listado público sin datos de contacto o dirección exacta.
- 110 pruebas del backend, incluidas dos de concurrencia que requieren PostgreSQL, y 5 del cliente API.

**Por implementar:** matching, postulaciones, invitaciones, participantes, respaldos y notificaciones internas. WhatsApp será manual asistido, sin API pagada.

## Cómo abrirlo en tu computador

Instrucciones para **Windows y PowerShell**. Necesitas Python 3.13 y Node.js 22.12 o superior.

Mantén **dos terminales abiertas**: una ejecuta Django y otra React. No necesitas Docker ni contratar un servidor para probar esta versión.

### 1. Abre la carpeta del proyecto

En VS Code abre la carpeta que contiene este README. Si usas la ubicación original, en PowerShell ejecuta:

```powershell
cd 'D:\Visual Studio code\Fundacion_Voluntarios'
```

Si descargaste el repositorio en otra carpeta, usa esa ubicación. Los siguientes comandos parten desde la raíz del proyecto.

### 2. Instala las dependencias de Python

Esto se hace la primera vez o cuando cambien las dependencias:

```powershell
python -m venv .venv
python -m pip --python .venv install -r backend/requirements.lock
```

Si el primer comando falla en `ensurepip`, utiliza esta alternativa:

```powershell
python -m venv --without-pip .venv
python -m pip --python .venv install -r backend/requirements.lock
```

`.venv` guarda las dependencias de Python del proyecto. No se sube a GitHub.

### 3. Inicia Django — terminal 1

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

El script prepara la base de datos local, crea los grupos de permisos y arranca Django en `http://127.0.0.1:8000`. Deja esta terminal abierta.

`-ExecutionPolicy Bypass` afecta solo a ese proceso; no cambia permanentemente la política de Windows.

### 4. Inicia React — terminal 2

Abre otra terminal en la raíz del proyecto:

```powershell
cd frontend
npm ci
npm run dev
```

`npm ci` instala las dependencias de JavaScript. Solo necesitas repetirlo cuando descargues cambios en las dependencias.

### 5. Abre la aplicación

Visita **http://127.0.0.1:5173/** en tu navegador.

Usa siempre esa dirección. React se comunica con Django a través de ella. Si Django está apagado, aparecerá un aviso y no podrás registrarte.

Para detener el proyecto, presiona **Ctrl + C** en cada terminal.

## Cómo probar el registro

En desarrollo, **los correos no se envían a Internet**: se muestran en la terminal de Django.

1. Pulsa **Ser voluntario** y completa el registro con datos ficticios.
2. Busca el mensaje de verificación en la terminal 1.
3. Copia el enlace en el navegador. Si contiene el puerto `8000`, reemplázalo por `5173` conservando el resto del enlace.
4. Confirma el correo en la página que se abre.
5. Vuelve al portal e inicia sesión.

La recuperación de contraseña funciona del mismo modo. No compartas enlaces de verificación o recuperación.

Si aparece un aviso de seguridad de sesión, recarga la página y vuelve a intentarlo. En desarrollo se permiten únicamente los orígenes `http://127.0.0.1:5173` y `http://localhost:5173`; todos los formularios siguen requiriendo token CSRF. Usa la misma dirección durante todo el recorrido y reinicia Django después de cambiar configuración.

El aviso de privacidad definitivo y el envío de correo real se configurarán antes de producción.

## Cómo probar habilidades y disponibilidad

Si estás actualizando una copia que ya tenías, detén Django con **Ctrl + C** y vuelve a ejecutar el comando del paso 3. El script aplicará las migraciones nuevas y actualizará los grupos de permisos.

En otra terminal, desde la raíz, puedes cargar ejemplos de catálogos:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manage-local.ps1 seed_catalogs
```

Este comando añade ejemplos editables de habilidades y profesiones; no crea usuarios ni usa datos personales. Solo funciona en desarrollo y no impone los requisitos documentales reales de la fundación.

Después de entrar al portal:

1. Abre **Habilidades y profesión**, selecciona opciones y guarda.
2. Abre **Disponibilidad**, agrega una franja, por ejemplo lunes de 18:00 a 22:00, y guarda.
3. Puedes agregar varios rangos en un día, siempre que no se superpongan.
4. Agrega una fecha en la que no puedas participar: bloqueará ese día completo.
5. Recarga para comprobar que los cambios se conservaron.

Los horarios corresponden a **Santiago de Chile**. Cada franja empieza y termina dentro del mismo día. No se solicitan tiempos de traslado. Declarar una profesión no significa acreditarla.

Si otra sesión guardó cambios antes que tú, verás un aviso: pulsa **Recargar**, revisa la información y vuelve a editar. Recargar descarta los cambios que aún no guardaste.

## Cómo administrar los catálogos

La primera interfaz administrativa usa el panel de Django; allí puedes crear, editar y desactivar habilidades, profesiones y tipos documentales. No se permite borrarlos desde el panel para conservar sus referencias.

Para crear tu cuenta administrativa local:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\manage-local.ps1 createsuperuser
```

Introduce tú mismo el correo y la contraseña en la terminal. Luego:

1. Visita **http://127.0.0.1:5173/accounts/login/** y verifica tu correo cuando se solicite. El enlace estará en la terminal de Django.
2. Configura una aplicación autenticadora en **http://127.0.0.1:5173/accounts/2fa/** y conserva los códigos de recuperación de forma privada.
3. Cierra sesión y vuelve a entrar completando el segundo factor.
4. Visita **http://127.0.0.1:5173/admin/volunteers/**.

El acceso administrativo requiere MFA. Los demás usuarios necesitan además los permisos específicos y habilitación de acceso al panel; pertenecer a un grupo por sí solo no concede todos los privilegios. El superusuario es una cuenta técnica de desarrollo, no la cuenta habitual de la secretaria.

## Cómo probar documentos privados

Si actualizaste el proyecto, instala primero las nuevas dependencias y reinicia Django:

```powershell
python -m pip --python .venv install -r backend/requirements.lock
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

El script aplica las migraciones y asigna el permiso documental a los grupos administrativos existentes.

1. Entra como voluntario y abre **Mis documentos**.
2. Elige un tipo documental y carga un **PDF o imagen ficticia** de hasta 10 MB.
3. Comprueba el estado pendiente, el historial y la descarga.
4. Para revisar, entra con **otra cuenta** que tenga permiso documental y MFA, y abre **Revisión documental**. Un administrador no puede revisar sus propios archivos.
5. Descarga el archivo, valida o rechaza e indica observación y vencimiento cuando corresponda. El rechazo exige un motivo.
6. Vuelve a la cuenta del voluntario para consultar la decisión. Cargar otra versión no borra el historial y exige una nueva revisión.

Cada voluntario tiene una cuota inicial de 50 MB incluyendo versiones históricas, y un máximo de 100 versiones. El documento vence al terminar su fecha de validez en Santiago de Chile. Las habilidades y profesiones todavía no se marcan automáticamente como acreditadas; esa evaluación se incorporará con el matching.

Los archivos se guardan en `backend/private_media/documents/`, fuera de las rutas públicas y excluidos de Git. No publiques esa carpeta ni la configures como `/media/` público.

**Antivirus:** ClamAV no está instalado en el entorno local. Los archivos de prueba muestran "Sin análisis antimalware". En producción las cargas exigen ClamAV disponible en una red interna; si no está configurado, se rechazan con 503. Las validaciones de estructura no garantizan ausencia de malware. Consulta [el diseño documental](docs/DOCUMENTOS.md).

## Cómo probar solicitudes y eventos

Reinicia Django con el script del paso 3 para aplicar las migraciones y permisos nuevos. Mantén React ejecutándose en la otra terminal.

1. Desde el menú de la web abre **Solicitar apoyo**. No necesitas iniciar sesión.
2. Completa el formulario con datos ficticios, una fecha futura y horarios dentro del mismo día.
3. Envía la solicitud y revisa el mensaje en la **terminal de Django**. No llega a Gmail en este entorno.
4. Copia el enlace completo, incluido el fragmento `#confirm-request=...`, ábrelo y pulsa **Confirmar mi correo**. Esa verificación no aprueba la solicitud.
5. Entra con una cuenta administrativa mediante `/accounts/login/`, completa MFA y abre **Solicitudes y eventos**.
6. Abre la solicitud, pulsa **Comenzar revisión** y después aprueba o rechaza. Rechazar exige una justificación; aprobar exige correo verificado.
7. Desde una solicitud aprobada pulsa **Crear evento**. Revisa fecha/dirección y redacta una descripción pública sin información personal.
8. Define una o varias funciones, sus cupos y requisitos; guarda como borrador.
9. En **Eventos**, abre el borrador y pulsa **Abrir convocatoria**.
10. Comprueba la publicación en **Oportunidades** o en la página de inicio: se muestran comuna y requisitos, pero no dirección exacta ni contacto del solicitante.

Una solicitud puede generar varios eventos. Los borradores se pueden editar; los abiertos no se editan en esta etapa hasta implementar el flujo de comunicación de cambios. Se puede cancelar con motivo; finalizar exige que haya terminado el horario. Todavía no hay postulaciones ni asignación automática de participantes.

Para producción se necesita `PUBLIC_APP_URL` con el dominio HTTPS real, además de un servicio de correo configurado. No uses una dirección enviada por el visitante para construir enlaces. Más detalles en [docs/ACTIVIDADES.md](docs/ACTIVIDADES.md).

## Base de datos

- **Desarrollo local:** SQLite, un archivo que el script crea automáticamente. Así puedes comenzar sin instalar PostgreSQL.
- **Servidor Cloud-2:** PostgreSQL. La configuración de producción no permite SQLite.

Las bases de datos locales no se suben al repositorio.

## Cómo ejecutar las pruebas

Desde la raíz, en una terminal adicional:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-backend.ps1
```

Para comprobar la compilación de React:

```powershell
cd frontend
npm run build
npm test
```

Las pruebas comprueban permisos, perfil propio, CSRF, registro sin privilegios, correo verificado, recuperación, catálogos, horarios, fechas, límites y prevención de sobrescrituras entre sesiones.

## Carpetas

| Carpeta | Para qué sirve |
| --- | --- |
| `backend/` | Django, API, usuarios, permisos y migraciones |
| `frontend/` | React, pantallas y estilos |
| `scripts/` | Inicio local y pruebas |
| `docs/` | Decisiones técnicas y pendientes |
| `.github/workflows/` | Comprobaciones automáticas en GitHub |

## GitHub y publicación

GitHub guarda el código y su historial. **Subirlo no publica la aplicación en Internet.** El despliegue en V2Networks se hará después, con dominio, HTTPS, PostgreSQL y backups.

No subas `.env`, contraseñas, claves privadas, bases de datos, documentos personales ni backups. `.env.example` contiene nombres de variables sin secretos reales.

## Pendientes importantes

- Las pruebas locales usan SQLite. Las dos de concurrencia real se ejecutan únicamente con PostgreSQL, mediante el workflow de GitHub.
- Completar la revisión visual en navegador; el frontend ya compila.
- Verificar el recorrido administrativo completo de MFA antes de producción.
- Incorporar módulos operativos, hardening, backups y restauración.

Consulta [las decisiones técnicas y los pendientes](docs/IMPLEMENTACION.md).
