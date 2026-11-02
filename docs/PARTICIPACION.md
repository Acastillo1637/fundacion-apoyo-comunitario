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

## Voluntarios de respaldo

Cada participación distingue su asignación: titular o respaldo. Las anteriores se conservan como titulares. Los estados de invitación, confirmación, rechazo y cancelación son los mismos; la asignación se muestra explícitamente en los espacios del voluntario y de coordinación.

1. Desde Matching, la coordinación elige Invitar como titular o Invitar como respaldo. También puede proponer como respaldo a alguien que postuló o quedó en espera.
2. El voluntario debe aceptar la invitación como respaldo. Esa aceptación no ocupa un cupo titular, no confirma asistencia y no genera horas registradas.
3. Participantes y asistencia muestra los cupos disponibles por función y una lista de respaldos con paginación independiente. Se vuelve a comprobar su compatibilidad al consultarlos.
4. Cuando hay un cupo libre en la función del respaldo, la coordinación pulsa Activar respaldo. Solo se admite para un respaldo que ya aceptó y antes del inicio de la actividad.
5. Activar genera una nueva invitación como titular; no confirma al voluntario automáticamente. La persona puede aceptar o rechazar. La invitación vence a las 48 horas o al inicio del evento.
6. La aceptación final comprueba otra vez requisitos, restricciones, disponibilidad, cruces con otras participaciones titulares y capacidad. Si otra persona ocupó el cupo, pasa a lista de espera. Las invitaciones no reservan cupos.

Cancelar una participación no contacta ni promueve automáticamente a los respaldos: el cupo aparece disponible para revisión humana. Las invitaciones generan avisos internos. La preparación manual de WhatsApp sigue requiriendo consentimiento y teléfono registrado.

Un respaldo no bloquea por sí solo una participación titular en otro evento. Al activarlo se comprueba si adquirió otro compromiso confirmado; si se superpone, la activación se rechaza. Solo los titulares confirmados reciben la dirección exacta y pueden tener asistencia u horas registradas. Los avisos de cambios quedan en notificaciones y cada decisión se audita.

El API de participantes admite los filtros `assignment=primary|backup` y `status=confirmed`. La respuesta conserva indicadores del evento completo y entrega vacantes por función. `invite-backup` propone un respaldo a partir de una postulación/lista de espera y `activate-backup` crea la invitación titular. Ambas acciones exigen permiso de coordinación y revisión vigente.

La dirección exacta solo se entrega al participante confirmado, además de la coordinación autorizada. Los candidatos no exponen documentos o domicilios. La revisión documental continúa exigiendo un permiso específico y prohíbe revisar archivos propios. Las restricciones conservan motivo, actor e historial administrativo; bloquean nuevas postulaciones, invitaciones y confirmaciones. La coordinación revisa y cancela por separado compromisos confirmados anteriores.

## WhatsApp y notificaciones

Las notificaciones se guardan en la aplicación y se pueden marcar como leídas. No se envían correos ni WhatsApp automáticamente para invitaciones. Si el voluntario aceptó el contacto por WhatsApp y registró teléfono, la coordinación obtiene **Preparar WhatsApp**: abre un mensaje que la persona encargada decide enviar. No se simulan entrega ni lectura.

Al aprobar u observar un documento se notifica únicamente a su titular, una sola vez por decisión. La notificación no copia las observaciones privadas: el titular las consulta en Mis documentos. Los avisos nuevos pueden incluir un botón Ver detalle que abre documentos, participaciones o solicitudes propias; la autorización de cada destino sigue comprobándose en el backend.

## Restricciones temporales

Desde Voluntarios → Ver ficha, la coordinación puede aplicar, modificar o retirar una restricción. Cada operación exige motivo y una revisión vigente de la ficha; si otra persona la cambió, se devuelve 409 para evitar sobrescribirla. El historial conserva responsable, fecha, motivo y fechas de término anterior/nueva.

La fecha opcional de término se interpreta al final del día en America/Santiago. Si se deja vacía, el retiro es manual. Las restricciones existentes sin fecha se conservan como manuales. El backend calcula su vigencia cada vez que evalúa una postulación, una invitación o una confirmación: pasada la fecha ya no bloquea esas acciones, sin borrar el historial ni requerir una tarea programada. No se aplican sanciones automáticamente por rechazar invitaciones o registrar ausencias.

El voluntario ve su estado vigente y motivo tanto en el resumen como en Mis participaciones. Al aplicar, modificar o retirar una restricción recibe un aviso interno; el mero vencimiento no genera una notificación programada. Las participaciones anteriores se revisan por separado por la coordinación.

## Correcciones informativas de convocatorias publicadas

Antes del inicio, la coordinación puede corregir título, descripción pública y notas internas de un evento abierto. Se exige motivo y revisión vigente. El backend bloquea la fila del evento, comprueba el estado, registra los campos modificados y conserva las versiones anterior/nueva de los campos públicos. Las notas internas no se duplican en las instantáneas de contenido público.

Cambiar título o descripción genera un aviso interno a los usuarios activos con postulaciones, invitaciones vigentes, participaciones confirmadas (titulares y respaldos) o lista de espera, y al solicitante vinculado. Si una persona tiene ambos papeles, recibe un solo aviso. Las invitaciones vencidas y participaciones rechazadas/canceladas no se incluyen. Las notas y el motivo interno no se copian en las notificaciones. Si solo cambian notas internas, se conserva el historial sin generar avisos externos al equipo. Los avisos son internos a la aplicación; no se envía WhatsApp ni correo automáticamente.

La actualización, el historial y los avisos se guardan en la misma transacción. Si falla la operación, se revierten. Reintentar con una revisión antigua devuelve 409 y no duplica avisos. Los participantes consultan la descripción actual en Mis participaciones; el solicitante ve los eventos relacionados publicados desde Mis solicitudes, sin notas internas ni borradores.

Este flujo no cambia horarios, dirección, funciones, cupos ni requisitos, y no elimina participantes. Esos cambios requieren un flujo de modificación logística y reconfirmación todavía pendiente. Los eventos comenzados, finalizados o cancelados no admiten estas correcciones. El endpoint es `PATCH /api/activities/operations/events/<uuid>/`; `PUT` conserva su uso para editar borradores.

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
| GET | `/api/activities/participation-status/` | Estado y motivo vigentes del voluntario conectado |

## Validación y límites

Pruebas de acceso unificado, TOTP y recuperación, permisos, CSRF, separación de espacios, propiedad, requisitos, vencimiento, revisiones, lista de espera, privacidad, asistencia, renovación y cancelación. Una prueba de PostgreSQL enfrenta dos aceptaciones por el último cupo: una confirma y otra queda en espera.

Los catálogos son pequeños y se cargan completos para edición. La selección de candidatos pagina de 20 en 20 y evalúa cada candidato; no es un buscador geográfico. Las notificaciones muestran las 30 más recientes. Falta validar visualmente todo el recorrido en navegadores y móviles, y configurar la operación de producción (SMTP, HTTPS, respaldos y monitoreo) antes de usar datos reales.
