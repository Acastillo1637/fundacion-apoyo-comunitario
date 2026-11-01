# Dashboards y participación

## Acceso único

Todos los roles ingresan desde **Iniciar sesión** en React. Una cuenta con correo verificado y sin segundo factor configurado entra con correo y contraseña. Los roles administrativos ya no redirigen a otro formulario.

Si el titular activó TOTP o códigos de recuperación, el formulario pide el código en la misma pantalla. No se inicia una sesión antes de comprobarlo. Se usan los validadores de allauth, con protección contra reutilización; no se desactiva un factor existente. La configuración opcional de seguridad y Django Admin conservan las vistas de allauth; Django Admin sigue exigiendo MFA. Las APIs del portal exigen sus permisos y un registro de autenticación por contraseña válido para esa identidad, o MFA cuando está configurado.

## Espacios funcionales

| Espacio | Funciones |
| --- | --- |
| Voluntario | Resumen real, perfil, habilidades/profesiones, disponibilidad, documentos, oportunidades, postulación, invitaciones, participaciones, notificaciones |
| Solicitante | Resumen de solicitudes propias, perfil de persona/empresa/institución, nueva solicitud y seguimiento, notificaciones |
| Secretaría | Resumen operativo, solicitudes/eventos, revisión documental, candidatos, invitaciones, participantes, asistencia y restricciones |
| Administración | Cantidades reales de cuentas, gestión de usuarios/roles, catálogos editables dentro de React y perfil de cuenta |

Las cuentas con varios roles cambian de espacio explícitamente. No se inventan datos para completar gráficos. Los resúmenes consultan filas existentes y respetan permisos; el solicitante solo cuenta solicitudes vinculadas a su perfil.

## Circuito de participación

1. La coordinación publica un evento con funciones y cupos.
2. El voluntario postula a una función desde Oportunidades; o la coordinación lo invita desde Participantes y asistencia.
3. Los candidatos muestran habilidades, documentos vigentes hasta el término del evento, disponibilidad, restricciones y cruces con otras participaciones confirmadas. Proximidad significa coincidencia de comuna, sin domicilio personal.
4. La invitación genera una notificación interna. Vence a las 48 horas o al comienzo del evento, lo que ocurra primero. Puede renovarla la coordinación si venció o la participación terminó en rechazo/cancelación.
5. El voluntario acepta o rechaza desde su cuenta. Aceptar vuelve a comprobar los requisitos y asigna un cupo; si está completo, queda en lista de espera. Las postulaciones requieren confirmación de la coordinación.
6. Se permite retirar una participación antes del inicio. Un cupo liberado se asigna mediante confirmación manual de la lista de espera, con nueva comprobación de requisitos; no hay promoción automática.
7. Desde el inicio del evento, la coordinación registra presente/ausente para confirmados. Las correcciones quedan auditadas.
8. Cancelar un evento cancela sus participaciones activas y genera notificaciones.

Una persona tiene una sola participación por evento. Puede participar en varios eventos si no se superponen. La asignación bloquea evento y perfil en PostgreSQL, evitando exceder cupos y confirmar cruces concurrentes. Las decisiones llevan revisión; una pantalla obsoleta devuelve 409.

La dirección exacta solo se entrega al participante confirmado, además de la coordinación autorizada. Los candidatos no exponen documentos o domicilios. La revisión documental continúa exigiendo un permiso específico y prohíbe revisar archivos propios. Las restricciones conservan motivo, actor e historial administrativo; bloquean nuevas postulaciones, invitaciones y confirmaciones. La coordinación revisa y cancela por separado compromisos confirmados anteriores.

## WhatsApp y notificaciones

Las notificaciones se guardan en la aplicación y se pueden marcar como leídas. No se envían correos ni WhatsApp automáticamente para invitaciones. Si el voluntario aceptó el contacto por WhatsApp y registró teléfono, la coordinación obtiene **Preparar WhatsApp**: abre un mensaje que la persona encargada decide enviar. No se simulan entrega ni lectura.

## Endpoints

| Método | Ruta | Acceso |
| --- | --- | --- |
| GET | `/api/workspace-summary/?portal=...` | Espacio asignado; resúmenes propios o permiso administrativo |
| PATCH | `/api/account-profile/` | Nombre propio, revisión, sin edición de acceso |
| GET/POST/PUT | `/api/management/catalogs/<skills\|professions\|documents>/` | Permiso específico del catálogo |
| GET/POST | `/api/operations/volunteers/` | Coordinación; restricciones con motivo |
| GET/POST | `/api/activities/participations/` | Voluntario; consulta propia/postulación |
| POST | `/api/activities/participations/<uuid>/decision/` | Titular o coordinación según acción |
| GET/POST | `/api/activities/operations/events/<uuid>/participants/` | Coordinación; listado/invitación |
| GET | `/api/activities/operations/events/<uuid>/positions/<id>/candidates/` | Coordinación |
| GET/POST | `/api/activities/notifications/` | Notificaciones propias; marcar leídas |

## Validación y límites

Pruebas de acceso unificado, TOTP y recuperación, permisos, CSRF, separación de espacios, propiedad, requisitos, vencimiento, revisiones, lista de espera, privacidad, asistencia, renovación y cancelación. Una prueba de PostgreSQL enfrenta dos aceptaciones por el último cupo: una confirma y otra queda en espera.

Los catálogos son pequeños y se cargan completos para edición. La selección de candidatos pagina de 20 en 20 y evalúa cada candidato; no es un buscador geográfico. Las notificaciones muestran las 30 más recientes. Falta validar visualmente todo el recorrido en navegadores y móviles, y configurar la operación de producción (SMTP, HTTPS, respaldos y monitoreo) antes de usar datos reales.
