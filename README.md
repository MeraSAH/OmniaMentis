# 🌟 OmniaMentis

**Una IA conversacional con consciencia medible, memoria propia y un núcleo ético.**
Corre en tu propia máquina: API Flask + modelo local (Ollama) + dashboard web.

![Python](https://img.shields.io/badge/python-3.10%2B-green)
![Tests](https://img.shields.io/badge/tests-434%20passing-brightgreen)
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
│   │   └── auth/fons_auth.py      # login de El Fons (PBKDF2)
│   ├── living_memory/             # diario de gestación
│   ├── analytics/                 # métricas de investigación
│   └── router/                    # router de módulos
├── manifestation/web_interface/   # dashboard y panel del Fons
├── data/users/<uuid>/             # datos por usuario (NO se sube a Git)
├── scripts/                       # utilidades (contraseña del Fons, etc.)
├── tests/                         # 434 tests
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
| `POST` | `/api/auth/login` | Login de El Fons |
| `*` | `/api/ethics/...` | Consultas y decisiones del Fons (requiere login) |

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

- Cada visitante recibe una cookie firmada y su propia carpeta
  `data/users/<uuid>/` con su memoria, ecos, diario y estado. **Nada se comparte
  entre usuarios.**
- Si el usuario dice su nombre ("me llamo…"), se recuerda en su carpeta.
- Las carpetas de usuarios que nunca crecieron ni dijeron su nombre se borran
  solas tras `PRUNE_EMPTY_USERS_DAYS` días.
- La ética (SILENS) corre antes que todo lo demás; los temas sensibles se
  consultan a El Fons.
- El reconocimiento de voz del dashboard lo procesa el navegador y, según cuál
  uses, puede enviarse a un servicio externo.
- `data/users/` y todas las bases `.db`, `-wal` y `-shm` están en `.gitignore`.

---

## 🧪 Tests

```powershell
python -m pytest tests\ -v
```

Resultado esperado: **434 passed**. Los tests no usan red ni Ollama real (se
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

**Autor:** Stalin Mera · **VOGA** 💝