# Administración de usuarios desde el portal

## Funciones y permisos

La sección React **Usuarios** permite listar, buscar por nombre/correo, filtrar, consultar detalle, invitar cuentas, modificar nombre/apellido, asignar roles, activar/desactivar y enviar recuperación. Requiere el permiso accounts.manage_accounts y MFA vinculado al usuario de la sesión. setup_roles lo concede únicamente al grupo Administrador general; el superusuario técnico también lo posee por definición de Django.

Se muestran datos básicos y estado de correo/MFA; no se devuelven hashes, contraseñas, tokens, documentos, teléfonos ni domicilios. La lista pagina de 20 en 20 y limita la búsqueda a 100 caracteres. El historial muestra los 30 cambios administrativos más recientes.

Roles asignables: Voluntario, Solicitante, Secretaría y Administrador general. Se admiten combinaciones y el titular cambia explícitamente de espacio en React. El API no acepta is_superuser, is_staff, permisos arbitrarios, contraseñas ni modificación del correo. is_staff se deriva de la pertenencia a Administrador general cuando se asignan roles; la secretaría usa las vistas operativas de React, sin requerir acceso al panel de Django.

Solicitante dispone de un perfil independiente para persona, empresa o institución. No obtiene acceso al perfil, habilidades, disponibilidad o carga documental de voluntario. Si también participa como voluntario, se le asignan ambos roles. Las cuentas invitadas completan personalmente el perfil del espacio correspondiente; no se inventan consentimientos.

## Altas por invitación

Una cuenta nueva comienza sin contraseña utilizable ni correo verificado. Se crea EmailAddress sin verificación y se solicita un enlace usando el flujo de recuperación de allauth, dirigido explícitamente al usuario creado. El titular establece su contraseña y verifica su correo. Las cuentas privilegiadas deben configurar y usar MFA antes de operar.

El administrador no puede aceptar la mayoría de edad o los consentimientos por otra persona: no se crea un VolunteerProfile durante el alta. El titular autenticado y con correo verificado completa su incorporación. El endpoint es idempotente y no sobrescribe consentimientos existentes.

La creación comprueba correo en User y EmailAddress, para no confundir alias de otras cuentas. Si falla SMTP, la cuenta queda disponible con estado de envío fallido y se permite reintentar desde el detalle. Los enlaces no se entregan al administrador en el JSON; aparecen solo en el correo o, en desarrollo, en la terminal. El adaptador usa PUBLIC_APP_URL válido para dirigir los enlaces al portal en lugar del puerto del backend.

Los envíos siguen siendo síncronos y con timeout, como el resto del correo de esta etapa. No se garantiza entrega, lectura ni procesamiento exactamente una vez. Se limita a 10 altas por IP/15 minutos y 3 solicitudes de enlace por cuenta e IP/15 minutos. La versión definitiva debe integrar outbox/tareas y monitoreo del proveedor.

## Protecciones de privilegios

- No se permite cambiar roles o estado propios desde esta sección; sí el nombre propio.
- Otras cuentas superusuarias, con permisos directos o grupos ajenos al catálogo quedan protegidas. Se conservan para operación técnica mediante procedimientos separados.
- Se rechaza la retirada del último administrador activo reconocido como superusuario o miembro de Administrador general.
- Las decisiones de acceso se serializan con una fila de AccountManagementGuard, y se revalida el actor después de adquirirla.
- Los cambios exigen una revisión vigente y motivo de 8–1000 caracteres. Una revisión obsoleta devuelve 409.
- La edición del nombre desde el perfil personal incrementa también la revisión, evitando que el panel sobrescriba silenciosamente ese cambio.
- Se validan permisos en backend y CSRF en cada mutación; esconder el menú es solo una adaptación visual.

## Sesiones

User.session_version se captura mediante la señal de login de Django, tanto para el acceso JSON como para allauth. Al cambiar roles o estado se incrementa su versión. El middleware compara la sesión con el usuario actual y cierra sesión si no coincide.

La revocación se aplica desde la siguiente petición, no interrumpe respuestas o descargas ya iniciadas. Reactivar una cuenta no revive sus sesiones anteriores. Las sesiones antiguas sin esta marca solo se aceptan para versión cero, conservando compatibilidad inicial sin aceptar sesiones revocadas.

El adaptador de cambio de contraseña actualiza únicamente ese campo para no sobrescribir una desactivación o versión de sesión cambiada mientras se procesaba un formulario. No se utiliza criptografía propia.

Los cambios hechos directamente por herramientas externas o Django Admin no pasan por el servicio de este portal: antes de producción deben unificarse esos procedimientos o restringirse y auditarse como operaciones técnicas. La garantía de revocación descrita corresponde a cambios desde esta API.

## Auditoría y privacidad

AccountChange registra actor, cuenta afectada, acción, motivo, campos cambiados y estados anterior/nuevo de roles/actividad. No duplica valores de nombres/correos ni guarda secretos. AuditEvent registra también acción, recurso y fecha. Se registran envíos fallidos y correctos; el usuario debe evitar introducir datos sensibles en el motivo.

No hay borrado definitivo ni edición administrativa del correo en esta etapa. La desactivación no sustituye el procedimiento legal de eliminación: retención, supresión de información y sus relaciones deben diseñarse antes de usar datos reales.

## Endpoints

| Método | Ruta | Control |
| --- | --- | --- |
| GET/POST | /api/management/users/ | Permiso de gestión + MFA |
| GET/PATCH | /api/management/users/<uuid>/ | Permiso, MFA, revisión, protecciones de cuenta |
| POST | /api/management/users/<uuid>/access-email/ | Permiso, MFA, motivo, destinatario acotado |
| POST | /api/profile/onboarding/ | Titular autenticado, correo verificado y consentimientos |
| GET/PUT | /api/requester/profile/ | Rol Solicitante, correo verificado, revisión y consentimientos |
| GET/POST | /api/requester/requests/ | Rol Solicitante, perfil propio y correo verificado |
| GET | /api/requester/requests/<uuid>/ | Solicitud asociada al titular; 404 para otra cuenta |

Las solicitudes autenticadas toman contacto y entidad del perfil, conservan una instantánea y tienen una clave de envío idempotente. No se admite enviar propietario, correo, estado o datos de otra entidad. Una clave que corresponde a otra cuenta o a una solicitud pública devuelve 409. Las solicitudes públicas previas no se reclaman por coincidencia de correo. El historial del solicitante solo expone estados y fechas, sin actores ni motivos internos.

## Pruebas

Cobertura: permisos, MFA, CSRF, filtros, campos prohibidos, roles, autorrestricción, cuentas técnicas, último administrador, revisión obsoleta, auditoría, invitación sin contraseña, alias, entrega fallida, establecimiento de contraseña por el destinatario, incorporación y revocación de sesiones.

Una prueba con PostgreSQL enfrenta dos administradores que intentan retirarse mutuamente: una operación obtiene 200 y la otra 403, conservando un administrador activo. Cada worker cierra su propia conexión antes de limpiar la base de pruebas.

Pendiente la verificación visual/móvil completa y las pruebas de operación con SMTP real.
