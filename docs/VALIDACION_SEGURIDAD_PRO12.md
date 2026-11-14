# Verificación y límites de seguridad — 14-11-2026

## Resultados reproducibles

| Comprobación | Resultado |
|---|---|
| Suite completa Django sobre PostgreSQL 17 local aislado | 281 pruebas satisfactorias, sin omisiones. Incluye siete pruebas PostgreSQL de concurrencia. |
| Componentes y API cliente Node | 31 pruebas satisfactorias. |
| Compilación Vite | Correcta; Leaflet separado mediante importación dinámica. |
| Django `check` y detección de migraciones | Sin problemas; no faltan migraciones de modelos. |
| Dependencias Python fijadas, incluido Gunicorn 27.0.1 | Cero vulnerabilidades conocidas según pip-audit en esta fecha. Se actualizaron DRF y Pillow tras detectar avisos en las versiones anteriores. |
| Dependencias npm | Cero vulnerabilidades conocidas en la auditoría realizada. |
| Recuperación local | 49 tablas con contenido idéntico entre origen y destino separado; archivo ficticio idéntico; destino con tablas rechazado. |
| Migraciones compartidas | Aplicadas en Supabase después de respaldo privado del esquema de aplicación. Sin eliminación de datos existentes. |

Comandos: `scripts/check-backend.ps1` prueba SQLite (las pruebas exclusivas PostgreSQL se omiten allí); para concurrencia usar una **base PostgreSQL local/CI aislada**, con usuario que pueda crear la base temporal de pruebas, nunca `.env.shared`. Ejecutar `python backend/manage.py test accounts volunteers documents activities` con las variables de esa base. `npm --prefix frontend test` y `npm --prefix frontend run build`. Auditoría: `pip-audit -r backend/requirements.production.lock --no-deps --disable-pip` en Linux y `npm --prefix frontend audit --audit-level=high`. Las versiones están fijadas; no tienen hashes de distribución en el lock.

CI ejecuta PostgreSQL 17, permisos, migraciones, pruebas, auditorías, frontend y una comprobación WSGI de Gunicorn. El smoke Linux no se ejecutó en Windows; consultar el resultado de Actions del commit entregado. No presentar auditorías de dependencias como prueba de ausencia de fallos en el código.

## Cobertura funcional

`test_pro12_flow.py` recorre por la API registro real de cuenta ficticia, verificación de email en memoria, login, habilidades, disponibilidad, ubicación, archivo privado, aprobación, actividad georreferenciada con requisitos, ranking, datos de mapa autorizados, enlace WhatsApp, estados manuales simulados explícitamente como datos ficticios, confirmación, cancelación y reemplazo con trazabilidad. Es un flujo integral de API: no es una prueba automatizada de navegador ni acredita envío real de correo o mensajes.

`test_pro12.py` cubre Haversine, coordenadas incorrectas, ranking antes de paginar, experiencia con asistencia, actividades remotas, falta de ubicación, vencimiento documental antes del evento, pesos/revisión/permisos, geocodificador desactivado/cache/fallo y contactos/consentimiento/cupos. `test_pro12_concurrency.py` comprueba dos confirmaciones simultáneas con un solo cupo y el límite global del geocodificador. `test_privacy.py` verifica notificación a todos los administradores activos, aislamiento entre titulares, revisión con permisos, versión, exportación sin secretos y controles de despliegue.

La revisión manual de navegador sobre datos sintéticos locales comprobó login con cuenta existente, rechazo de pesos que no suman 100 y guardado válido auditado, ranking/distancias, selección bidireccional mapa/listado y preparación de WhatsApp con aviso de intento. No se envió mensaje. Se revisaron 1366×900 y 390×844; en móvil el documento no excedió el ancho de pantalla. No equivale a revisar todos los dispositivos/pantallas ni a una evaluación completa WCAG.

Evidencias sintéticas: [mapa escritorio](evidencias/matching-escritorio.png), [vista móvil](evidencias/matching-movil.png). Los pesos modificados durante la prueba pertenecen solo a la base local ficticia; Supabase conserva su política propia.

## Controles y riesgo residual

| Área | Verificación / límite |
|---|---|
| Acceso por objeto / BOLA | Dueño en perfiles, ubicaciones, exportación y solicitudes; permisos de coordinación en candidatos/contactos; administradores en política y bandeja global. Pruebas con perfiles ajenos e IDs manipulados. |
| Autenticación | Contraseñas con hash Django, correo verificado, límites de intentos y sesiones con CSRF. Si una cuenta tiene MFA, se exige en el portal; administración Django conserva el control MFA. El portal no obliga a enrolar MFA a todo el personal: decisión heredada del alcance, riesgo pendiente de producción. |
| Integridad | Bloqueos de evento/usuario/perfil, transacciones, revisiones optimistas, restricciones de base y pruebas de cupos concurrentes. Ranking no reserva cupos. |
| Inyección / XSS | ORM parametrizado, validación backend estricta y React con escape; etiquetas Leaflet mediante `textContent`, sin interpolar HTML de usuarios. No se hizo un pentest externo completo. |
| Archivos | Tipos/tamaño/cuota, archivos privados, versiones y acceso autorizado. El análisis de producción requiere ClamAV real; las pruebas usan archivos ficticios y simulación del analizador. Compartir PostgreSQL no replica esos archivos. |
| Configuración | HTTPS/cookies seguras con DEBUG false, CSRF de mismo origen, secretos fuera de Git, errores de proveedores sanitizados. No hay CORS abierto. Verificar configuración real del proxy y CA PostgreSQL en hosting. |
| Servicios externos | Mapas sin nombres/documentos; búsqueda optativa de lugares públicos; caché y límite global. El proveedor ve IP/área visualizada y, si se habilita búsqueda, la consulta enviada. Evitar datos confidenciales sigue siendo una responsabilidad operativa. |
| Datos y privacidad | Bandeja distribuida a todos los administradores generales activos y exportación propia. La respuesta manual no ejecuta borrado. Plazos, atención de personas sin cuenta, procedimiento de eliminación y revisión institucional siguen pendientes. |

## Referencias normativas, sin certificación de cumplimiento

La [Ley 19.628](https://www.bcn.cl/leychile/Navegar?dt=open&idLey=19628) es referencia para el tratamiento de datos personales. La [Ley 21.719](https://www.bcn.cl/balance-legislativo/detalle/ficha_LEY_21719_2024-12-13) introduce el nuevo marco con entrada en vigor el 1 de diciembre de 2026: la publicación prevista debe evaluar esa transición. Faltan acuerdos institucionales, conservación, canales y evaluación del tratamiento; no se declara cumplimiento legal.

La Ley 21.459 se considera respecto de accesos no autorizados e integridad: los controles técnicos ayudan a prevenir abusos, pero no certifican cumplimiento. La [Ley 21.663](https://www.bcn.cl/leychile/Navegar?idNorma=1202434&idParte=10496176&idVersion=2025-01-01) vincula su aplicación a servicios esenciales y operadores calificados. Tener una web de voluntariado no basta para afirmar que esta fundación está sujeta a todas sus obligaciones; faltan antecedentes de actividades y calificación. Esta es una evaluación técnica preliminar, no un dictamen jurídico.

OWASP Top 10 y API Security Top 10 orientan la revisión de permisos, validación, archivos y exposición de datos; no se obtuvo una certificación OWASP ni se afirma invulnerabilidad.
