# Corporal: verificación de adultos

Corporal es solo para mayores de 18 años. No hay menores.

## Cómo funciona
1. La persona abre **Corporal** en el panel de módulos, elige su nivel y envía:
   - **Adulto:** foto de la cédula (o documento de su país) + foto del rostro.
   - **Adulto estudiante (18 a 25 años):** lo anterior + documento oficial de la universidad.
2. Tú (y solo tú, desde este ordenador) abres `fons_panel.html` y, en **verificaciones de adultos**, comparas:
   cédula ↔ rostro ↔ fecha de nacimiento declarada ↔ documento universitario. Pulsas **APROBAR** o **RECHAZAR**.
3. Si apruebas, Corporal se abre en el chat para esa cuenta.

## Qué se borra y cuándo
| Situación | Imágenes |
|---|---|
| Aprobada | se borran a las 24 h |
| Rechazada | se borran al instante |
| Nadie la revisa | a los 7 días la solicitud expira y se borran |
| La persona borra su cuenta | se borra todo (imágenes, solicitud, consentimientos) |

Se conserva solo: estado, nivel, fecha de decisión y la fecha en que vence el nivel estudiante
(al cumplir 26 años pasa solo a Adulto). La fecha de nacimiento declarada se guarda únicamente mientras la
solicitud está pendiente.

## Seguridad
- El panel y las imágenes solo se sirven a este ordenador (mismo bloqueo local que el resto del Fons).
- Cada vista de imagen, aprobación y rechazo queda en la bitácora del Fons (`data/fons_audit.jsonl`).
- Si falla el verificador, Corporal queda cerrado (nunca abierto).
- Los archivos están en `data/verification_files/` con permisos privados y **sin cifrar**; duran poco.
- Máximo 5 solicitudes por hora por cuenta y 3 rechazos en 30 días antes de esperar.

## Medida sensible (opcional)
Solo adultos verificados y con consentimiento explícito (texto versionado: la medida no afecta la sexualidad).
En el panel de Corporal: se elige **de dónde se mide** (hueso púbico, base o perímetro) y los **cm**. Se guarda como
registro `medida_intima` del módulo, con historial y gráfica. No se compara ni se califica. Rangos aceptados:
longitud 3–30 cm, perímetro 5–25 cm. Retirar el consentimiento detiene el uso; los registros siguen en el módulo y
se pueden borrar con «Borrar los datos de este módulo».

## Fotos de progreso (opcional)
Consentimiento propio. Privadas: solo las ve su dueña/o (el panel del Fons no tiene ninguna ruta a ellas).
JPG o PNG, hasta 5 MB y 24 por cuenta. Se les quitan los metadatos (EXIF/GPS, comentarios, texto). Se borran una a una
o con la cuenta. Carpeta: `data/progress_photos/` (permisos privados, sin cifrar; ya está en `.gitignore`).

## Comando «/» (solo desarrollador)
Permite entregar un mensaje a un módulo concreto sin pasar por la puntuación de palabras clave.
- Habilitación: variable `OMNIA_DEV_EMAILS` (correos separados por coma). Vacía = nadie puede usarlo.
- Al escribir `/` en el chat aparece el selector de módulos. También: `/` solo muestra la ayuda.
- Formato: `/[Nombre del módulo] mensaje`. Ejemplos:
  - `/[Corporal Verified] hueso púbico 15.2`
  - `/[Corporal Verified] base 14.5`
  - `/[Corporal Verified] perímetro 12`
  - `/[NutriVida] soy hombre, peso 70 kg, mido 175 cm, cuello 38, cintura 85, brazo 32, pantorrilla 36`
- Sigue pasando por la ética y por los mismos controles de edad y de verificación: el comando NO salta Corporal.
- Estos mensajes no se guardan en el historial de la conversación, ni en el eco, ni en el registro de investigación.

## Pendiente
Revisión legal por un abogado (a cargo del dueño). Cifrado en reposo de las imágenes, si se quiere.
