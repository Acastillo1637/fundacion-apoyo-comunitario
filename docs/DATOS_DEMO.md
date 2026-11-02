# Datos de demostración comunitaria

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
