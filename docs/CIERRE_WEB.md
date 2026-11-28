> Registro histórico del cierre del commit `4499c75`. Las cifras corresponden a esa ejecución; consultar [validación vigente](VALIDACION_SEGURIDAD_PRO12.md) para el estado posterior.

# Cierre de revisión web — 21-11-2026

## Diagnóstico y cambios realizados

La auditoría encontró los módulos principales integrados: cuentas por rol, solicitudes, actividades, documentos, requisitos, participación, matching, mapa, ubicación, WhatsApp manual y trazabilidad. No se reconstruyó la aplicación.

Se cerraron estas carencias de uso:

- Solicitudes y convocatorias: búsqueda en todo el conjunto autorizado antes de paginar, estado y fecha; filtros desde operaciones, matching y participantes. Búsqueda de actividades por título/comuna y solicitudes por contacto/entidad/comuna. No se consulta mientras se escribe: el usuario pulsa Buscar. Al cambiar los filtros vuelve a la primera página.
- Notificaciones: acceso a todo el historial por páginas de 30, filtro de avisos sin leer, lectura individual y lectura global. Antes solo se podían consultar los últimos 30. El contador de pendientes sigue siendo global; no se confunde con los avisos de la página. El endpoint obtiene los totales mediante funciones de ventana, manteniendo una sola consulta en la primera página. Una página vacía fuera de rango consulta los totales para permitir volver a una página válida.
- Permisos de avisos: el ID que se marca como leído debe pertenecer a la sesión. Un ID ajeno devuelve 404 y no cambia su lectura. No se aceptan propietario ni campos adicionales.
- Carga: se descartan respuestas anteriores a otra búsqueda o página, se presentan estados de actualización y resultados vacíos; un error permite reintentar. Los filtros forman parte de la clave de lectura temporal existente. El matching limpia la página anterior mientras actualiza candidatos.
- Confirmaciones al rechazar solicitudes, cancelar/finalizar actividades y retirar/cancelar participaciones. La edición pública refresca también la lista.
- WhatsApp: aviso de rondas vencidas y desactivación de acciones que el backend rechazaría hasta iniciar otra ronda. Estado de preparación para evitar dobles pulsaciones del contacto general. No se enviaron mensajes.
- Adaptación móvil de los filtros, con controles de ancho completo en pantallas estrechas.

No se cambiaron requisitos de elegibilidad, permisos, cupos, contraseñas, roles ni datos de Supabase. No hay migraciones nuevas.

## Verificaciones

- 315 pruebas backend satisfactorias sobre PostgreSQL local aislado, incluidas concurrencia, aislamiento entre usuarios, filtros y archivo de notificaciones. Cero omisiones en esa ejecución.
- 55 pruebas frontend satisfactorias: navegación, autenticación, formularios, datos API, filtros, vencimiento de contacto, páginas de avisos, lectura individual y recuperación de errores.
- Compilación de producción Vite correcta; comprobación de Django y detección de migraciones sin problemas.
- Auditorías npm y pip-audit del lock de desarrollo sin vulnerabilidades conocidas al consultar el 21-11-2026. CI comprueba además el lock de producción en Linux. Esto no equivale a un pentest ni garantiza ausencia de vulnerabilidades.
- Navegador sobre servidores 8001/5174 y PostgreSQL aislados: login de prueba existente, cambio de espacio, búsqueda sin resultados y con resultados, filtros de eventos, matching con distancias y mapa, segunda página de 35 avisos ficticios y lectura individual con actualización del contador 35→34.
- En 390×844, navegación móvil y filtros sin desbordamiento horizontal: ancho del documento 375 px con viewport de 390 px. Se restableció el viewport al terminar. No se modificaron los servidores habituales ni se probaron con cuentas reales.

Evidencias de datos exclusivamente ficticios: [filtros escritorio](evidencias/cierre-filtros-escritorio.jpg), [filtros móvil](evidencias/cierre-filtros-movil.jpg) y [notificaciones antiguas](evidencias/cierre-notificaciones.jpg).

## Para probar esta versión

Reinicia Django y Vite desde los scripts habituales. No necesitas otra base ni importar datos. La base definitiva sigue siendo Supabase PostgreSQL.

1. Secretaría: Solicitudes y eventos → Buscar, Estado y Fecha. Prueba Limpiar filtros y vuelve a abrir una ficha.
2. Matching o Participantes: filtra la convocatoria antes de abrirla; después se mantienen los flujos de candidatos, mapa, invitaciones, participación y asistencia.
3. Cualquier rol: Notificaciones → Mostrar solo sin leer, Marcar leída y Siguiente/Anterior si hay más de 30 avisos propios.
4. Una ronda WhatsApp vencida exige Nueva ronda de contacto con justificación. Abrir WhatsApp sigue siendo solo un intento, nunca envío o entrega automáticos.

## Límites antes de publicación

La aplicación local y sus flujos comprobados están integrados. La publicación en internet todavía requiere el hosting real con dominio/HTTPS, SMTP para entrega de correos, antivirus y almacenamiento privado de producción, copias externas y política institucional de conservación. Compartir PostgreSQL no comparte por sí solo los archivos privados entre equipos.

Las modificaciones logísticas de una convocatoria publicada (horarios, funciones, cupos y requisitos con participantes vinculados) no tienen un flujo general de reconfirmación; se conservan las restricciones actuales para proteger asignaciones. Sí existen edición de borradores, cambios públicos auditados y actualización autorizada de ubicación. No se implementó borrado automático de expedientes ni se eligió un plazo institucional sin aprobación.

Estos requisitos externos y decisiones pendientes se conservan explícitos en [despliegue](DESPLIEGUE_PRO12.md) y [seguridad](VALIDACION_SEGURIDAD_PRO12.md). No se declara despliegue realizado, entrega de correo verificada, cumplimiento legal o ausencia total de errores.

## Cierre del acceso local — 28-11-2026

Se completó la corrección que había quedado sin publicar: el origen local de Vite en el puerto 5174 ya pasa la validación CSRF, igual que 5173, cuando DEBUG está activado. La lista de producción permanece explícita y no incorpora estos orígenes. Los archivos de ejemplo aclaran la separación entre desarrollo compartido y hosting. No se modifican usuarios, contraseñas, consentimientos ni datos de Supabase; no hay migraciones nuevas. El detalle y las pruebas de rechazo se documentan en [navegación y seguridad](NAVEGACION_SEGURIDAD.md).

Validación de este cierre: 44 pruebas de autenticación, seguridad y CSRF aprobadas en base local aislada; 75 pruebas frontend aprobadas; compilación Vite correcta; 21 documentos Markdown sin enlaces locales rotos. La auditoría integral previa de 356 pruebas PostgreSQL se conserva como evidencia anterior y no se presenta como una nueva ejecución de esta corrección.
