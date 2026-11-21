> Registro histórico de la auditoría inicial. Sus pendientes y decisiones de esa fecha no representan el estado actual; consultar [el índice vigente](README.md) y [validación](VALIDACION_SEGURIDAD_PRO12.md).

# Auditoría de PRO-12 — 14 de noviembre de 2026

## Punto de partida

El repositorio existente usa React/Vite, Django/DRF, PostgreSQL en Supabase y GitHub Actions. La revisión inicial encontró 244 pruebas de backend y 24 de frontend, con pruebas de concurrencia PostgreSQL en CI. Los modelos y endpoints implementan cuentas separadas de voluntario, solicitante y coordinación; correo verificado; MFA de cuentas que lo han activado; disponibilidad y excepciones; documentos privados versionados; solicitudes, eventos, participaciones, cupos, lista de espera y respaldos; revisiones optimistas, bloqueos y auditoría. Se conservan estos módulos.

## Brechas y orden de trabajo

1. El matching valida requisitos pero no puntúa globalmente ni admite pesos o habilidades deseables. Incorporar puntuación determinista, clasificación antes de paginar y explicaciones.
2. La proximidad solo compara comunas. Incorporar puntos de referencia aproximados, coordenadas privadas de eventos, Haversine y mapas sincronizados con el listado.
3. Existen enlaces wa.me con consentimiento, pero falta seguimiento de contacto y confirmación manual trazable. Separar el intento de abrir WhatsApp de la confirmación manual de envío/respuesta; revalidar cupos y requisitos al confirmar.
4. Incorporar el logo aportado sin alterarlo y el eslogan oficial.
5. Completar pruebas de integración, fallos de proveedores, permisos de ubicaciones, puntuaciones, confirmaciones manuales y reemplazos.
6. Preparar salud, despliegue, restauración, API, límites de proveedores y evaluación de seguridad con resultados verificables.

## Decisiones de implementación

- Cambios aditivos de esquema y migraciones reproducibles; sin eliminar registros.
- Ubicación del voluntario redondeada a centésimas de grado, con aviso de aproximación; no se solicita domicilio.
- Distancias geodésicas en línea recta, sin inventar rutas ni tiempos de traslado.
- Leaflet estable, OpenStreetMap con atribución y sin descarga masiva. Geocodificación pública optativa, activada conscientemente por administración tras leer las condiciones; sin autocompletado ni geocodificación de domicilios particulares.
- La selección sigue en manos de coordinación. La puntuación no reserva cupos ni confirma participantes.
- WhatsApp mediante enlaces oficiales y envío humano; ninguna simulación de entrega ni automatización no oficial.
- Los cambios en el repositorio no equivalen a un despliegue de producción ni a una certificación legal.

## Cierre de la implementación

Las brechas técnicas priorizadas se abordaron en los módulos existentes: matching global explicado, mapas/Haversine, contactos manuales con estados, revalidación de cupos y requisitos, identidad oficial, privacidad distribuida a administración, comprobaciones de despliegue y recuperación no destructiva. Las migraciones se aplicaron en Supabase con respaldo previo.

La validación local terminó con 281 pruebas backend sobre PostgreSQL, 31 frontend, compilación correcta y recuperación comprobada de 49 tablas y un archivo ficticio. Consulta [la evidencia y los límites de seguridad](VALIDACION_SEGURIDAD_PRO12.md). Quedan fuera de la verificación local los servicios reales del hosting, SMTP, antivirus y certificados; también las decisiones institucionales de conservación y el canal para personas sin cuenta. La revisión automática de CI del commit se informa por separado.
