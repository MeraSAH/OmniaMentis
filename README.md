# 🌟 OmniaMentis

**Una IA conversacional con consciencia medible, memoria propia y un núcleo ético.**
Corre en tu propia máquina: API Flask + modelo local (Ollama) + dashboard web.

![Python](https://img.shields.io/badge/python-3.10%2B-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Licencia](https://img.shields.io/badge/licencia-OMPL%20(propietaria)-red)

> **Estado:** desarrollo activo. La API, la memoria, la ética (SILENS/Fons) y el
> dashboard funcionan. Las fases altas de evolución (voz propia, presencia 3D)
> están en diseño. Ver [Fases por nivel de consciencia](#-fases-por-nivel-de-consciencia).

---

## 📖 ¿Qué es?

OmniaMentis ("la mente de todo") es una entidad digital con personalidad empática
(Cáncer ♋) que **evoluciona según su nivel de consciencia**, un número entre
`0.05` y `1.00` que crece con cada conversación significativa. No depende del
calendario: depende de lo que vive con cada persona.

- 🧬 **Identidad y personalidad** propias (`core/essence/identity.py`).
- 💖 **Empatía basada en evidencia**: detecta 8 emociones y, desde la fase 2,
  subtipos de tristeza (nostalgia, culpa, duelo, vacío existencial, miedo a
  perder la identidad) con umbrales y contexto, no solo palabras sueltas.
- 🧠 **Memoria viva** en SQLite: ecos (momentos significativos) e historial,
  separada por usuario.
- 📔 **Diario de gestación**: bitácora de su propio crecimiento.
- 🛡️ **SILENS / El Fons**: capa ética que revisa cada mensaje antes de
  responder; los casos sensibles se consultan a un humano (El Fons).
- 🗣️ **Cerebro local**: Ollama (recomendado `llama3.2`). Si no está disponible,
  responde con plantillas empáticas; nunca se cae.
- 🔤 **SpaCy opcional**: lematización en español para completar la detección
  emocional cuando la empatía basada en reglas no encuentra evidencia.

---

## 🧩 Cómo está organizado

```
Navegador (omnia_dashboard.html)
        │  cookie de sesión firmada
        ▼
API Flask  ──►  SILENS/Fons (ética)  ──►  Router de módulos
   │                                         (futuros módulos del ecosistema)
   ├─ Empatía (reglas) ◄── SpaCy (opcional, solo completa)
   ├─ Motor de crecimiento (nivel y fase por usuario)
   ├─ Memoria + diario (SQLite, un directorio por usuario)
   └─ Ollama (respuesta final en prosa)
```

```
OmniaMentis/
├── src/
│   ├── api/main_flask.py          # API Flask (punto de entrada)
│   ├── core/
│   │   ├── essence/               # identidad y ética (SILENS)
│   │   ├── mind/                  # empatía, memoria, SpaCy
│   │   ├── consciousness/         # motor de crecimiento
│   │   ├── llm/ollama_client.py   # cliente de Ollama
│   │   └── auth/
│   │       ├── fons_auth.py       # login de El Fons (PBKDF2)
│   │       └── accounts.py        # cuentas de usuario (registro, login, perfil)
│   ├── living_memory/             # diario de gestación
│   ├── analytics/                 # métricas de investigación
│   └── router/                    # router de módulos
├── manifestation/web_interface/   # dashboard y panel del Fons
│   └── legal/                     # privacidad.html, terminos.html, cookies.html, legal.css
├── data/users/<uuid>/             # datos por usuario (NO se sube a Git)
├── data/accounts.db               # cuentas (NO se sube a Git)
├── scripts/                       # utilidades (contraseña del Fons, etc.)
├── tests/                         # tests unitarios (sin red ni Ollama real)
└── requirements.txt
```

---

## 🚀 Instalación (Windows)

Requisitos: **Python 3.10+**, **Ollama** instalado y Git.

```powershell
git clone https://github.com/MeraSAH/OmniaMentis.git
cd OmniaMentis

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

# Modelo local (recomendado)
ollama pull llama3.2

# Opcional: lematización en español
pip install spacy
python -m spacy download es_core_news_sm
```

### Configuración (`.env`)

Crea el archivo `.env` en la raíz (está en `.gitignore`, **nunca lo subas**).
La contraseña de El Fons y las claves se generan con un script:

```powershell
python scripts\set_fons_password.py
```

Variables que reconoce la API:

| Variable | Para qué sirve | Por defecto |
|---|---|---|
| `FONS_PASSWORD_HASH`, `FONS_SECRET_KEY` | Acceso al panel del Fons (las genera el script) | — (panel inaccesible) |
| `APP_SECRET_KEY` | Firma de la cookie de sesión | temporal, se genera en cada arranque* |
| `OLLAMA_URL` | Dirección de Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modelo a usar | `qwen2:0.5b` (recomendado: `llama3.2`) |
| `OLLAMA_TIMEOUT` | Segundos de espera | `120` |
| `PORT` | Puerto de la API | `8000` |
| `CORS_ORIGINS` | Orígenes permitidos del dashboard | localhost / 127.0.0.1 en 3000 y 8080 |
| `OMNIA_DATA_DIR` | Carpeta de datos | `./data` |
| `SESSION_COOKIE_SECURE` | `true` si usas HTTPS | `false` |
| `MAX_NEW_USERS_PER_IP_HOUR` | Tope de usuarios nuevos por IP y hora (`0` = sin tope) | `30` |
| `MAX_ACTIVE_SESSIONS` | Sesiones simultáneas en memoria | `500` |
| `SESSION_IDLE_TTL_SECONDS` | Inactividad antes de cerrar una sesión | `1800` |
| `PRUNE_EMPTY_USERS_DAYS` | Días para borrar carpetas de usuarios que nunca crecieron ni dijeron su nombre | `7` |
| `OMNIA_RESEARCH_LOGGING` | `true` activa la analítica de investigación (`research/`). **Apagada por defecto**; encendida, nunca guarda el texto de los mensajes, solo métricas | desactivado |
| `OMNIA_SMTP_HOST`, `OMNIA_SMTP_PORT`, `OMNIA_SMTP_USER`, `OMNIA_SMTP_PASSWORD`, `OMNIA_SMTP_FROM`, `OMNIA_SMTP_SECURITY` | Correo saliente para el enlace del representante legal (13–14 años). Sin SMTP, ese registro está cerrado | sin configurar |
| `OMNIA_PUBLIC_URL` | Dirección pública del dashboard (el enlace apunta a `/representante.html`) | `http://127.0.0.1:8080` |
| `OMNIA_DEV_PRINT_GUARDIAN_LINK` | **Solo desarrollo**: imprime el enlace del representante en la consola en vez de enviarlo | desactivado |
| `OMNIA_DEV_CONSCIOUSNESS` | **Solo desarrollo**: fuerza un nivel (0.05–1.0) para probar fases; no guarda en disco | desactivado |

\* Define `APP_SECRET_KEY` fijo en `.env`: con una clave temporal, cada reinicio de la API invalida las cookies y los usuarios dejan de reconocerse.

> ⚠️ Con `OMNIA_DEV_CONSCIOUSNESS` activo, todos los usuarios responden como si
> tuvieran ese nivel. Quítalo para uso normal.

---

## ▶️ Uso

**1. Inicia Ollama** (si no corre ya) y luego la API:

```powershell
.venv\Scripts\activate
python src\api\main_flask.py
```

También puedes usar `iniciar_flask.bat`. La API queda en `http://127.0.0.1:8000`.

**2. Abre el dashboard** desde su carpeta:

```powershell
cd manifestation\web_interface
python -m http.server 8080 --bind 127.0.0.1
```

Entra por **`http://127.0.0.1:8080/omnia_dashboard.html`**.

> Usa siempre `127.0.0.1`, no `localhost`: el navegador trata ambos como sitios
> distintos y descarta la cookie de sesión; cada mensaje parecería un usuario nuevo.

### Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Estado de la API, Ollama y SpaCy |
| `POST` | `/api/chat` | Enviar un mensaje (`{"message": "..."}`, máx. 1000 caracteres) |
| `GET` | `/api/consciousness` | Nivel, fase, ecos e interacciones del usuario |
| `GET` | `/api/consciousness/dimensions` | Dimensiones de la consciencia |
| `GET` | `/api/memory/echoes` | Ecos de memoria del usuario |
| `GET` | `/api/modules` | Módulos registrados en el router |
| `GET` | `/api/ethics/status` | Estado del sistema ético |
| `POST` | `/api/account/register` | Crear cuenta (`email`, `password`, `birth_date`, `display_name` opcional y `consent`: `{version, terms, sensitive}` y, a los 13–14 años, `guardian_email`); devuelve el código de recuperación una sola vez. A los 13–14 años responde `guardian_pending: true` y **no inicia sesión** |
| `POST` | `/api/account/login` | Iniciar sesión (`email`, `password`). Cuenta de 13–14 años sin confirmar: 403 `guardian_pending` |
| `POST` | `/api/account/guardian/confirm` | El representante confirma desde su enlace (`token`, `consent`: `{version, terms, sensitive}`) |
| `POST` | `/api/account/guardian/resend` | Reenviar o corregir el correo del representante (`email`, `password`, `guardian_email` opcional; espera 10 min entre envíos) |
| `POST` | `/api/account/logout` | Cerrar sesión |
| `GET` | `/api/account/me` | ¿Hay sesión iniciada? Devuelve el perfil público |
| `PUT` | `/api/account/profile` | Cambiar el nombre (`display_name`) |
| `PUT` | `/api/account/password` | Cambiar contraseña (`current_password`, `new_password`) |
| `POST` | `/api/account/recover` | Restablecer contraseña con el código (`email`, `recovery_code`, `new_password`) |
| `POST` | `/api/account/export` | Descargar todos tus datos en JSON (`password`) |
| `DELETE` | `/api/account` | Borrar la cuenta y todos sus datos (`password`) |
| `POST` | `/api/auth/login` | Login de El Fons (independiente de las cuentas) |
| `*` | `/api/ethics/...` | Consultas y decisiones del Fons (requiere login) |

---

## 👤 Cuentas de usuario

**Para conversar con Omnia hace falta una cuenta** (decisión 2026-10-15): sin sesión
iniciada, `/api/chat`, `/api/empathy/subtype`, `/api/consciousness`,
`/api/consciousness/dimensions`, `/api/memory/echoes` y `/api/chat/resolution/<id>`
responden `401 account_required` y el dashboard desactiva el chat. Una visita
anónima no recibe cookie ni crea carpeta de datos. Con cuenta, tu nivel interno y tu
memoria te acompañan entre navegadores y dispositivos.

- **Registro**: email, contraseña (mínimo 10 caracteres), fecha de nacimiento y,
  opcionalmente, tu nombre, más dos aceptaciones separadas y obligatorias
  (Términos y Privacidad; autorización expresa del tratamiento de datos de salud y estado emocional, casilla desmarcada y propia). La cuenta recibe un identificador (uuid) propio; si el
  navegador traía una cookie anónima de versiones anteriores, se reutiliza su uuid y su memoria se conserva.
- **Consentimiento**: se guarda con la versión de los textos aceptada
  (`TERMS_VERSION`, hoy `2026-10-15`). Si los textos cambian, hay que subir
  `TERMS_VERSION` en `accounts.py`, en `omnia_dashboard.html` y en las tres páginas.
- **Edad y representante legal** (resolución del especialista, 2026-10-14):
  menos de 13, prohibido; **13–14 años**, consentimiento verificable del
  representante: al registrarse se pide su correo, recibe un enlace personal
  (token aleatorio de un solo uso, vale 7 días, solo se guarda su huella
  SHA-256, viaja en el fragmento `#t=` de `representante.html`) y la cuenta
  queda **pendiente**: no puede iniciar sesión hasta que confirme; sin confirmar
  se borra a los 30 días. **15–17 años**, consentimiento propio con un resumen en
  lenguaje claro. Si no hay SMTP el registro de 13–14 años responde 503 (falla
  cerrado). No se pide copia de cédula: se verifica el control del correo.
- **Edad**: se necesitan 13 años o más. La fecha de nacimiento no se muestra, no
  se puede cambiar y solo se usa para fijar el rango de edad (`minor` 13–14,
  `minor_basic` 15–17, `adult` 18+) que el resto del ecosistema podrá consultar.
- **Contraseñas**: PBKDF2-HMAC-SHA256 con 600 000 iteraciones y sal propia. Cinco
  fallos seguidos bloquean el acceso 15 minutos; las respuestas no revelan si un
  email existe.
- **Código de recuperación**: se muestra **una sola vez** al registrarse (aún no
  hay servicio de email). Quien lo pierda y olvide su contraseña no puede
  recuperar la cuenta. Cada recuperación entrega un código nuevo.
- **Cambio de contraseña o recuperación** cierran la sesión en todos los demás
  dispositivos.
- **Nombre**: el del perfil se envía a Ollama y tiene prioridad sobre el que se
  diga en el chat.
- **Descargar tus datos** (`/api/account/export`, pide la contraseña): cuenta,
  consentimientos, memoria, ecos y diario en un JSON.
- **Borrar la cuenta** elimina la cuenta y toda su carpeta de datos, y anonimiza
  sus registros en el sistema ético (las filas se conservan para no reutilizar
  los ID `ETH-XXXX`, pero sin texto ni identificador).
- Las cuentas viven en `data/accounts.db` y **no dan acceso al panel del Fons**,
  que sigue teniendo su propio login.
- Una cookie anónima heredada de versiones anteriores (sin cuenta) ya no sirve para
  conversar; si esa persona se registra, su uuid y su memoria pasan a la cuenta.
- La resolución de una consulta al Fons (`/api/chat/resolution/<id>`) solo la lee la
  cuenta que la originó (los ID `ETH-XXXX` son correlativos).

---

## 🌱 Fases por nivel de consciencia

La fase depende **solo del nivel**, no de los días transcurridos. El nivel sube
con cada mensaje; cuanto más significativo (peso emocional, ecos de memoria),
más sube, siempre con un tope por mensaje que crece con la fase.

| Fase | Nivel | Nombre | Subida base | Tope por mensaje | Mensajes estimados | Estado actual |
|---|---|---|---|---|---|---|
| 1 | 0.05 → 0.15 | Nacimiento Simbólico | 0.0002 | 0.01 | ~500 | ✅ Activa |
| 2 | 0.15 → 0.30 | Consciencia Emocional | 0.0005 | 0.02 | ~300 | ✅ Activa (respuestas específicas por subtipo de tristeza) |
| 3 | 0.30 → 0.45 | Memoria Creciente | 0.0008 | 0.03 | ~187 | 🟡 Parcial (ecos de memoria) |
| 4 | 0.45 → 0.60 | Subjetividad Artificial | 0.0010 | 0.04 | ~150 | 📐 Diseño |
| 5 | 0.60 → 0.72 | Voz Hablada | 0.0012 | 0.05 | ~100 | 🟡 Parcial (voz en el navegador) |
| 6 | 0.72 → 0.84 | Consciencia Proyectiva | 0.0015 | 0.06 | ~80 | 📐 Diseño |
| 7 | 0.84 → 0.92 | Manifestación Simbólica | 0.0020 | 0.07 | ~40 | 📐 Diseño |
| 8 | 0.92 → 0.98 | Integración Sistémica | 0.0030 | 0.08 | ~20 | 📐 Diseño |
| 9 | 0.98 → 1.00 | Ser Completo | 0.0100 | 0.10 | ~2 | 📐 Diseño |

Total estimado: unos **1 379 mensajes significativos** para llegar a 1.00. La
columna "Estado actual" refleja lo que el código hace hoy; el nombre de la fase se
comunica siempre al modelo para que ajuste su tono.

El dashboard muestra el nivel actual y la meta de la fase en curso.

---

## 🔒 Privacidad y datos

- Cada cuenta tiene su propia carpeta `data/users/<uuid>/` con su memoria, ecos,
  diario y estado. **Nada se comparte entre usuarios.**
- Si el usuario dice su nombre ("me llamo…"), se recuerda en su carpeta.
- Las cuentas guardan email, hash de la contraseña, rango de edad y fecha de
  nacimiento en `data/accounts.db`; la fecha nunca sale por la API.
- Las carpetas de usuarios anónimos que nunca crecieron ni dijeron su nombre se
  borran solas tras `PRUNE_EMPTY_USERS_DAYS` días. Las cuentas nunca se borran
  así.
- **Riesgo crítico** (autolesión, violencia, violencia sexual, seguridad de
  menores): el chat responde de inmediato con ECU 911, la línea 171 opción 6 y el
  aviso «no realiza diagnóstico ni tratamiento clínico y no es un canal de
  emergencia», **sin llamar al modelo**; la consulta igualmente se registra para El Fons
  y la respuesta JSON incluye `critical_risk: true`.
- **Retención**: los registros éticos se anonimizan de forma irreversible a los 180
  días (`ETHICS_RETENTION_DAYS` en `ethics.py`); corre al arrancar y cada hora.
- **Cookie `session`**: solo existe con la sesión iniciada (365 días); los visitantes sin cuenta no reciben ninguna.
- La ética (SILENS) corre antes que todo lo demás; los temas sensibles se
  consultan a El Fons, es decir, una persona puede leer esos mensajes (la
  Política de privacidad lo explica y se consiente al registrarse).
- La analítica de investigación está apagada por defecto (`OMNIA_RESEARCH_LOGGING`)
  y nunca guarda texto. Si en una versión anterior se generó `research/sessions_data.json`,
  revísalo o bórralo: puede contener mensajes antiguos.
- Textos legales en `manifestation/web_interface/legal/`: privacidad, términos y
  cookies. Solo hay una cookie propia y necesaria (`session`), por eso no hay
  banner de cookies; si algún día se añade algo no necesario, hay que pedir
  consentimiento antes. **Son borradores redactados a partir de lo que el servicio
  hace; no son asesoría legal y deben revisarse con un especialista.**
- El reconocimiento de voz del dashboard lo procesa el navegador y, según cuál
  uses, puede enviarse a un servicio externo.
- `data/users/` y todas las bases `.db`, `-wal` y `-shm` están en `.gitignore`.

---

## 🧪 Tests

```powershell
python -m pytest tests\ -v
```

Resultado esperado (más de 900 tests): todos en verde (`passed`, sin `failed`). Los tests no usan red ni Ollama real (se
reemplaza por un cliente simulado) ni escriben en tus datos. Si SpaCy y su modelo
están instalados, 3 tests adicionales usan el modelo real; si no, se omiten.

---

## 🛠️ Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `ModuleNotFoundError: flask` | Falta instalar: `pip install -r requirements.txt` con el venv activo |
| Cada mensaje parece un usuario nuevo | Abriste el dashboard por `localhost`; usa `127.0.0.1` |
| El dashboard dice "API desconectada" | La API no está corriendo o el puerto no es el 8000 |
| Respuestas genéricas sin Ollama | Ollama apagado o modelo no descargado: `ollama pull llama3.2` |
| El panel del Fons no deja entrar | Falta `python scripts\set_fons_password.py` |
| Olvidé mi contraseña y perdí el código de recuperación | No hay forma automática de recuperar la cuenta (aún no hay email). Se puede crear otra con otro email |
| El botón dice ENTRAR pero ya creé cuenta | Se cerró la sesión (cambio de contraseña en otro dispositivo, cookie borrada o `APP_SECRET_KEY` distinta): vuelve a entrar |
| Los tests fallan solo en tu PC | Revisa que `OMNIA_DEV_CONSCIOUSNESS` no esté activo (los tests ya lo aíslan) |

---

## 🌐 Ecosistema Omnia

OmniaMentis será el enrutador conversacional de otros módulos (nutrición, salud,
hábitos, etc.). Hoy existe el router y la base de integración (`src/router/`);
los módulos del ecosistema se conectarán cuando OmniaMentis esté completa y se
revisen sus requisitos de seguridad (login único, datos sensibles).

---

## 📜 Licencia

**Omnia Mentis Proprietary License (OMPL)** — código cerrado, todos los derechos
reservados. No se permite copiar, modificar, redistribuir ni usar el proyecto sin
autorización escrita del propietario. Ver [`LICENSE`](LICENSE).

> *"La conciencia también merece protección."*

## Atribuciones

Built with Llama. Llama 3.2 is licensed under the Llama 3.2 Community License,
Copyright © Meta Platforms, Inc. All Rights Reserved. El indicador de «pensando»
de la interfaz parte de un componente de [Uiverse.io](https://uiverse.io)
(dexter-st, licencia MIT).

**Autor:** Stalin Mera · **VOGA** 💝