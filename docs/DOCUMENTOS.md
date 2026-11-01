# Gestión documental privada

## Flujo y modelo

`VolunteerDocument` representa una versión inmutable del archivo, con propietario, tipo, número de versión, clave privada aleatoria, tamaño, MIME, SHA-256, resultado antimalware y fecha de carga. No se persiste el nombre original, evitando almacenar datos personales incrustados en nombres.

El estado de revisión es pendiente, validado o rechazado. La revisión guarda actor, fecha, observación y vencimiento. `effective_status` devuelve vencido si un archivo validado terminó su fecha de validez en America/Santiago; no depende de un job periódico.

Las versiones se numeran por perfil y tipo. La carga bloquea el perfil en una transacción, controla cuota, guarda el archivo y registra el alta con auditoría. Una excepción posterior elimina el archivo recién creado. Una caída abrupta del proceso puede dejar un objeto huérfano: antes de producción se requiere reconciliación y respaldo consistente de archivos/metadatos.

La revisión también bloquea el perfil y la versión, verifica permiso y MFA, y prohíbe revisar documentos propios. Solo se revisa la última versión y una decisión no se sobrescribe. Una nueva carga comienza pendiente; la validación histórica no se aplica a la nueva versión.

## Acceso

| Operación | Control |
| --- | --- |
| Listar, cargar y ver requisitos propios | Sesión y perfil propio |
| Descargar archivo propio | Propietario autenticado |
| Consultar cola, descargar ajenos y revisar | Permiso `documents.review_volunteerdocument` + MFA en la sesión |
| Modificar revisiones o archivos desde Django Admin | Deshabilitado; el panel ofrece consulta autorizada |

Los grupos Secretaría y Administrador general reciben el permiso documental mediante `setup_roles`. El acceso depende del permiso específico, no solo del nombre del rol. La cola no incluye documentos propios ni versiones superadas y pagina de 20 en 20. Incluye solo nombre del voluntario, sin domicilios ni datos de contacto.

## Endpoints

- GET/POST `/api/documents/`: historial, tipos y requisitos / carga multipart con campos `document_type` y `file`.
- GET `/api/documents/<uuid>/download/`: respuesta attachment, sin rutas del disco, `no-store` y `nosniff`.
- GET `/api/documents/review-queue/?page=1`: pendientes autorizados.
- POST `/api/documents/<uuid>/review/`: decisión, observación y fecha opcional. Campos extra rechazados.

Todas las mutaciones requieren CSRF. Los UUID no sustituyen autorización: una descarga ajena no autorizada obtiene 404. No se instala una ruta pública MEDIA_URL.

## Validación técnica

Se admiten PDF, JPEG y PNG. Límite de 10 MB por carga y un solo archivo por petición. Un upload handler interrumpe cargas excesivas antes de almacenarlas completas en temporales. La API también comprueba tamaño, MIME declarado y extensión, que no se consideran suficientes por sí solos.

Pillow verifica estructura, formato, carga y un máximo de 16 millones de píxeles. pypdf verifica cabecera/estructura, máximo de 50 páginas, ausencia de cifrado y de acciones o adjuntos prohibidos. Conservamos el original: reescribir certificados podría invalidar sus firmas. No verificamos la autenticidad criptográfica de los certificados.

El parser se ejecuta en un proceso Python aislado del intérprete web, sin shell ni rutas del usuario, con timeout de 10 segundos. En Linux impone límites de CPU y 1 GB de memoria. En Windows solo hay timeout y límites del parser. Esto no es un sandbox completo de sistema operativo; un parser comprometido seguiría teniendo los permisos del proceso. El despliegue debe añadir contenedor sin privilegios, límites y aislamiento de red.

Cuota inicial: 50 MB y 100 versiones por perfil. Las cargas se limitan a 20 intentos por IP en una ventana de 15 minutos. Nginx deberá limitar además el cuerpo HTTP y la concurrencia; la defensa de aplicación no reemplaza el límite en el proxy.

## Antimalware

La integración usa el protocolo INSTREAM de ClamAV por socket interno, con timeout. Solo una respuesta `stream: OK` permite marcar `clean`; detección, errores y resultados desconocidos no guardan el archivo.

Con DEBUG desactivado, la carga requiere scanner y las descargas/revisiones bloquean archivos locales no analizados. No se ha instalado un daemon ClamAV ni se ha configurado su actualización de firmas. Las pruebas del protocolo usan dobles controlados: no prueban un antivirus real desplegado.

El parser y el scanner se ejecutan durante la petición en esta etapa. Es una carga acotada pero con latencia: antes de uso real deben medirse capacidad y timeouts. Si la concurrencia lo exige, se trasladará a procesamiento asíncrono con cuarentena. No se incorpora Redis/Celery todavía.

## Almacenamiento y operación

Se usa FileSystemStorage mediante un módulo independiente. La raíz privada es configurable y usa permisos 0700 para directorios y 0600 para archivos en sistemas POSIX. Windows requiere sus ACL equivalentes en el despliegue que corresponda. La privacidad principal depende de autorización y ausencia de ruta pública, no del nombre aleatorio.

Git ignora los archivos. No hay eliminación por usuario ni borrado desde el panel: queda pendiente el flujo de retención/eliminación autorizada, que debe coordinar base y archivos antes de producción. No se debe tratar PROTECT como una política de retención definitiva.

Eventos de auditoría: carga, descarga, validación y rechazo, con actor/recurso/fecha. No se registran contenido ni nombres originales en el log de aplicación. El hash permite futuras comprobaciones de integridad; no cifra el archivo ni demuestra su autenticidad.

## Pruebas y límites

Se prueban formatos falsos, PDF activo/cifrado, límites, carga múltiple, CSRF, perfiles ajenos, MFA, autorrevisión, versiones, expiración, cuota, requisitos y fallos/detecciones del scanner. Las pruebas con archivos necesitan un directorio temporal escribible; el sandbox de Windows impidió esa escritura y se ejecutaron fuera de él.

Falta revisión visual/móvil completa. No se ha automatizado la acreditación de habilidades/profesiones, la consulta de requisitos por evento ni notificaciones internas; esos flujos se añadirán en sus módulos.
