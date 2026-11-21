# Fundación Apoyo Comunitario

**Conectamos personas, multiplicamos la ayuda.**

Sistema de gestión de voluntariados PRO-12: React/Vite, Django REST Framework y PostgreSQL en Supabase. La autenticación pertenece a Django; no se usa Supabase Auth. El código funciona en desarrollo y está preparado para instalarse, pero todavía no hay hosting contratado ni publicación verificada.

## Ejecutar en Windows

Requisitos: Python 3.13 y Node.js 22.22.2 o 24.15 o superior. Ejecuta desde la raíz del repositorio; usa dos terminales.

Primera instalación o cambio de dependencias:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
npm --prefix frontend ci
```

Si ya tienes `.env.shared`, consérvalo: no crees otra base ni vuelvas a importar los datos. Para conectar otro equipo, copia `config/shared-database.env.example` a `.env.shared` y completa los datos por un canal privado. Consulta [base compartida](docs/BASE_COMPARTIDA.md).

Terminal 1 — Django:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

Terminal 2 — React:

```powershell
npm --prefix frontend run dev
```

Abre **http://127.0.0.1:5173/**. Django escucha en 8000; Vite dirige las llamadas al backend. Detén ambos con `Ctrl+C`. `ExecutionPolicy Bypass` afecta únicamente al proceso iniciado.

El inicio detecta `.env.shared` y usa Supabase. En ese modo **no aplica migraciones ni crea roles automáticamente**. Tras actualizar, una persona revisa el plan y ejecuta, con respaldo cuando corresponda:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 migrate --plan
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 migrate
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 setup_roles
```

Sin `.env.shared`, el inicio usa SQLite local y prepara sus tablas/roles. SQLite está reservado al desarrollo y las pruebas.

## Configuración de cada entorno

| Entorno | Configuración | Cómo se carga |
|---|---|---|
| Desarrollo con Supabase | `.env.shared`, desde `config/shared-database.env.example` | Scripts `start-backend.ps1` o `manage-shared.ps1` |
| Pruebas/local aislado | Variables temporales de `manage-local.ps1` | Siempre SQLite; nunca la base compartida |
| Hosting | `.env.example` copiado fuera de la web, por ejemplo `/etc/fundacion/backend.env` | Servicio del hosting/systemd o `production-manage.py --env-file` |

Django no carga automáticamente archivos `.env`. No copies la plantilla de producción a `.env.shared`: tienen propósitos y lectores diferentes. Las claves nunca llevan prefijo `VITE_` ni se suben a GitHub. [Variables, formatos y valores necesarios](docs/CONFIGURACION.md).

## Funciones disponibles

- Registro adulto de voluntarios y solicitantes, acceso inmediato sin confirmación obligatoria de correo, recuperación y seguridad de cuenta con MFA opcional en el portal.
- Espacios por rol: voluntariado, solicitante, secretaría y administración. Usuarios, catálogos, restricciones y auditoría desde la web.
- Habilidades, profesiones, disponibilidad, ubicación aproximada, consentimiento de contacto y documentos privados versionados.
- Solicitudes, convocatorias, requisitos y cupos por función; postulaciones, invitaciones, asistencia, espera y respaldos.
- Matching determinista configurable, distancias aproximadas en línea recta y mapa sincronizado. Geoapify calcula referencias por dirección con consentimiento; no se conserva el domicilio completo.
- WhatsApp por enlaces oficiales: envío humano y seguimiento manual, sin automatización ni confirmación de entrega.
- Notificaciones con historial y lectura individual; solicitudes de privacidad para todos los administradores activos y exportación de datos propios.

La solicitud pública anónima mantiene su verificación independiente. En desarrollo los correos aparecen en la terminal: **no llegan a Gmail sin SMTP**. Los permisos, privacidad y límites están descritos en las [guías de módulos](docs/README.md).

Los archivos privados viven fuera de PostgreSQL. Compartir Supabase no comparte PDF/imágenes entre equipos. No publiques `backend/private_media/` ni los respaldos.

## Probar y administrar

Usa datos ficticios. Los accesos generados y respaldos se guardan de forma privada, fuera de Git; no hay una contraseña universal. [Datos de demostración](docs/DATOS_DEMO.md).

El administrador asigna roles desde la web; el registro público no permite elegir privilegios administrativos. Cada titular acepta sus propios consentimientos. Django Admin conserva controles adicionales de MFA y no es la interfaz habitual de secretaría. [Usuarios](docs/USUARIOS.md) y [seguridad de cuenta](docs/NAVEGACION_SEGURIDAD.md).

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-backend.ps1
npm --prefix frontend test
npm --prefix frontend run build
```

El primer comando usa SQLite y omite comprobaciones exclusivas de PostgreSQL. GitHub Actions ejecuta la suite completa sobre PostgreSQL aislado, auditorías de dependencias, frontend, Gunicorn y validación Nginx. Nunca ejecutes pruebas sobre `.env.shared`. [Resultados y alcance de validación](docs/VALIDACION_SEGURIDAD_PRO12.md).

## Preparar el hosting

```powershell
.venv\Scripts\python.exe scripts/build-release.py
```

Con un checkout limpio y las dependencias instaladas, crea un ZIP identificado por commit en `backups/releases/`, con frontend/estáticos compilados y manifiesto SHA-256. Excluye secretos, base de datos y documentos. La plantilla única de producción es **`.env.example`**.

Faltan el proveedor/plan, dominio/HTTPS, SMTP real, antivirus/almacenamiento privado, copias externas y aprobación del plazo de conservación. Supabase continúa como base definitiva. [Instalación, requisitos del plan y recuperación](docs/DESPLIEGUE_PRO12.md).

## Documentación

El [índice de documentación](docs/README.md) distingue guías vigentes de registros históricos. Cada tema tiene una guía principal; las evidencias y resultados antiguos se conservan con su contexto, sin presentarlos como estado actual.
