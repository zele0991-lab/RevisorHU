# Guía de banca móvil

> Guía para personas. Explica por qué existen los criterios del paquete de banca móvil; **no
> define criterios**. Los criterios están solo en `criterios.yaml`.
>
> **Borrador v0.** Se valida con los líderes técnicos y con las áreas de Seguridad y
> Cumplimiento antes de usarlo en el banco. Las referencias normativas concretas las confirma
> Cumplimiento.

## Autenticación y segundo factor
Las operaciones sensibles (transferencias, alta de cuentas favoritas, cambio de datos, registro
de un dispositivo nuevo) piden reautenticación o un segundo factor. Una historia que **debilita**
la autenticación existente (por ejemplo, ingresar solo con un PIN corto) es un riesgo y entra en
conflicto con las historias que la exigen.

## Manejo de sesión
Hay que definir cuándo expira la sesión por inactividad, qué pasa cuando la app pasa a segundo
plano y si se permiten sesiones en varios dispositivos.

## Datos sensibles: enmascarado
Los números de cuenta y de tarjeta, la identificación y los saldos no se muestran completos en
notificaciones, capturas ni registros. Ejemplo: cuenta ****1234.

## Seguridad de la app (OWASP MASVS)
El estándar OWASP MASVS agrupa los controles de seguridad de apps móviles en áreas como
almacenamiento, criptografía, autenticación, red, plataforma, código, resiliencia y privacidad.
Una historia no debe contradecirlos: por ejemplo, no se guardan credenciales en texto plano en el
dispositivo, sino en el almacén seguro del sistema (Keychain en iOS, Keystore en Android).
Referencia: https://mas.owasp.org/MASVS/

## Trazabilidad y auditoría
Las operaciones monetarias y los cambios de datos del cliente dejan un registro auditable: quién,
qué, cuándo y desde qué dispositivo, sin datos sensibles en claro.

## Accesibilidad
Las pantallas nuevas consideran lectores de pantalla (VoiceOver, TalkBack), contraste y tamaño de
texto configurable. Como referencia se usa WCAG 2.1, nivel AA.

## Sin conexión, errores y operaciones duplicadas
Casi todo depende de la red. Hay que definir qué ve el cliente sin conexión o con un tiempo de
espera agotado. En operaciones monetarias, la app consulta el estado antes de reintentar, para no
cobrar dos veces (idempotencia).

## iOS y Android
Si la historia usa funciones del dispositivo (biometría, notificaciones, cámara, NFC), considera
las dos plataformas, sus versiones mínimas y la alternativa cuando la función no está disponible.

## Protección de datos personales (Costa Rica)
La Ley 8968, de Protección de la Persona frente al Tratamiento de sus Datos Personales, exige,
entre otros principios, el consentimiento informado y que los datos se usen solo para la
finalidad declarada. En una historia, cualquier dato personal nuevo (ubicación, contactos, fotos,
datos biométricos) debe indicar para qué se usa, cómo se pide el consentimiento y por qué es
necesario.

## Normativa SUGEF
Las operaciones financieras están sujetas a la normativa de la Superintendencia General de
Entidades Financieras (SUGEF) y del CONASSIF, incluida la de gestión de tecnología de
información. El agente no interpreta normas: si una historia crea o cambia una operación
financiera, límites o la información que se da al cliente, recomienda validarla con Cumplimiento.
