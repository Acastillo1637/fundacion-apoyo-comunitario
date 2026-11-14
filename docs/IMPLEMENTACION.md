# Estado de implementación PRO-12

Fundación Apoyo Comunitario · Conectamos personas, multiplicamos la ayuda.

React/Vite y Django/DRF conservan la arquitectura existente; PostgreSQL en Supabase es la base definitiva. SQLite sirve para pruebas aisladas, no para producción. No se sustituyó el proyecto ni se eliminaron sus datos.

## Funcionalidades integradas

- Cuentas verificadas, registro voluntario/solicitante adulto declarado, recuperación mediante allauth, sesiones con CSRF y acceso por roles. MFA se exige cuando está enrolado; Django Admin mantiene su flujo protegido.
- Espacios de voluntariado, solicitante, secretaría y administración; gestión web de usuarios, catálogos y restricciones, con historial.
- Perfiles, habilidades, profesiones, disponibilidad y excepciones, documentos privados versionados, revisión y vencimiento.
- Solicitudes verificadas, eventos, funciones, cupos, publicación, cancelación, participantes, asistencia, lista de espera, respaldos, notificaciones y auditoría.
- Recomendación determinista global con requisitos obligatorios, habilidades deseables, experiencia con asistencia y distancia aproximada. Pesos editables por administración, revisiones y motivos.
- Ubicaciones de referencia redondeadas, ubicación privada de eventos, actividades remotas, Haversine y mapa interactivo sincronizado. Fallos del proveedor no impiden usar coordenadas y listados.
- WhatsApp consentido mediante enlaces oficiales, intentos separados del envío manual, estados e historial, renovación de invitaciones y confirmación con control transaccional de cupos/requisitos.
- Privacidad: descarga de datos propios y solicitudes con notificaciones para todos los administradores generales activos. La respuesta administrativa no borra datos automáticamente.
- Logo oficial aportado, sin alteración, en React y autenticación Django; eslogan oficial y diseño adaptable.
- Migraciones aditivas aplicadas en Supabase con respaldo previo; herramientas de respaldo/restauración, salud, ejemplos de despliegue y CI ampliado.

## Evidencia y documentación

[Auditoría inicial y cierre](AUDITORIA_PRO12.md), [algoritmo y proveedores](MATCHING_MAPAS_WHATSAPP.md), [API](API_PRO12.md), [despliegue/recuperación](DESPLIEGUE_PRO12.md) y [validación/seguridad](VALIDACION_SEGURIDAD_PRO12.md).

281 pruebas backend satisfactorias sobre PostgreSQL local, 31 frontend y compilación correcta. El flujo integral automatizado es de API; la revisión de navegador cubre escenarios críticos, no todas las combinaciones. Cero vulnerabilidades conocidas en las auditorías de dependencias de esta fecha no implica ausencia de vulnerabilidades.

## Límites reales

No se publicó en hosting ni se verificó correo SMTP real, antivirus de producción o certificados del hosting. WhatsApp no envía automáticamente ni confirma entregas. No hay rutas ni tiempos de traslado; Nominatim está desactivado hasta aceptación informada y sus respuestas se probaron con simulación. Faltan plazo institucional de conservación, canal para personas sin cuenta, política MFA de producción, monitoreo y respaldo externo programado. Los archivos privados no se replican por compartir la base.

No se afirma cumplimiento normativo, invulnerabilidad ni certificación de accesibilidad. No introducir datos personales reales antes de resolver los pendientes de publicación.
