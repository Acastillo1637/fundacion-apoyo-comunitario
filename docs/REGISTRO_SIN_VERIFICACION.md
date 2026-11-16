# Registro sin verificación obligatoria — 15-11-2026

## Comportamiento

La autenticación pertenece a Django y django-allauth; Supabase se usa únicamente como PostgreSQL. No existe dependencia de Supabase Auth.

`POST /api/register/` valida contraseña, correo, mayoría de edad, privacidad y tipo de cuenta. Crea una cuenta activa y un perfil con rol Voluntario o Solicitante. Devuelve 201 y mensaje de éxito, sin enviar correo ni invocar generación de confirmación. React abre el inicio de sesión y muestra ese mensaje. Los correos duplicados, incluyendo diferencias de mayúsculas, producen 409 sin modificar la cuenta original. Se mantienen las restricciones únicas en base de datos, las contraseñas con hash y el límite de intentos.

`ACCOUNT_EMAIL_VERIFICATION=none` elimina la barrera de allauth. El login JSON, la incorporación al perfil de voluntario y el espacio de solicitantes dejan de exigir el indicador de correo comprobado. El indicador `EmailAddress.verified` se conserva: no se falsifica ni se actualiza masivamente. Las cuentas existentes, sus estados activos/inactivos, roles y factores MFA permanecen iguales. No hacen falta migraciones ni cambios de datos en Supabase.

Los permisos backend, CSRF, validadores de contraseña y MFA enrolado siguen vigentes. El registro no admite escoger administración o secretaría. Las solicitudes de usuarios autenticados pueden revisarse sin simular una comprobación de correo; se identifica su procedencia de cuenta y se mantiene `email_verified_at` vacío cuando corresponde. Las solicitudes públicas anónimas mantienen su verificación independiente y no se vinculan automáticamente a cuentas por coincidencia de correo.

## Recuperación y riesgo residual

La recuperación conserva los enlaces firmados, caducables y de un solo uso de allauth. El formulario personalizado permite recuperar exclusivamente una cuenta activa cuyo `User.email` coincide con el destino. Un alias secundario, incluso marcado como verificado, no puede desviar la recuperación a otra cuenta. El enlace debe llegar al buzón principal; solicitarlo no cambia la contraseña ni inicia sesión. Después de cambiar la contraseña, las sesiones anteriores dejan de acceder. Las contraseñas nuevas siguen pasando los validadores de Django.

Eliminar la verificación permite registrar un correo mal escrito o ajeno. La plataforma ya no acredita propiedad del buzón al registrarse; el dueño real de ese buzón puede recuperar la cuenta. No usar coincidencia de correo como prueba de identidad, para conceder roles ni para reclamar solicitudes o datos ajenos. Se acepta además mayor exposición a enumeración porque el registro informa correos duplicados; los límites de intentos siguen activos. En producción, SMTP y los procedimientos institucionales de recuperación siguen siendo necesarios.

## Logo

Se reemplazaron ambas copias por la imagen proporcionada por el usuario, sin rediseño ni remuestreo. Se ajustaron las cajas de presentación a formato cuadrado y se versionaron las URL para evitar la copia anterior en caché. El archivo original mantiene su resolución; su mayor tamaño implica una descarga inicial mayor, reutilizada por la caché del navegador.

## Archivos modificados

- `backend/config/settings.py`: política de allauth y formulario de recuperación.
- `backend/accounts/views.py`: registro, respuesta de duplicados, login y onboarding.
- `backend/accounts/forms.py`: recuperación limitada al correo principal activo.
- `backend/accounts/requesters.py`, `backend/accounts/workspaces.py` y `backend/activities/services.py`: continuidad del flujo de solicitudes desde cuentas, sin falsear verificación.
- `backend/accounts/account_management.py`: mensaje de invitación administrativa coherente; se conserva establecer contraseña mediante enlace seguro.
- `frontend/src/design/Auth.jsx` y `frontend/src/main.jsx`: éxito de registro y redirección a login.
- `frontend/src/accounts/UserManagement.jsx` y `frontend/src/activities/Operations.jsx`: estados coherentes con acceso sin verificación.
- `frontend/public/brand/fundacion-logo.png`, `backend/accounts/static/accounts/logo.png`, `frontend/src/design/Brand.jsx`, `frontend/src/design/pro12.css` y `backend/templates/account/base.html`: logo de mayor resolución, proporciones y caché.
- Pruebas: `backend/accounts/tests.py`, `backend/accounts/test_requesters.py`, `backend/accounts/test_management.py`, `backend/activities/test_pro12_flow.py` y `frontend/src/pro12.test.js`.
- Documentación: README, USUARIOS, IMPLEMENTACION y esta guía.

## Validación

Se prueban registro sin correo o tokens de confirmación, login inmediato, duplicados sin sobrescritura, contraseñas débiles, cuentas inactivas, permisos privados, recuperación de cuenta no verificada, reutilización de enlace rechazada, invalidación de sesiones previas y alias de otra cuenta. Se conserva el flujo integral de matching/documentos/participación, ahora sin confirmar correo tras el registro. Las pruebas de solicitantes verifican que su solicitud pueda aprobarse y producir un evento sin marcar falsamente un correo como comprobado. Las pruebas frontend verifican mensaje de éxito, ausencia de instrucciones de confirmación y conservación de recuperación y longitud mínima de contraseña.

Resultado local: 286 pruebas backend satisfactorias sobre PostgreSQL 17 aislado, sin omisiones; 32 pruebas frontend satisfactorias y compilación Vite correcta. La comprobación Django no detectó problemas ni migraciones faltantes.
