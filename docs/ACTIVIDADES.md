# Solicitudes y eventos

> Actualización de acceso y funciones: el portal usa un inicio de sesión único para todos los roles. Las cuentas sin MFA configurado entran con contraseña; las que lo activaron validan el código en la misma pantalla. Django Admin conserva su requisito MFA. Los controles de roles y propiedad siguen vigentes. Consulta [dashboards y participación](PARTICIPACION.md) para el comportamiento actual, que reemplaza las referencias anteriores a redirección obligatoria y módulos de participación pendientes.

## Alcance

Se implementa recepción pública, verificación del correo, revisión administrativa, creación de uno o varios eventos por solicitud, funciones/cupos, publicación, cancelación y cierre. No hay todavía postulaciones, participantes, matching, invitaciones ni mensajes de WhatsApp. Los cupos publicados son definidos, no un contador de plazas libres.

## Modelo

- ServiceRequest: identidad de contacto, tipo persona/empresa/institución, organización, necesidad, cantidad, horario, dirección, comuna, habilidades y consentimiento fechado.
- RequestTransition: estado anterior/nuevo, actor, motivo y fecha.
- Event: solicitud aprobada de origen, título y descripción públicos, horario, dirección privada, comuna, notas internas, estado y revisión.
- EventPosition: función única por evento, cupos, habilidades obligatorias y documentos adicionales.
- EventTransition: historial de cambios de estado con actor, motivo y fecha.

Las habilidades aportan sus requisitos documentales por relación; se muestran aparte de los documentos adicionales de la función y se deberán evaluar en conjunto en el matching. No se copia la descripción privada del solicitante al campo público: el operador debe redactarla/revisarla explícitamente.

## Workflows

Solicitud: pendiente → en revisión → aprobada/rechazada. Solo se aprueba si el correo está verificado y la fecha solicitada sigue vigente. Rechazo exige motivo. Los estados terminales no se reabren en esta etapa.

Evento: borrador → abierto → finalizado; borrador/abierto pueden pasar a cancelado con motivo. Para abrir se exige fecha futura, funciones y requisitos activos. Finalizar exige que termine el horario. Solo se editan borradores; sus funciones aún no tienen referencias desde participaciones. Antes de introducir participantes se conservarán sus identificadores al editar, en vez de reemplazar el conjunto.

No hay borrado por API. Las transiciones y las ediciones bloquean la fila del recurso y comprueban una revisión enviada por el cliente; un cambio obsoleto devuelve 409. Historial y auditoría se escriben en la misma transacción. Una prueba de PostgreSQL enfrenta dos publicaciones simultáneas: debe producir 200 y 409, y una sola transición.

## Horarios y límites

Se reciben fecha y horas locales de America/Santiago, y se guardan instantes con zona horaria. Las actividades son de un solo día en esta etapa. Se rechazan horas ambiguas/inexistentes por cambio de hora en vez de interpretarlas silenciosamente.

Máximo: 500 voluntarios solicitados, 20 funciones por evento, 500 cupos totales y 30 requisitos por lista. Las listas se acotan antes de consultar los catálogos. Los endpoints paginan de 20 en 20.

## Verificación y correo

La solicitud usa una clave UUID de envío, conservada por el formulario ante reintentos. Repetirla no crea otra solicitud ni modifica sus datos originales. Si falla el correo, se conserva pendiente y se puede reintentar la entrega usando el mismo formulario.

Se usa el firmador con timestamp de Django, sal específica, UUID de solicitud y nonce, con vencimiento de 48 horas. Confirmar es idempotente y no equivale a aprobar. El enlace usa PUBLIC_APP_URL configurado por el operador, no el host suministrado por un visitante. En producción solo admite HTTPS.

El token viaja en el fragmento del enlace, que no llega en la ruta de las peticiones HTTP. El usuario confirma y React lo envía por POST con CSRF; después lo elimina de la barra de dirección. No se devuelve al público información de contacto ni detalle privado del expediente.

En desarrollo el correo se imprime en la terminal; las pantallas lo explican. En producción requiere SMTP, dominio y configuración de remitente reales. El envío es síncrono y tiene timeout de 10 segundos. Se deberá incorporar outbox/worker antes de escalar: no se garantiza entrega exactamente una vez y una caída entre envío y confirmación de transacción puede provocar reenvío.

## Acceso y abuso

Formularios públicos: sin cuenta, pero con CSRF explícito incluso para anónimos. No basta con la autenticación de sesión de DRF, porque omite ese control para anónimos. La creación se limita a 5 intentos por IP/15 minutos y la verificación a 15; hay un campo trampa y topes de tamaño de campos. Estos controles no sustituyen protección en el proxy ni una defensa distribuida ante bots.

Operaciones: permiso activities.manage_operations y MFA de la sesión vinculado al usuario. Secretaría y Administrador general lo reciben con setup_roles. Conocer el UUID no concede acceso. La API pública de oportunidades solo muestra eventos abiertos futuros, título, descripción revisada, fecha, comuna, funciones, cupos y requisitos. Excluye contacto, dirección exacta, notas e identificador del expediente origen.

La minimización estructural no detecta datos personales pegados en texto libre: el operador es responsable de revisar la descripción antes de publicarla. Auditoría registra actor, acción, recurso y fecha; no copia cuerpos ni tokens.

## Endpoints

Públicos:

- GET /api/activities/public-options/
- POST /api/activities/requests/
- POST /api/activities/request-verification/
- GET /api/activities/public-events/

Con permiso y MFA, bajo /api/activities/operations/:

- GET options/
- GET requests/ y requests/<uuid>/
- POST requests/<uuid>/transition/
- POST requests/<uuid>/events/
- GET events/ y GET/PUT events/<uuid>/
- POST events/<uuid>/transition/

## Evidencia y pendientes

Las pruebas cubren recorrido completo, idempotencia de envío/verificación, fallo y reintento de correo, CSRF anónimo, permisos/MFA, estados, revisiones, requisitos retirados, horario y privacidad de publicación.

Pendiente: revisión visual/móvil, interfaz de seguimiento del solicitante, modificaciones logísticas con reconfirmación de participantes, notificaciones internas, retención y eliminación de expedientes, limitación de creación de eventos y procesamiento asíncrono del correo. El siguiente bloque funcional es matching y, después, postulaciones/invitaciones/participantes con cupos transaccionales.

Las correcciones informativas de convocatorias abiertas (título, descripción y notas internas) ya cuentan con revisión, motivo, historial y avisos internos. Consulta el flujo vigente en [PARTICIPACION.md](PARTICIPACION.md). Los cambios de horario, ubicación y dotación siguen protegidos.
