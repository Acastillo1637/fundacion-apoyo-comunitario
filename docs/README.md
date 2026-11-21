# Documentación del proyecto

Las instrucciones para iniciar están en el [README principal](../README.md). Estas son las fuentes principales por tema; los informes de una entrega concreta no reemplazan las guías vigentes.

## Guías vigentes

| Tema | Guía |
|---|---|
| Variables de entorno y plantillas | [Configuración](CONFIGURACION.md) |
| Conectar ambos equipos a Supabase | [Base compartida](BASE_COMPARTIDA.md) |
| Decisión de base definitiva y texto para el informe | [Arquitectura de datos](ARQUITECTURA_BD.md) |
| Usuarios, roles y administración web | [Usuarios](USUARIOS.md) |
| Acceso sin confirmación de correo y sus riesgos | [Registro](REGISTRO_SIN_VERIFICACION.md) |
| Rutas, menú y seguridad de cuenta | [Navegación y seguridad](NAVEGACION_SEGURIDAD.md) |
| Habilidades, profesiones y disponibilidad | [Voluntarios](VOLUNTARIOS.md) |
| Documentos, revisión y almacenamiento privado | [Documentos](DOCUMENTOS.md) |
| Solicitudes y convocatorias | [Actividades](ACTIVIDADES.md) |
| Postulaciones, cupos, espera, respaldos y asistencia | [Participación](PARTICIPACION.md) |
| Ranking, mapas y seguimiento WhatsApp | [Matching](MATCHING_MAPAS_WHATSAPP.md) |
| Cálculo de referencia por domicilio con consentimiento | [Geoapify](GEOCODIFICACION_DOMICILIOS.md) |
| Endpoints incorporados a PRO-12 | [API](API_PRO12.md) |
| Paquete, hosting, copias y recuperación | [Despliegue](DESPLIEGUE_PRO12.md) |
| Pruebas y límites de seguridad | [Validación](VALIDACION_SEGURIDAD_PRO12.md) |
| Optimizaciones y mediciones | [Rendimiento](RENDIMIENTO.md) |
| Usuarios y convocatorias ficticias | [Datos de demostración](DATOS_DEMO.md) |

## Registros históricos y evidencias

- [Auditoría inicial PRO-12](AUDITORIA_PRO12.md): diagnóstico y decisiones de esa etapa.
- [Cierre de revisión web del 21-11-2026](CIERRE_WEB.md): cambios del commit `4499c75` y capturas de pruebas locales.
- Las imágenes de `evidencias/` muestran datos ficticios. Una revisión visual puntual no acredita todos los dispositivos ni una evaluación WCAG completa.

## Criterio de limpieza

Se consolidaron las dos plantillas de producción en `.env.example`, y las guías de preparación/despliegue en `DESPLIEGUE_PRO12.md`. El estado funcional se resume en el README principal; se retiró su copia en `IMPLEMENTACION.md`.

Las copias exactas que sí requiere la arquitectura se conservan: `__init__.py` de paquetes/migraciones, bases de plantillas que allauth busca por rutas distintas y el logo servido separadamente por Vite y Django. Los locks, migraciones, documentos privados y respaldos no son duplicados eliminables.
