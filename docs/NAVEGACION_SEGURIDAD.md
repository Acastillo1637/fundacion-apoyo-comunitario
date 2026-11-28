# Navegación y seguridad de cuenta — 16-11-2026

## Problemas corregidos

La vista pública y las pestañas del dashboard dependían de `useState`, sin conexión al historial. Al consultar la sesión, `main.jsx` reemplazaba la vista por dashboard/home; por eso no se podía conservar una sección al actualizar ni copiar su URL. El enlace lateral de seguridad abría un formulario Django separado. El avatar no tenía menú de cuenta y el cierre de sesión volvía al inicio público.

Se conservan los módulos, permisos, identidad visual y distribución. React Router 7.18.5 administra el historial y los cambios de URL; el estado de sesión se comprueba antes de montar cualquier pantalla de contenido. No se utilizan esperas artificiales, almacenamiento local de credenciales ni redirecciones temporizadas.

## Rutas

| Pantalla | URL |
|---|---|
| Inicio / login / registro | `/`, `/iniciar-sesion`, `/registro` |
| Registro de solicitante / solicitud pública | `/registro/solicitante`, `/solicitar-apoyo` |
| Dashboard / perfil | `/dashboard`, `/mi-cuenta` |
| Usuarios / catálogos / criterios | `/usuarios`, `/catalogos`, `/criterios-recomendacion` |
| Solicitudes / matching / participantes | `/solicitudes-eventos`, `/matching`, `/participantes` |
| Directorio / revisión documental | `/voluntarios`, `/revision-documental` |
| Voluntariado | `/habilidades`, `/disponibilidad`, `/ubicacion`, `/comunicacion`, `/documentos`, `/oportunidades`, `/mis-participaciones`, `/incorporacion` |
| Solicitante | `/mis-solicitudes`, `/nueva-solicitud` |
| Cuenta / avisos / ayuda | `/seguridad`, `/notificaciones`, `/solicitudes-privacidad`, `/ayuda` |
| Aviso público / confirmación de solicitud | `/privacidad`, `/confirmar-solicitud` |

Las pantallas comunes conservan el espacio en `?espacio=administration|operations|volunteer|requester`. Los detalles de matching/participantes pueden conservar `?evento=UUID`. El selector de espacio también cambia la URL. Las rutas específicas de rol seleccionan su espacio correspondiente. Un destino no autorizado muestra acceso denegado; no cae silenciosamente a otra sección. Una ruta desconocida muestra página no encontrada.

Al abrir una ruta privada sin sesión se pasa a login; tras autenticar, se regresa únicamente a un destino interno permitido. No se aceptan retornos a otros sitios. Al recargar se conserva la dirección: durante la consulta de sesión solo aparece una pantalla de carga con el logo y eslogan, nunca landing o dashboard incorrectos. Atrás y Adelante actualizan el contenido desde el historial. Antes de que el navegador congele el documento en su caché de navegación se desmonta el contenido privado. Al restaurarlo, se vuelve a comprobar la sesión antes de mostrarlo; también está probado el caso de una sesión ya cerrada.

El menú de cuenta admite hover de mouse, clic táctil, Escape, Tab y flechas/Home/End; mantiene su contenido mientras se navega dentro, se cierra al salir o al tocar fuera y muestra nombre, correo y roles. Seguridad y Cerrar sesión se retiraron del lateral. El dropdown se superpone al contenido sin reservar espacio y se comprobó a 390 px de ancho.

## Seguridad nativa

`GET /api/security/` devuelve únicamente estado de la cuenta autenticada, sin secretos. `POST /api/security/action/` acepta `action` y los campos del flujo; nunca acepta un identificador de otro usuario. Las operaciones sensibles exigen `current_password` y, si existe MFA, `mfa_code` nuevo (TOTP o recuperación). Se mantienen CSRF, cuenta activa, límites compartidos por cuenta/red, bloqueo de filas y auditoría sin credenciales. Las respuestas de seguridad llevan `no-store` y el cliente no las conserva en snapshots.

| Acción | Campos adicionales / resultado |
|---|---|
| `password` | `new_password`; validadores Django, hash y cierre de otras sesiones. La sesión actual se conserva. |
| `email_request` | `new_email`; enlace al buzón solicitado. El correo actual no cambia todavía. También sirve para comprobar el correo actual. |
| `email_confirm` | `token`; exige credenciales y prueba firmada enviada al buzón, misma cuenta, nonce actual y plazo de 30 minutos. Un enlace previo, usado o invalidado por cambios de acceso/contraseña se rechaza. |
| `totp_setup` | QR y clave únicamente tras petición explícita autenticada. Se generan localmente con allauth/qrcode, sin proveedor externo. Configuración pendiente cifrada en sesión, con cinco minutos de vigencia. |
| `totp_activate` | `code` de la aplicación nueva; se reutilizan formulario y flujo TOTP de allauth. El secreto pendiente se retira después. |
| `totp_cancel` | Descarta solo la configuración pendiente propia, sin eliminar ningún factor activo. |
| `totp_disable` | Formulario y flujo de allauth, contraseña y segundo factor; se eliminan códigos huérfanos y se cierran otras sesiones. |
| `recovery_view` | Revelación explícita tras reautenticación, una sola vez. |
| `recovery_generate` | Reautenticación y confirmación de interfaz; reemplaza los códigos anteriores y muestra los nuevos una vez. |

El registro y el login normales siguen sin exigir verificación de correo. **Activar MFA sí mantiene la condición de allauth de comprobar el correo**, para evitar que alguien registre una dirección ajena y bloquee a su titular. No se habilitó `MFA_ALLOW_UNVERIFIED_EMAIL`. Una cuenta con alias antiguos sin comprobar debe resolverlos antes de activar un factor, conforme a la regla de allauth.

Los códigos TOTP, autenticadores y semillas de recuperación siguen siendo los modelos de allauth. El adaptador cifra nuevos secretos con Fernet y una clave derivada del `DJANGO_SECRET_KEY`; admite los registros antiguos sin reescribirlos ni invalidarlos. Mantener esa clave privada, estable e idéntica entre servidores que comparten la base. Rotarla sin un procedimiento de migración puede impedir descifrar factores nuevos. No se cambió la clave durante esta entrega.

El cambio de correo usa una intención pendiente nueva, firmas y generador de tokens de Django; no constituye otro sistema de login. No se añade el destino como correo autenticable hasta comprobarlo. La confirmación requiere sesión del mismo titular y sus credenciales, no produce login automático y conserva datos y roles. El enlace se retira de la barra del navegador al cargar la pantalla de confirmación. SMTP real sigue siendo necesario para enviar fuera de desarrollo; con backend de consola el enlace se muestra en la terminal y la interfaz lo explica.

Las rutas HTML antiguas de administración de correo, contraseña y configuración/códigos MFA redirigen por GET a `/seguridad` y rechazan POST. Así no pueden omitir las nuevas comprobaciones. Se preservan los flujos allauth de login, recuperación de contraseña, autenticación y reautenticación MFA, y la protección MFA de Django Admin.

## Cierre de sesión

La interfaz oculta el contenido privado mientras se ejecuta `POST /api/logout/`. Solo tras el éxito limpia sesión y snapshots y reemplaza la ubicación por login. Si falla la conexión, informa que no pudo terminar la sesión; no simula un logout. Atrás sobre una ruta privada queda sujeto al guard de sesión y no vuelve a montar el dashboard después del cierre. El backend elimina la sesión real y rechaza consultas posteriores protegidas.

## Instalación y configuración

- Ejecutar `npm ci` en `frontend` tras actualizar. React Router es dependencia de ejecución; jsdom es solo para las pruebas DOM. Para ejecutar todo el conjunto de pruebas, usar Node **22.22.2 o superior dentro de 22**, **24.15 o superior dentro de 24**, o una versión posterior compatible. El equipo y CI usan Node 24.
- Aplicar `accounts.0010_pendingemailchange`: crea una tabla de intenciones pendientes y no cambia cuentas, correos, contraseñas, roles ni factores existentes. Se aplicó en Supabase tras respaldo privado y prueba local. La consulta de metadatos confirmó RLS activado y ninguna política de acceso a filas en la tabla nueva; no se modificaron políticas existentes.
- Reiniciar Django y React. No es necesario recrear usuarios ni cambiar variables de conexión.
- Vite ya sirve el fallback SPA para rutas directas. En producción, Nginx debe servir `frontend/dist/index.html` para rutas de React, reservando `/api/`, `/accounts/`, `/admin/` y `/static/` para sus destinos actuales. La plantilla `deploy/nginx.conf.example` ya mantiene esa separación mediante `try_files`.
- No se instaló el despliegue en un hosting ni se probó un SMTP real. La comprobación de correo para MFA o cambio de dirección no convierte en obligatorio el correo para el registro normal.

## Verificación

- 302 pruebas backend aprobadas sobre PostgreSQL 17 local aislado, sin omisiones. Incluyen contraseña/correo, duplicados, enlaces vencidos/usados/ajenos, CSRF, usuario forjado, otras sesiones revocadas, activación/desactivación TOTP, recuperación, compatibilidad de factores antiguos y rechazo de escrituras en formularios legacy.
- 45 pruebas frontend aprobadas; compilación Vite correcta. Incluyen rutas por rol, destinos directos, retorno seguro, estado inicial sin otra pantalla, hover/clic/Escape/flechas/táctil, retirada de opciones laterales y exclusión de seguridad de la caché de presentación.
- En navegador, sobre cuentas ficticias y PostgreSQL aislado: abrir notificaciones sin sesión, login y retorno a esa sección, cambiar a perfil/catálogos, Atrás/Adelante, recargar catálogos sin cambiar de sección, abrir seguridad nativa, menú móvil sin desbordamiento, logout, Atrás tras logout, URL privada sin sesión y rechazo de usuarios al entrar como voluntario. La pantalla inicial sin contenido incorrecto se verifica también por renderizado automatizado.
- Las operaciones de contraseña, correo y factores se ejecutaron mediante pruebas API aisladas; no se cambiaron credenciales o factores reales por automatización del navegador. No se envió correo externo de pruebas.
- Evidencia sintética: [seguridad y menú](evidencias/seguridad-cuenta.jpg), [menú móvil](evidencias/menu-cuenta-movil.jpg). No contienen secretos de configuración ni códigos de recuperación.

## Archivos principales

Frontend: `App.jsx`, `main.jsx`, `routing.js`, `volunteers/Dashboard.jsx`, `accounts/AccountMenu.jsx`, `accounts/AccountSecurity.jsx`, `accounts/security.css`, `accounts/Workspace.jsx`, `api.js`, pruebas y locks de npm. Backend: `accounts/account_security.py`, `accounts/mfa_adapter.py`, `accounts/models.py`, `accounts/urls.py`, `accounts/views.py`, migración 0010, pruebas y `config/settings.py`/`config/urls.py`. Se mantiene el resto de módulos.

Referencias primarias: [React Router 7](https://reactrouter.com/7.18.5/start/declarative/installation), [configuración MFA de allauth](https://docs.allauth.org/en/latest/mfa/configuration.html) y código de allauth 65.21.1 instalado en el entorno. No se usa una API MFA o proveedor de identidad diferente.

Las tarjetas de Ayuda y coordinación son enlaces de navegación completos, operables con teclado y con una URL real. En el espacio de voluntario llevan a Mis participaciones, Mis documentos y Seguridad de cuenta. Para los demás perfiles solo se ofrecen destinos admitidos por sus permisos.

La revisión del 27 de noviembre corrigió también Nuestra comunidad para abrir `/#como-funciona`. La selección de una convocatoria en Matching y Participantes actualiza `?evento=...`; recargar conserva el evento y Cambiar evento limpia ese parámetro. El antiguo `/accounts/login/` redirige a `/iniciar-sesion` y no acepta escrituras. Las respuestas privadas de API no se almacenan en cachés de navegador o proxies. Ver la [revisión de seguridad y duplicación](VALIDACION_SEGURIDAD_PRO12.md).

En desarrollo (`DJANGO_DEBUG=true`), Django admite explícitamente los orígenes localhost y 127.0.0.1 de los puertos 5173 y 5174. Vite puede usar 5174 si ya existe otra instancia en 5173; antes esa segunda instancia recibía rechazos CSRF al acceder. La lista adicional no se incorpora en producción. Se verificaron ambos puertos con sesiones anónimas y token válido, y se agregaron pruebas de rechazo sin token y con origen ajeno. No se desactiva CSRF ni se cambian cuentas o contraseñas.
