# Rendimiento del entorno local

React corre en el equipo, pero Django consulta PostgreSQL en Supabase por internet. El 13 de noviembre de 2026 cada viaje a la base demoró aproximadamente entre 130 y 160 ms. La mayoría del tiempo de las vistas correspondía a esas consultas, incluso con el pool de conexiones funcionando.

Se midieron peticiones autenticadas pasando por el middleware de sesiones y permisos, con una cuenta ficticia. Los tiempos varían con la red; el número de consultas permite comparar el cambio sin confundirlo con esa variación.

| Vista | Consultas antes | Consultas después |
|---|---:|---:|
| Sesión | 7 | 6 |
| Dashboard de administración | 9 | 7 |
| Dashboard de operaciones | 12 | 8 |
| Usuarios | 10 | 6 |
| Tarjetas de eventos | 12 | 5 |
| Solicitudes | 6 | 5 |
| Directorio | 6 | 5 |
| Revisión documental | 6 | 5 |

Las tarjetas de eventos usan `compact=1`. Los detalles mantienen sus requisitos, posiciones e historiales, cargados al abrir el evento. Los totales del dashboard se calculan junto con sus vistas previas; las ventanas SQL cuentan también las filas que quedan fuera del límite de la vista previa.

El inicio del voluntario usa `GET /api/volunteer-overview/` para cargar únicamente sus datos, nombres de habilidades y profesiones, últimas versiones documentales, primeras cuatro participaciones y disponibilidad. Reemplaza seis peticiones que repetían comprobaciones de sesión y perfil. El editor de disponibilidad recibe el horario inicial y sigue guardándolo mediante su endpoint habitual.

Los permisos directos y de grupos se reúnen en una consulta por instancia de usuario. Se mantienen las comprobaciones de actividad, MFA, versión de sesión y autorizaciones. Se conserva el backend anterior para que las sesiones existentes sigan funcionando. No se cachean los permisos entre peticiones.

Los contadores de límites de uso usan un incremento atómico en la base compartida. Su limpieza se ejecuta como máximo una vez cada 15 minutos por proceso, en lugar de borrar registros en cada acción. Las pruebas de PostgreSQL verifican que solicitudes simultáneas no pierdan incrementos.

Las acciones de participación también reúnen sus requisitos documentales en consultas por conjunto y comprueban horario y excepciones juntos. Mantienen sus bloqueos de evento/perfil, las comprobaciones actuales dentro de la transacción y la revisión de cupos al confirmar; no reutilizan una evaluación de candidatos de otra petición.

Al volver a una sección, el frontend puede presentar una copia reciente de la respuesta mientras vuelve a consultarla. Esta copia vive únicamente en memoria, vence a los 60 segundos, tiene un máximo de 100 entradas y se copia antes de entregarla a formularios. Se descarta al comenzar y terminar cualquier escritura, al iniciar o cerrar sesión y ante un acceso denegado. Una respuesta antigua en vuelo no puede volver a poblarla después de guardar. Actualizar siempre consulta al servidor; no se sustituyen las comprobaciones del backend con datos de la copia.

La primera carga aún depende de la conexión a Supabase. El pool sigue limitado a cuatro conexiones por proceso; no se aumentó para ocultar las demoras. No hay cambios de base de datos ni es necesario migrar datos para estas optimizaciones.


## Matching y contadores — 15-11-2026

La medición de lectura sobre el lote DEMO compartido encontró 15 consultas consecutivas de matching, con aproximadamente 130–160 ms por ida y vuelta a Supabase. Se agregó una lectura específica de PostgreSQL con subconsultas correlacionadas para reunir habilidades, últimos documentos relevantes, franjas compatibles, excepciones, cruces confirmados, experiencia y participación existente. Posición/requisitos, política y perfiles requieren tres consultas en total. SQLite mantiene el camino portátil.

La misma función de elegibilidad procesa ambos caminos. Solo se agrupan lecturas de una recomendación; las escrituras, permisos, restricciones y comprobaciones transaccionales de invitación/confirmación siguen usando información actual. No se añadió caché de elegibilidad entre peticiones. Las pruebas comparan ambas respuestas con documentos heredados, versiones nuevas pendientes, indisponibilidad y cruces, y comprueban el límite de tres consultas en PostgreSQL.

Comparación sobre los mismos 22 perfiles y una conexión ya abierta, dos lecturas por variante: camino anterior 2417/2401 ms y 15 consultas; agrupado 491/492 ms y tres consultas. Es el tiempo del cálculo/lectura, no una medición de toda la página ni una garantía para otras redes o cargas; el establecimiento inicial de conexión y la autenticación agregan tiempo.

Los contadores de participantes se reúnen en un agregado y la capacidad se calcula con las funciones ya cargadas. El matching solicita `compact=1` en el listado de participantes, sin calcular otra vez la elegibilidad que ya obtiene de los candidatos. El registro completo de participantes conserva su evaluación normal. Al alternar el filtro, el mapa permanece montado durante la actualización, muestra el estado de carga y descarta respuestas anteriores que llegan fuera de orden. Los snapshots de presentación existentes mantienen su vencimiento y descarte tras escrituras; no autorizan operaciones.
