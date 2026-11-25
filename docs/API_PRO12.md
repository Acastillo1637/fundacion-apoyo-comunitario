# API de las incorporaciones PRO-12

Base `/api/`. JSON UTF-8; sesión Django en cookie HttpOnly. Las escrituras requieren CSRF (`X-CSRFToken`) y sesión autenticada. Se mantienen las API anteriores descritas en ACTIVIDADES, DOCUMENTOS, PARTICIPACION y USUARIOS. No existe autenticación con claves públicas de Supabase.

Actualización 21-11-2026: los listados de operaciones `activities/operations/requests/` y `activities/operations/events/` aceptan `q` (máximo 120 caracteres), `status` y `period=upcoming|past`; los filtros se aplican antes de paginar, también con `compact=1`. `activities/notifications/` acepta `page` y `unread_only=0|1`; devuelve `results`, `total`, `page`, `page_size=30` y `unread` global. POST admite exclusivamente `{read_id: ID_PROPIO}` o `{read_all:true}`. El ID ajeno devuelve 404; filtros, páginas o cuerpos inválidos devuelven 400.

WhatsApp, 25-11-2026: contactos y candidatos autorizados incluyen `delivery`: `opened` y `sent` contienen `at`, `actor_id` y `actor`, o `null`; `send_confirmed` distingue confirmación manual y `can_confirm_send` indica si puede registrarse. Candidatos incluyen un resumen `contact` o `null`. Son datos de la ronda actual, reconstruidos desde la auditoría. `action=start` registra solo apertura solicitada y devuelve `whatsapp_url`; `action=sent` exige una apertura previa, no cambia aceptaciones ni cupos y registra la confirmación manual. Una confirmación repetida devuelve 409. Se conservan revisiones, CSRF y permisos operativos; propietario, responsable y timestamps no se aceptan del cliente.

| Método y ruta | Autorización y propósito |
|---|---|
| GET/PUT `volunteer/location/` | Solo voluntario sobre su propio perfil. Comuna, sector, coordenadas aproximadas y revisión. |
| POST `volunteer/location/address/` | Solo voluntario sobre su propio perfil; dirección, comuna, sector, consentimiento y revisión. Calcula y guarda referencia con Geoapify o devuelve opciones a confirmar. [Contrato, errores y privacidad](GEOCODIFICACION_DOMICILIOS.md). |
| GET/PUT `volunteer/contact-preferences/` | Titular voluntario; teléfono, consentimiento WhatsApp, revisión. |
| GET `maps/config/` | Voluntario o coordinación autorizada; configuración de mapa y búsqueda habilitada. |
| POST `maps/search/` | Mismos roles; `{ "query": "Plaza de Armas, Santiago" }`. Solo lugares públicos. 503 deshabilitado/proveedor fallido; 429 límite compartido. |
| GET/PUT `management/matching-policy/` | Administración general; pesos, límites, motivo y revisión. |
| PUT `activities/operations/events/{uuid}/location/` | Coordinación; ubicación de convocatoria futura en borrador/abierta, motivo y revisión. |
| GET `activities/operations/events/{uuid}/positions/{id}/candidates/` | Coordinación; `page`, `eligible_only=1` para elegibles. Clasificación global, explicaciones y coordenadas privadas autorizadas. |
| GET/POST `activities/operations/events/{uuid}/contacts/` | Coordinación; listar o crear seguimiento de un candidato elegible. |
| POST `activities/operations/contacts/{id}/action/` | Coordinación; transición manual, intento de contacto, renovación o confirmación de cupo. |
| POST `operations/volunteers/{id}/whatsapp/` | Coordinación; contacto general consentido, sin actividad; solo intento. |
| GET/POST `privacy/requests/` | Titular; `scope=mine` por defecto. `scope=all` solo administración. |
| POST `privacy/requests/{id}/review/` | Administración; respuesta y transición con revisión. |
| GET `privacy/export/` | Descarga JSON del titular; sin contraseñas ni secretos MFA. |
| GET/HEAD `health/live/` | Público; proceso disponible, sin consulta de base. |
| GET/HEAD `health/ready/` | Público; consulta mínima de base, 503 genérico si falla. |

Ejemplo de ubicación propia:

```json
{"commune":"Santiago","sector":"Centro","latitude":-33.451,"longitude":-70.661,"revision":0}
```

Se guarda redondeada a `-33.45,-70.66`. Borrar ambas coordenadas enviando `null` es válido; una sola coordenada, NaN, infinito o valores fuera de rango se rechazan. Las ubicaciones privadas no se incorporan al DTO público de eventos.

Configuración de matching (utilizar la revisión real obtenida con GET):

```json
{"skills_weight":60,"experience_weight":15,"distance_weight":25,"distance_limit_km":50,"experience_target":5,"revision":0,"reason":"Criterios aprobados para coordinación","geocoding_enabled":false,"accept_geocoding_policy":false}
```

Crear un seguimiento:

```json
{"position_id":1,"profile_id":1}
```

Consultar primero los campos y la revisión reales del candidato/seguimiento. Acción sobre contacto:

```json
{"action":"start","revision":0,"note":""}
```

`start` devuelve `whatsapp_url` y registra solo intento. Acciones `sent`, `accepted`, `declined`, `no_response`, `cancelled`, `confirm`, `reopen` exigen referencia manual cuando corresponde, de al menos ocho caracteres. `confirm` exige aceptación registrada, convocatoria futura, requisitos y disponibilidad vigentes; puede devolver participación en espera por falta de cupos. `reopen` renueva el plazo conservando historial. No existe un endpoint de envío automático.

Solicitud y revisión:

```json
{"kind":"access","note":"Solicito revisar los datos asociados a mi cuenta."}
```

```json
{"status":"in_review","revision":0,"response":"Solicitud recibida para revisión administrativa."}
```

Tipos `access`, `rectification`, `deletion`, `other`; revisión a `in_review`, `answered`, `rejected`. No se admite indicar otro propietario al crear. Las listas devuelven `results`, `page`, `total`; revisar la respuesta concreta para metadatos adicionales. Una revisión desactualizada produce 409; validación 400, acceso no autorizado 403, recurso inexistente 404. No registrar cuerpos con datos personales en los logs del proxy.


Actualización 15-11-2026: al desactivar “Mostrar solo candidatos elegibles”, el mapa también representa los perfiles no elegibles de la página que tengan referencia registrada, en ámbar. No se les asigna puntuación ni se habilita su invitación. Sin coordenadas no se inventa un marcador; las actividades remotas siguen sin mostrar ubicaciones personales. El endpoint mantiene el permiso de coordinación en Django.


## Navegación y seguridad de cuenta

`GET /api/security/` consulta exclusivamente el estado de la cuenta propia. `POST /api/security/action/` gestiona contraseña, solicitud/confirmación de correo, TOTP y recuperación con credenciales actuales y CSRF. No acepta un identificador de otro usuario; los detalles y acciones están en [Navegación y seguridad](NAVEGACION_SEGURIDAD.md). Las rutas React se sirven con fallback a `index.html`, manteniendo `/api`, `/accounts`, `/admin` y `/static` para Django/estáticos.
