# Cálculo de referencia por domicilio

Implementado el 16-11-2026. La geocodificación de domicilios utiliza Geoapify desde Django; no se envían domicilios a Nominatim público.

## Configuración y uso

Agrega `GEOAPIFY_API_KEY` a `.env.shared` (o al entorno del backend en producción). Reinicia Django con `scripts/start-shared-backend.ps1` para cargarla. La clave nunca debe llevar prefijo `VITE_`, incluirse en el frontend o subirse al repositorio.

En el perfil del voluntario, abre **Mi ubicación de referencia**, ingresa calle, número y comuna y marca la autorización. Al pulsar **Guardar y calcular ubicación**, una coincidencia única de edificio, completa y con confianza mínima 0,95 se guarda automáticamente. Otros resultados requieren confirmar el sector aproximado. Se puede corregir la dirección y buscar nuevamente. No hay consultas mientras se escribe ni búsquedas masivas en segundo plano.

La dirección solo existe en el formulario y durante la solicitud del backend. No se guarda como campo del perfil, en almacenamiento del navegador, auditoría, ni en la caché. El proveedor recibe la dirección y la IP del servidor. Nuestra base guarda coordenadas redondeadas a 0,01 grados, comuna y sector. Estas coordenadas siguen siendo datos personales: el redondeo no garantiza anonimato. El matching existente utiliza la nueva referencia sin otro paso de sincronización; es necesario volver a consultar los candidatos si el panel ya estaba abierto.

Los perfiles antiguos sin ubicación deben completar este paso una vez. No se les inventan domicilios ni coordenadas a partir de sus nombres o comunas. El mapa conserva sus filtros y muestra los candidatos de la página actual con referencia disponible.

## API y protecciones

`GET /api/volunteer/location/` informa `address_geocoding_enabled` sin devolver la clave. `POST /api/volunteer/location/address/` recibe `address`, `commune`, `sector`, `revision`, `consent` y, solo para confirmar una opción, `choice`.

Respuesta automática: `{saved:true, location:{...}}`. Respuesta ambigua: `{saved:false, choices:[{label, latitude, longitude, token}]}`; esta respuesta todavía no cambia el perfil. El token firmado expira a los diez minutos, contiene solo coordenadas aproximadas y está vinculado al usuario, dirección mediante HMAC y revisión. No contiene el domicilio en claro. No se acepta un ID ajeno ni coordenadas arbitrarias en este endpoint.

Se valida sesión, rol de voluntario, CSRF, consentimiento y versión del perfil. La revisión se comprueba antes de consultar al proveedor y nuevamente dentro de una transacción con bloqueo de fila al guardar. Un error, conflicto o respuesta ambigua conserva la ubicación anterior. Los datos del proveedor se validan y redondean antes de devolverlos o almacenarlos. No se propagan sus errores, URLs ni credenciales al cliente. Auditoría registra actor, fecha y acción `profile.location.geoapify_consent_v1`, sin dirección.

La caché tiene validez de 24 horas, claves HMAC por usuario y consulta normalizada y solo resultados aproximados con descripciones de sector/ciudad. Hay un límite de diez búsquedas nuevas por usuario y veinte por IP cada quince minutos, un presupuesto compartido de veinte por intervalo de quince minutos y separación global de 1,1 segundos. Los resultados en caché no consumen consultas externas. Timeout de cinco segundos y respuesta máxima de 64 KiB; no hay reintentos automáticos. El presupuesto es propio de esta aplicación: no controla el uso de la clave en otros programas.

La alternativa manual continúa disponible y no requiere enviar el domicilio. Si fallan el proveedor, su cuota o el mapa, no se borran referencias ni se bloquean las demás funciones. Las distancias siguen siendo estimaciones en línea recta, no recorridos ni tiempos de traslado.

## Proveedor y privacidad

El plan gratuito publicado por Geoapify contempla 3.000 créditos diarios y hasta cinco solicitudes por segundo; una consulta simple consume un crédito. Los límites y condiciones deben revisarse antes del despliegue y si cambia el tráfico. No se contrató ni activó un plan de pago.

Geoapify declara que procesa las solicitudes en centros de datos europeos y conserva registros técnicos de llamadas; generalmente, los de solicitudes exitosas no superan las 24 horas. El formulario informa esta transferencia y requiere autorización explícita. La fundación debe revisar las condiciones del encargado y su aviso institucional antes de producción; esta implementación no acredita cumplimiento normativo por sí sola.

Fuentes oficiales consultadas el 16-11-2026: [API de geocodificación](https://apidocs.geoapify.com/docs/geocoding/), [precios](https://www.geoapify.com/pricing/), [privacidad](https://www.geoapify.com/privacy-policy/).

## Validación

Las pruebas automatizadas utilizan respuestas simuladas, direcciones ficticias y bases locales aisladas. Cubren guardado y redondeo, minimización de caché/auditoría, consentimiento, permisos, versiones concurrentes, errores y confirmación ambigua vinculada al usuario. Las pruebas del componente comprueban información de privacidad, consentimiento, errores y actualización de la referencia. La clave real se comprobó mediante una consulta a un lugar público (Palacio de La Moneda), sin domicilios privados ni cambios de perfiles compartidos.

Resultado local de esta entrega: 309 pruebas backend satisfactorias en PostgreSQL aislado (sin omisiones), 49 pruebas frontend satisfactorias y compilación de producción correcta. Comprobación de Django y detección de migraciones sin cambios pendientes. La comprobación específica de las siete pruebas de geocodificación también pasó en SQLite.
