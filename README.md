# Fundación Apoyo Comunitario

Plataforma web para organizar voluntarios y su participación en actividades de la fundación.

**En desarrollo.** Actualmente funcionan el registro, la verificación de correo, el inicio de sesión y la edición del perfil. Todavía no está desplegada ni preparada para datos reales.

## Lo que ya funciona

- Portal responsive inspirado en Stitch.
- Registro con declaración de mayoría de edad y verificación por correo.
- Inicio/cierre de sesión y recuperación de contraseña.
- Edición del nombre, apellido, teléfono y comuna del usuario conectado.
- Permisos backend y control de segundo factor para operaciones administrativas.
- 14 pruebas automatizadas del backend.

**Por implementar:** habilidades, profesiones, disponibilidad, documentos privados, solicitudes, eventos, matching, invitaciones, participantes y respaldos. WhatsApp será manual asistido, sin API pagada.

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

El aviso de privacidad definitivo y el envío de correo real se configurarán antes de producción.

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
```

Las pruebas comprueban permisos, perfil propio, CSRF, registro sin privilegios, correo verificado, recuperación y límites de acceso.

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

- Validar PostgreSQL mediante CI: las primeras pruebas locales usaron SQLite.
- Completar la revisión visual en navegador; el frontend ya compila.
- Verificar el recorrido administrativo completo de MFA antes de producción.
- Incorporar módulos operativos, hardening, backups y restauración.

Consulta [las decisiones técnicas y los pendientes](docs/IMPLEMENTACION.md).
