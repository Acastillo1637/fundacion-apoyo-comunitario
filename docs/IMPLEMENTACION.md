# Fundación Apoyo Comunitario — identidad y base visual

Estado: desarrollo local. No habilitar datos reales todavía.

## Decisiones vigentes

- Una fundación: Fundación Apoyo Comunitario. Nombre configurable mediante FOUNDATION_NAME.
- React + Vite + JavaScript, Django + DRF y PostgreSQL como destino.
- Referencia visual: ZIP de Stitch entregado por el usuario. Sus textos y automatizaciones no constituyen requisitos.
- Paleta tomada de DESIGN.md: azul #0051d5, texto #142339 y fondos claros.
- No se incorporan OTP por WhatsApp, entrega/lectura simulada ni promoción autónoma de respaldos.
- Registro público de adultos declarados, sin campo editable de rol.
- Sesión en cookie HTTPOnly. Todas las mutaciones requieren CSRF, incluso antes de autenticarse.
- allauth gestiona enlaces de verificación, recuperación, TOTP y códigos de recuperación.
- Cuentas privilegiadas o con factores configurados pasan por el flujo de allauth. El endpoint JSON no omite MFA.
- Operaciones administrativas requieren permiso específico y autenticación MFA en la sesión.
- Desarrollo SQLite explícito por falta de PostgreSQL/Docker local. Producción no admite SQLite.

## Endpoints del primer bloque

| Método | Ruta | Acceso |
| --- | --- | --- |
| GET | /api/session/ | Público, emite token CSRF y nombre configurado |
| POST | /api/register/ | Público, consentimiento y declaración de mayoría de edad |
| POST | /api/login/ | Correo verificado, credenciales y límites |
| POST | /api/logout/ | CSRF |
| GET/PATCH | /api/profile/ | Perfil propio; campos permitidos explícitos |
| GET | /api/operations/ | Permiso view_volunteerprofile + MFA |
| GET/POST | /accounts/... | Flujos de verificación, recuperación y MFA de allauth |

## Pendientes antes de producción

- Aviso institucional y política de retención; consentimiento actual es para pruebas con datos ficticios.
- Dominio, SMTP real y logo oficial.
- Probar MFA y recuperación completos en navegador, y política de recuperación de administradores.
- Ejecutar la suite actualizada con PostgreSQL y completar Nginx/HTTPS antes de publicar.
- Endurecer límites por cuenta/red y evaluar diferencias temporales de respuestas para enumeración.
- Completar auditoría de cambios de privilegios y fallos de acceso; la actual registra solo acciones del primer bloque.
- Configurar inactividad, CSP, monitoreo, copias externas y restauración.
- Completar matching, postulaciones, invitaciones, notificaciones y demás módulos comprometidos.

## Límite del primer bloque

El dashboard muestra estado real de la cuenta y perfil. No existen todavía métricas de eventos o documentos. No hay usuarios de demostración con contraseñas públicas ni creación automática de superusuarios.

## Segundo bloque

Se incorporan catálogos administrables, habilidades/profesiones declaradas, franjas semanales y fechas no disponibles. El dashboard usa sus cantidades reales. Consulta [modelo, endpoints, permisos y limitaciones](VOLUNTARIOS.md).

## Tercer bloque

Se incorporan carga privada y versiones documentales, requisitos por perfil, descarga autorizada, cola de revisión con permiso y MFA, decisiones auditadas y vencimiento calculado. Consulta [el diseño documental y los pendientes para producción](DOCUMENTOS.md).

## Cuarto bloque

Se incorporan solicitudes públicas verificadas, decisiones administrativas, eventos con funciones/cupos y publicación con datos mínimos. Consulta [modelo, workflows, permisos y limitaciones](ACTIVIDADES.md).

## Administración de usuarios

Se incorpora la sección Usuarios en React, con invitaciones, roles acotados, activación/desactivación, auditoría e invalidación de sesiones. Consulta [controles y límites](USUARIOS.md).
