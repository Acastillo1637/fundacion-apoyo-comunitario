# Datos de demostración comunitaria

## Escenario adicional de matching y mapas

El lote `matching-map-demo-v1` crea **DEMO — Preparación de kits comunitarios y encuentro vecinal**, con dos cupos y tres candidatos ficticios: Camila Méndez, Diego Araya y Valentina Ríos. Fecha del lote creado el 14-11-2026: **21-11-2026, 10:00–13:00, Santiago**. Incluye una habilidad obligatoria, habilidades deseables con distinta coincidencia, disponibilidad completa, referencias aproximadas y un tipo documental exclusivo DEMO con archivos PDF aprobados sintéticamente y vigentes. No acredita formación ni revisión humana real. Las participaciones quedan vacías para probar invitaciones desde cero.

Los accesos aleatorios están en `backups/matching-map-demo-v1/access.json`, fuera de Git. Los PDF permanecen en el almacenamiento privado del backend que hizo la carga; compartir Supabase no copia esos archivos a otro equipo. Para demostrar descargas desde otro backend, trasladarlos por un canal privado autorizado conservando sus claves de almacenamiento.

El generador no incorpora teléfonos personales ni autoriza WhatsApp automáticamente. El titular del proyecto puede configurar un destinatario autorizado en las preferencias del voluntario ficticio. No se realiza ningún envío. La configuración particular posterior de un número no se almacena en el código ni se publica en GitHub.

```powershell
./scripts/manage-shared.ps1 seed_matching_demo
# Solo en desarrollo, para crear el lote una vez:
./scripts/manage-shared.ps1 seed_matching_demo --apply
```

El comando no duplica, reinicia ni sobrescribe un lote ya creado. La prueba aislada comprueba elegibilidad, documentos legibles, ausencia de consentimientos inventados y repetición segura. Los candidatos del lote también se verificaron mediante el ranking real sobre la base compartida. No se enviaron invitaciones para dejar el escenario disponible al usuario.

## Lote comunitario original

Se cargó el lote `community-demo-v1` en la base compartida de desarrollo, por solicitud del responsable del proyecto. Las personas, organizaciones, solicitudes y actividades son ficticias. Los nombres y comunas permiten presentar recorridos verosímiles, pero no representan usuarios, alianzas, verificaciones ni acciones reales.

## Contenido

- 18 voluntarios con nombres completos, comunas, profesiones, habilidades y disponibilidades variadas.
- 3 solicitantes: dos entidades comunitarias y una empresa ficticia.
- 1 cuenta de Secretaría para recorrer la coordinación. No se creó un administrador general adicional.
- 6 eventos: 4 abiertos, 1 borrador y 1 finalizado.
- 8 solicitudes: 6 aprobadas vinculadas a eventos, 1 pendiente y 1 en revisión.
- 31 participaciones: titulares, respaldos aceptados, invitaciones, postulaciones, lista de espera y una cancelación que libera un cupo.
- El evento finalizado tiene asistencia ficticia para probar el historial y las horas registradas.

Las convocatorias incluyen recuperación de espacios verdes, lectura y juegos familiares, acompañamiento de personas mayores, preparación de kits, apoyo escolar y una jornada vecinal. Las ubicaciones son referenciales; no se publicaron domicilios personales ni se inventaron prestaciones clínicas.

## Acceso

Las cuentas usan correos del dominio reservado `demo.example.org`. Sus contraseñas son aleatorias y diferentes. Las credenciales se guardaron en `backups/demo-community-*/access.json`, exclusivamente en el equipo que ejecutó la carga. Ese directorio está excluido de Git y no se publica. Para probar con Almendra, el responsable puede compartir los accesos ficticios por un canal privado.

La verificación de correo y las declaraciones de los perfiles son datos sintéticos de pruebas, no evidencias de verificaciones o consentimientos reales. No se enviaron correos ni WhatsApp, no se configuraron teléfonos de personas reales y no se crearon certificados o acreditaciones documentales falsas.

## Reproducción e integridad

```powershell
# Solo muestra el plan si el lote no existe.
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 seed_community_demo

# Crea el lote una vez. Si ya existe, no duplica ni sobrescribe.
powershell -ExecutionPolicy Bypass -File scripts/manage-shared.ps1 seed_community_demo --apply
```

El comando exige DEBUG activo, comprueba colisiones de correos, usa una transacción y registra la procedencia del lote. En PostgreSQL serializa ejecuciones simultáneas con un bloqueo asesor. No modifica usuarios existentes ni reemplaza sus contraseñas. Los catálogos existentes se reutilizan y se agregan las categorías generales necesarias.

La prueba aislada verifica repetición segura, conservación de cuentas, coherencia de requisitos/disponibilidad y límites de cupos. Después de cargar Supabase se comprobaron las cantidades y que no hubiera funciones con más titulares confirmados que su capacidad. Antes de utilizar la plataforma con datos operativos, retirar o separar este conjunto de demostración de forma controlada.

## Retiro de elementos sintéticos de la entrega

`./scripts/manage-shared.ps1 archive_demo_catalogs` muestra una vista previa. Con `--apply` desactiva las habilidades y tipos documentales con prefijo exacto DEMO — y cancela la convocatoria sintética identificada por UUID y por su lote de creación. La operación es repetible y auditable. Conserva todas las cuentas, archivos y relaciones históricas: no convierte certificados ficticios en acreditaciones reales. Las opciones DEMO archivadas no se ofrecen en el formulario de habilidades. El historial administrativo puede conservar sus nombres para trazabilidad. Los generadores y sus pruebas siguen disponibles solo para entornos de desarrollo.
