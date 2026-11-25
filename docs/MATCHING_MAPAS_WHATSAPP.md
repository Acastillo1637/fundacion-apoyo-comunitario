# Recomendaciones, mapas y contacto manual

## Recorrido en la web

1. Voluntariado: completa habilidades, disponibilidad, documentos, **Ubicación de referencia** y **Preferencias de comunicación**. En ubicación, ingresa calle, número y comuna, autoriza la consulta a Geoapify y pulsa **Guardar y calcular ubicación**. Solo se conserva una referencia redondeada a dos decimales. El buscador público de la opción manual sigue sin admitir domicilios particulares.
2. Coordinación: aprueba documentos, revisa una solicitud y crea la convocatoria con funciones, cupos, requisitos y habilidades deseables. Confirma su ubicación o indica que es remota. Publica la convocatoria.
3. **Matching y convocatoria → Encontrar candidatos** muestra primero los elegibles, sus puntuaciones y distancias. Seleccionar una tarjeta o un marcador sincroniza el mapa. El mapa muestra la página actual, no todos los candidatos a la vez.
4. **Contactar por WhatsApp** registra un intento y abre un enlace oficial. Si el navegador bloquea la ventana, utiliza el enlace que queda visible. La persona operadora revisa y envía el mensaje en WhatsApp.
5. En **Seguimiento de contactos e invitaciones**, registra manualmente envío y respuesta con una referencia breve, sin copiar conversaciones. Una aceptación registrada todavía no reserva un cupo: pulsa **Confirmar participación**. Si se agotaron los cupos, se utiliza la lista de espera.
6. Si una persona cancela, vuelve a ejecutar el matching. La elegibilidad y los cupos se comprueban otra vez al confirmar a su reemplazo. Los respaldos mantienen el circuito de invitación y aceptación existente.

## Algoritmo determinista

La elegibilidad usa cuenta activa, pertenencia a voluntariado, restricciones vigentes, disponibilidad completa para la franja y excepciones, habilidades obligatorias, documentos aprobados y vigentes **para la fecha de la actividad**, ausencia de confirmaciones superpuestas y convocatoria abierta/futura. Las profesiones o habilidades que tienen requisitos documentales heredan esas exigencias. Incumplir una condición excluye la recomendación; coordinación puede consultar motivos operativos sin acceder a documentos desde el mapa.

Para los elegibles:

`puntos = peso_habilidades × H + peso_experiencia × E + peso_distancia × D`

| Factor | Regla |
|---|---|
| H | Habilidades deseables coincidentes / habilidades deseables exigidas. Si no se definieron, vale 1 para todos. Las obligatorias se validan antes. |
| E | `min(participaciones_relevantes / objetivo, 1)`. Solo actividades pasadas finalizadas, como titular y con asistencia presente registrada, relacionadas por habilidades con la función. Sin habilidades de referencia, no se presume experiencia relevante. |
| D | `max(0, 1 − km/límite_km)`. Sin ubicación comparable: 0 puntos de distancia, sin excluir al candidato. En actividades remotas: 1 para todos y no se entregan referencias personales al mapa. |

Por defecto: pesos **60/15/25**, límite **50 km**, objetivo de experiencia **5**. Administración puede modificarlos en **Criterios de recomendación**, con motivo, versión e historial. Los pesos deben sumar 100. El porcentaje expresa compatibilidad con estos criterios; no es una probabilidad ni una decisión automática.

Se ordena el conjunto completo antes de paginar de 20 en 20. Desempates: mayor puntuación, menor distancia conocida, nombre normalizado e ID. Las distancias usan Haversine, radio terrestre 6371,0088 km; son **estimaciones en línea recta entre referencias**, nunca rutas ni tiempos de viaje. Las centésimas de grado reducen precisión, pero no garantizan anonimato; su consulta exige permisos.

## Proveedores y degradación

Leaflet se carga por separado del paquete principal. El fondo usa OpenStreetMap con atribución, caché normal del navegador y sin precarga masiva. `MAP_TILE_URL` permite cambiar de proveedor. Si falla, los puntos/listado y las coordenadas manuales siguen disponibles. No existe OSRM integrado ni se inventan tiempos de traslado.

La búsqueda de lugares está **desactivada por defecto**. Habilitarla requiere que administración lea y acepte conscientemente las condiciones del proveedor. No es necesaria para registrar coordenadas o marcar el mapa. Nominatim público solo puede usarse con tráfico moderado, búsquedas explícitas del usuario, identificación, atribución, caché y máximo global de una solicitud por segundo; no admite autocompletado ni datos personales/confidenciales. La aplicación aplica bloqueo compartido de 1,1 segundos, caché siete días, límite por IP y tiempo máximo de cuatro segundos. No se realizaron búsquedas reales de Nominatim durante las pruebas: se comprobaron respuestas simuladas y concurrencia local. En producción, el responsable debe reevaluar capacidad y condiciones, o configurar un proveedor alternativo.

Fuentes consultadas el 14-11-2026: [política Nominatim](https://operations.osmfoundation.org/policies/nominatim/) y [política de teselas](https://operations.osmfoundation.org/policies/tiles/). Son servicios comunitarios sin garantía de disponibilidad. El proveedor de teselas recibe IP y área visualizada; no se le envían nombres ni documentos.

## WhatsApp y trazabilidad

### Flujo manual de envío — actualizado 25-11-2026

1. **Contactar por WhatsApp** recupera o crea un único seguimiento por evento/voluntario y solicita abrir el enlace. Registra `start`, actor y fecha/hora del servidor. El estado de envío permanece pendiente; no se registra `sent` por abrir una ventana.
2. **Volver a abrir WhatsApp** reutiliza ese seguimiento y registra otro intento de apertura, sin crear otra invitación ni marcar envío. Si el navegador bloquea la ventana, el botón sigue disponible para reintentar. Se conservan consentimiento, permisos y vencimiento; una ronda vencida debe renovarse explícitamente.
3. **Confirmar envío** es una acción separada y explícita de secretaría, disponible en la tarjeta y en el seguimiento. Registra `sent` con responsable y fecha/hora; la referencia es opcional, y si se escribe debe tener al menos ocho caracteres. No registra aceptación, no crea participación y no asigna cupos.
4. **Registrar aceptación** sigue siendo una acción diferente. **Confirmar participación** vuelve a comprobar disponibilidad, requisitos y cupos. Registrar posteriormente un envío no sobrescribe una aceptación ya registrada.

El estado visible se reconstruye de `ContactChange` al consultar la API; no depende del estado temporal de React. Tanto el matching como el seguimiento muestran la última apertura y confirmación de la ronda actual tras recargar. Reabrir después de un envío confirmado conserva su confirmación; repetirla se rechaza sin otra transición. La lectura por lotes conserva la confirmación aunque haya más de veinte aperturas posteriores.

Una ventana abierta solo demuestra que se solicitó abrir un enlace: no acredita entrega, lectura ni envío real. La confirmación es una declaración del personal autorizado, no una verificación de WhatsApp. El historial anterior no se reescribe; una nueva ronda mantiene los registros previos y reinicia únicamente sus indicadores actuales. No se añaden servicios, dependencias de pago ni API de WhatsApp.

La comprobación de interfaz usó datos ficticios en PostgreSQL local: estado pendiente antes de confirmar, botones diferenciados y lectura de la confirmación persistida tras abrir nuevamente la pantalla. El diálogo nativo produjo un bloqueo de la herramienta del navegador; la recarga se verificó en una pestaña nueva. Los tests de componentes ejercitan la confirmación/cancelación del diálogo; los de API comprueban auditoría, responsables distintos, concurrencia, no duplicación y ausencia de asignación de cupos. No se envió ningún mensaje externo. [Evidencia local ficticia](evidencias/whatsapp-envio-manual.jpg).

Estados: pendiente de contacto, contacto iniciado, envío confirmado manualmente, aceptada, rechazada, sin respuesta y cancelada. Historial con actor, fecha, versión y referencia. Vencimiento: 48 horas o inicio de la actividad. Una nueva ronda exige revalidación y conserva el historial anterior.

`contacts.py` separa preparación del enlace de las transiciones del seguimiento y de la asignación de cupos. `whatsapp_link` normaliza teléfonos y personaliza nombre, actividad, fecha/hora de Santiago y comuna; no incluye dirección privada. Exige consentimiento vigente y número utilizable. La preparación no equivale a envío ni entrega. Retirar el consentimiento impide generar nuevos enlaces.

La solución actual no cobra por una API y no tiene automatización de WhatsApp Web. La eventual Business Platform requerirá un adaptador oficial, credenciales, consentimiento adecuado, webhooks y evaluación de costos; **no está implementada**. Hosting, almacenamiento, correo y límites comerciales de otros proveedores pueden tener costos propios.

## Privacidad

**Solicitudes de privacidad** permite registrar solicitudes y descargar los datos propios. Cada nueva solicitud notifica en la web a **todos los administradores generales activos**. La bandeja administrativa valida permisos en Django; voluntarios y solicitantes solo ven sus solicitudes. Las respuestas quedan trazadas y visibles al titular. Registrar una respuesta no ejecuta eliminación de datos.

El plazo de conservación aún requiere aprobación institucional. No se creó un plazo ficticio ni una tarea de borrado automático. `DATA_RETENTION_NOTICE` debe contener el texto aprobado antes de publicar. La bandeja autenticada no resuelve por sí sola las solicitudes de personas sin cuenta: falta acordar ese canal institucional.


Actualización 15-11-2026: al desactivar “Mostrar solo candidatos elegibles”, el mapa también representa los perfiles no elegibles de la página que tengan referencia registrada, en ámbar. No se les asigna puntuación ni se habilita su invitación. Sin coordenadas no se inventa un marcador; las actividades remotas siguen sin mostrar ubicaciones personales. El endpoint mantiene el permiso de coordinación en Django.
