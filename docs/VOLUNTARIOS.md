# Habilidades, profesiones y disponibilidad

## Alcance

Un voluntario autenticado edita únicamente sus propias declaraciones y horarios. Django obtiene el perfil desde la sesión; los endpoints no aceptan propietarios enviados por el navegador. No se han implementado documentos cargados, matching ni participaciones.

## Catálogos

`Skill`, `Profession` y `DocumentType` tienen nombre único sin distinguir mayúsculas, descripción y bandera activa. Los catálogos se administran en Django Admin con permiso por modelo y MFA. Las escrituras registran actor, acción, recurso y fecha; no se copian datos personales a la auditoría.

Se usa el panel incluido en Django para no introducir otra tecnología ni una segunda interfaz administrativa antes de completar la operación. No ofrece borrado de catálogos: se desactivan para conservar relaciones. Los cambios también quedan en el historial propio de Django Admin.

`VolunteerSkill` y `VolunteerProfession` guardan la declaración y su fecha. No tienen un booleano de acreditación editable por el voluntario. La validación futura se derivará de documentos y requisitos vigentes.

Una opción desactivada ya elegida se muestra y puede conservarse o retirarse; no se puede añadir de nuevo. Las relaciones usan PROTECT para impedir eliminar accidentalmente una opción aún declarada. La carga de requisitos documentales funciona en el catálogo; la revisión del archivo vendrá en el módulo documental.

`seed_catalogs` añade ejemplos explícitos, editables y solo en desarrollo; no se ejecuta automáticamente ni crea usuarios. Los nombres de ejemplo no están incrustados en los formularios o en el algoritmo.

## Disponibilidad

- Una franja tiene día (lunes = 0), inicio y término, en hora local de America/Santiago.
- Precisión de minutos. Inicio estrictamente anterior al término; no admite franjas que crucen medianoche en esta versión.
- Se permiten varios rangos separados o adyacentes en un día; se rechazan duplicados y superposiciones.
- Una fecha no disponible bloquea el día completo; no se almacena el motivo.
- Máximo de 42 franjas y 60 fechas por perfil en una actualización.
- La lista vacía significa que no existe disponibilidad declarada.
- Las fechas pasadas se pueden quitar; no hay una regla que impida conservarlas al guardar.
- El futuro matching deberá aplicar excepciones antes de comprobar las franjas, convertir el evento a America/Santiago y considerar cambios de hora. Esta etapa guarda y valida los datos, todavía no evalúa eventos.

No se solicitan tiempos de traslado ni se confirma asistencia al guardar disponibilidad.

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | /api/volunteer/catalogs/ | Opciones activas más inactivas ya declaradas, con requisitos |
| GET/PUT | /api/volunteer/qualifications/ | Reemplaza la selección propia de habilidades/profesiones |
| GET/PUT | /api/volunteer/availability/ | Reemplaza franjas semanales y fechas no disponibles |

Las mutaciones requieren sesión, CSRF, campos explícitos y revisión vigente. Respuestas principales: 400 datos inválidos, 403 falta de acceso/CSRF, 404 sin perfil y 409 edición obsoleta.

## Integridad y concurrencia

Cada recurso mantiene una revisión independiente en VolunteerProfile. GET entrega revisión; PUT exige la misma. En PostgreSQL, la transacción bloquea el perfil, comprueba revisión, valida y escribe todos los cambios junto con la auditoría. Una petición simultánea con revisión antigua recibe 409; no borra lo guardado antes. Un error invalida la operación completa.

Las selecciones bloquean las filas del catálogo para coordinarse con desactivaciones. Se preserva la fecha de declaración de las opciones que no cambiaron. La disponibilidad se reemplaza como conjunto; las franjas no tienen referencias externas en esta etapa.

Las restricciones de base de datos impiden duplicados y duraciones inválidas. La detección de superposiciones está en la validación del conjunto y se protege por el bloqueo de perfil para estas rutas. Las escrituras SQL directas o herramientas futuras deberán respetar el mismo servicio; SQLite no proporciona el bloqueo por fila de PostgreSQL.

## Verificación

La suite comprueba permisos, CSRF, perfiles ajenos, campos de acreditación inyectados, catálogos inactivos, requisitos, fechas, límites, rollback y revisión obsoleta. Incluye dos actualizaciones concurrentes en PostgreSQL: una debe obtener 200 y la otra 409. Esa prueba se omite en SQLite.

La comprobación visual de las pantallas nuevas quedó pendiente: la herramienta no pudo determinar de forma fiable la URL del navegador Windows y detuvo la interacción. La compilación de React no sustituye la verificación visual ni las pruebas móviles y de accesibilidad.
