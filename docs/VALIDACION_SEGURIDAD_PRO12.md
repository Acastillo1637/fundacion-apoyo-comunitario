# Validación y límites de seguridad

Esta guía resume el estado comprobado. Los informes de auditoría y cierre conservan sus cifras históricas; no son instrucciones de configuración.

## Comprobaciones reproducibles

| Comprobación | Último resultado registrado |
|---|---|
| Backend, PostgreSQL 17 local aislado | 346 pruebas satisfactorias en PostgreSQL aislado; incluye concurrencia, permisos, matching y nuevas reglas de formación y resguardo. Comprobaciones adicionales del archivo DEMO y la validación de comunas pasaron por separado. |
| Frontend Node | 65 pruebas satisfactorias: comunas, registro con celular chileno obligatorio, autorización de WhatsApp, descripción de oficio y confirmación manual de envío. |
| Compilación Vite | Correcta; mapas cargados por separado. |
| Django y modelos | Check sin problemas; sin migraciones faltantes. |
| Documentación y configuración | 21 Markdown sin enlaces locales rotos; plantillas comprobadas contra los nombres admitidos por sus lectores. |
| Dependencias | Auditorías sin vulnerabilidades conocidas en la entrega anterior; no equivalen a ausencia de fallos. CI vuelve a consultarlas en cada ejecución. |
| Nginx | Plantilla comprobada en Linux, con certificados ficticios, logs y puertos temporales. No instalada en un hosting real. |
| Paquete de instalación | 344 archivos y hashes verificados en el paquete del commit `f7aa5c9`; secretos configurados ausentes. Un paquete nuevo lleva su propio manifiesto. |
| Recuperación | Prueba histórica: 49 tablas y un archivo ficticio idénticos tras restaurar en destino vacío; se rechazó un destino poblado. |

La [validación de la preparación para hosting](https://github.com/Acastillo1637/fundacion-apoyo-comunitario/actions/runs/44869055115) aprobó backend, frontend y despliegue. La evidencia de navegador se encuentra en el [cierre web](CIERRE_WEB.md) y [seguridad de cuenta](NAVEGACION_SEGURIDAD.md).

Para repetir:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-backend.ps1
npm --prefix frontend test
npm --prefix frontend run build
.venv\Scripts\python.exe scripts/check-docs.py
```

El script backend usa SQLite: omite pruebas que requieren PostgreSQL. La suite completa debe ejecutarse con las variables de una base PostgreSQL **local o CI desechable**, nunca con `.env.shared`. CI instala los locks, ejecuta pruebas y auditorías, comprueba Gunicorn y Nginx y valida enlaces documentales. No se publican credenciales ni resultados ficticios.

## Cobertura y controles

- Registro/login sin confirmación obligatoria de correo, contraseñas validadas, límites de intentos, CSRF y sesiones revocables. Recuperación al buzón principal mediante enlace firmado y caducable; ver [riesgos aceptados de no verificar al registrar](REGISTRO_SIN_VERIFICACION.md).
- MFA exigido en el portal cuando está enrolado y comprobación actual de contraseña/factor en operaciones sensibles. Django Admin mantiene sus controles adicionales. No se impone enrolamiento a todo el personal desde React.
- Permisos por rol y objeto en backend; pruebas contra propietarios/IDs manipulados, autorrevisión y cambios indebidos de privilegios. Ocultar botones no se considera control suficiente.
- Confirmaciones, cupos y cambios con transacciones, bloqueos, revisiones y restricciones; pruebas concurrentes reales sobre PostgreSQL. El ranking no reserva cupos.
- Matching: documentos aprobados vigentes para la fecha, disponibilidad completa, excepciones y cruces; orden global previo a paginar, pesos administrables y distancias Haversine. No hay IA generativa, rutas ni tiempos inventados.
- Archivos: límites de tipo, tamaño y cuota, parser en proceso separado, versiones privadas y descarga autorizada. Antimalware de producción requiere ClamAV real; los tests usan dobles controlados.
- Geocodificación domiciliaria con consentimiento y Geoapify en el backend, referencia redondeada y domicilio completo no persistido. Nominatim público permanece separado y no admite domicilios.
- WhatsApp: enlaces oficiales y seguimiento manual; intento, envío confirmado manualmente y respuesta son eventos distintos. Pruebas sin enviar mensajes reales.
- SQL mediante ORM o parámetros; React escapa textos y Leaflet usa `textContent`. No se realizó pentest externo completo ni certificación OWASP.
- Despliegue: DEBUG desactivado, HTTPS/cookies seguras, TLS PostgreSQL, entorno privado y chequeos de correo/directorios/antivirus. La configuración y los secretos reales siguen pendientes del hosting.

El flujo integral de `test_pro12_flow.py` es una prueba de API, no una automatización completa de navegador: registro, perfil, documentos/revisión, actividad, matching, datos de mapa, WhatsApp, aceptación manual, confirmación, cancelación y reemplazo con trazabilidad. Las pruebas de geocodificación usan datos ficticios; la conexión real de Geoapify se comprobó con un lugar público, sin domicilios privados.

## Límites reales

Faltan hosting, SMTP con entrega comprobada, certificado/dominio, antivirus de producción, almacenamiento privado compartido y operación de copias externas. Los tests y comprobaciones simuladas no acreditan esos servicios. Compartir PostgreSQL no replica los archivos.

La bandeja de privacidad notifica a todos los administradores activos. La exportación de la base de voluntarios se limita a administración con reautenticación; no existe descarga de datos en el portal del voluntario ni exportación alternativa desde el directorio de coordinación. No ejecuta borrado automático; conservación, atención a personas sin cuenta y procedimientos institucionales requieren aprobación. La modificación logística general de convocatorias con participantes aún no tiene reconfirmación; se conservan sus restricciones.

Las revisiones visuales cubren escenarios concretos de escritorio y móvil, no todos los dispositivos ni conformidad WCAG. Una auditoría de dependencias sin avisos no prueba invulnerabilidad ni cumplimiento normativo.

## Referencias normativas de la evaluación histórica

La [Ley 19.628](https://www.bcn.cl/leychile/Navegar?dt=open&idLey=19628) es referencia para el tratamiento de datos personales. La [Ley 21.719](https://www.bcn.cl/balance-legislativo/detalle/ficha_LEY_21719_2024-12-13) introduce el nuevo marco con entrada en vigor el 1 de diciembre de 2026: la publicación prevista debe evaluar esa transición. Faltan acuerdos institucionales, conservación, canales y evaluación del tratamiento; no se declara cumplimiento legal.

La Ley 21.459 se considera respecto de accesos no autorizados e integridad: los controles técnicos ayudan a prevenir abusos, pero no certifican cumplimiento. La [Ley 21.663](https://www.bcn.cl/leychile/Navegar?idNorma=1202434&idParte=10496176&idVersion=2025-01-01) vincula su aplicación a servicios esenciales y operadores calificados. Tener una web de voluntariado no basta para afirmar que esta fundación está sujeta a todas sus obligaciones; faltan antecedentes de actividades y calificación. Esta es una evaluación técnica preliminar, no un dictamen jurídico.

OWASP Top 10 y API Security Top 10 orientan la revisión de permisos, validación, archivos y exposición de datos; no se obtuvo una certificación OWASP ni se afirma invulnerabilidad.

Actualización del registro y coordinación: pasaron 109 pruebas enfocadas de backend y comprobaciones finales de normalización chilena, consentimiento, creación de cuenta e invitaciones. No requiere migraciones ni modifica las autorizaciones existentes.

## Revisión de navegación, seguridad y duplicación — 27 de noviembre de 2026

Se revisaron los controles de React, las rutas y los permisos de backend. El inventario estático final identifica 223 elementos `button`, `a` y `form`. Las nueve alertas iniciales sobre botones de Seguridad de cuenta eran falsos positivos: sus formularios se construyen mediante una función auxiliar con envío real. No se encontraron referencias indefinidas ni importaciones sin uso en los módulos de aplicación después de las correcciones.

En navegador se recorrieron 34 destinos de navegación lateral entre voluntario, secretaría, administración y solicitante, además de acceso, ayuda, seguridad y portada. Se usó PostgreSQL local aislado y cuentas sintéticas; no se modificaron Supabase, credenciales reales ni consentimientos. Se comprobó abrir/cancelar la edición publicada, navegar al matching, recargar conservando la convocatoria y cambiar de evento retirándolo de la URL. Esta cobertura no equivale a pulsar cada posible acción destructiva ni a un pentest externo.

Correcciones realizadas:

- La edición informativa publicada contenía controles de mapa con un setter inexistente. Los controles de ubicación/remoto pertenecen ahora al editor de borradores; la actualización publicada conserva su lista de campos autorizados.
- Las respuestas detalladas de eventos incluyen inicio y término con zona horaria. El frontend puede impedir finalizar antes del término y controlar correctamente la edición de ubicación; el backend sigue validando esas restricciones.
- La reinvitación de un respaldo usa su función original, aunque otra función sea la primera del evento.
- El evento seleccionado se mantiene en la ruta del matching/participantes y sobrevive a recargar. Nuestra comunidad lleva al apartado correspondiente de la portada.
- Se retiró la exportación local del directorio de coordinación. Solo se mantiene la exportación administrativa protegida del backend.
- Todas las respuestas `/api/`, incluidos errores, llevan `Cache-Control: private, no-store, no-cache, must-revalidate, max-age=0` y `Vary: Cookie`. Los recursos estáticos mantienen su caché. Esta política de navegador/proxy no elimina las optimizaciones internas de consultas y caché autorizada.
- El acceso nativo antiguo `/accounts/login/` redirige al portal y rechaza POST con 405. Se evita un segundo formulario de acceso; recuperación y controles de autenticación permanecen cubiertos por pruebas.
- Se eliminó el componente antiguo `VolunteerDirectory` sin referencias y las importaciones sobrantes. Las copias del logo para Django/Vite y las plantillas base de entrada/MFA se conservan porque son recursos de cada sistema. No se detectaron cuerpos idénticos de funciones Python de cuatro o más instrucciones.

Resultados finales: 356 pruebas de backend aprobadas sobre PostgreSQL 17 aislado y 75 pruebas frontend aprobadas, sin omisiones. Incluyen las nuevas regresiones de edición publicada/borradores, función del respaldo, selección del evento, ancla de portada, cabeceras privadas y ruta antigua de acceso. La compilación Vite terminó correctamente y los 21 documentos Markdown no tienen enlaces locales rotos.

Auditoría de dependencias: `npm audit --json` no encontró vulnerabilidades conocidas; `pip-audit` tampoco en las 18 dependencias Python del lock base ni en las 19 del conjunto de producción, incluido Gunicorn. Son resultados del catálogo consultado, no una garantía de ausencia de vulnerabilidades nuevas.

`check` y `makemigrations --check --dry-run` pasaron sin cambios de esquema. `check --deploy` se ejecutó con configuración ficticia de producción, sin conectar servicios: no produjo errores y mostró W005/W021 por HSTS de subdominios y preload. Estas opciones se mantienen desactivadas hasta definir dominio, subdominios y HTTPS del hosting; no se activan automáticamente sobre dominios desconocidos. SMTP, antivirus, TLS y almacenamiento del hosting real siguen pendientes de verificación.

Referencias técnicas: [lista de despliegue de Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) y [guía de seguridad Django de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html).
