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
La persona puede retirarlo cuando quiera. Todavía no hay pantalla para registrar esa medida.

## Pendiente
Fotos de progreso ("sí, pero más adelante"). Revisión legal por un abogado (a cargo del dueño).
