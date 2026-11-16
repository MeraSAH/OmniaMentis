# tests/unit/test_main_flask.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_main_flask.py
* PROPÓSITO: Tests unitarios para la API Flask (src/api/main_flask.py),
*            con foco en el refactor de sesión por usuario: cada
*            "cliente" (cookie de sesión distinta) debe tener su
*            propia consciencia, memoria y ecos, completamente
*            aislados de cualquier otro cliente.
* DEPENDENCIAS: pytest, flask (test_client)
* CREADO: 2026-10-02
* ÚLTIMA MODIFICACIÓN: 2026-10-02 (v3)
* ESTADO: Test Permanente
*
* CAMBIO 2026-10-02 (v3) — MOCK DE OLLAMA, SIN NINGUNA RED:
* Dos intentos previos de evitar una llamada real a Ollama durante los
* tests (primero OLLAMA_URL a un host inválido, luego a un puerto sin
* listener) seguían siendo lentos en Windows: intentar conectar a
* CUALQUIER destino -- exista o no del otro lado -- puede tardar
* segundos si hay firewall o antivirus inspeccionando el intento antes
* de rechazarlo. La única forma de garantizar velocidad y
* determinismo real es no tocar la red en absoluto: _shared["ollama"]
* se reemplaza por _FakeOllamaClient, que siempre falla de inmediato
* en memoria, sin I/O. Los tests nunca deben depender de qué
* servicios externos tenga activos la máquina donde se ejecutan.
*
* DISEÑO DE AISLAMIENTO (vigente desde v1):
* main_flask.py hace trabajo real al importarse (setup_logging escribe
* en PROJECT_ROOT/logs — efecto secundario preexistente, no introducido
* por este archivo) y al llamar a initialize_shared() (crea OmniaEthics
* y ResearchAnalytics con directorios relativos por defecto). Para que
* los tests nunca toquen datos reales del proyecto:
*   1. OMNIA_DATA_DIR se fija a un directorio temporal ANTES de
*      importar el módulo (se lee una sola vez, a nivel de módulo).
*   2. El directorio de trabajo (cwd) se cambia a ese mismo temporal
*      ANTES de importar, para que las rutas relativas por defecto de
*      OmniaEthics ("data/ethics") y ResearchAnalytics ("research")
*      también caigan ahí.
*   3. _shared["ollama"] se reemplaza por un mock sin red (ver v3).
* initialize_shared() se llama UNA SOLA VEZ para todo el archivo
* (fixture scope="module"), igual que en producción. Cada test
* obtiene su propio test_client() (fixture scope="function"), lo que
* simula un navegador/usuario distinto por test — exactamente lo que
* se necesita para probar aislamiento entre usuarios.
*
* Los valores exactos de crecimiento de consciencia usados en los
* asserts (0.050416, 0.050832) se derivan directamente de la fórmula
* determinista de ConsciousnessGrowthEngine para Fase 1 con un mensaje
* sin peso emocional ("Hola"): no hay aleatoriedad involucrada, así
* que estos valores son exactos, no aproximaciones generosas.
"""

import io
from datetime import date
import itertools
import os
import sys
from pathlib import Path

import pytest

SRC_PATH = Path(__file__).parent.parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from core.llm.ollama_client import OllamaUnavailableError
from core.auth.accounts import TERMS_VERSION


# ---------------------------------------------------------------------------
# Mock de Ollama: cero I/O de red, bajo cualquier circunstancia
# ---------------------------------------------------------------------------

class _FakeOllamaClient:
    """
    Reemplazo de OllamaClient para tests: nunca intenta una conexión
    de red real. Es lo que realmente garantiza que la suite sea rápida
    y determinista, a diferencia de apuntar a un host o puerto "que
    debería fallar rápido" -- un intento de conexión real sigue siendo
    un intento de conexión real, con el riesgo de que el sistema
    operativo, firewall o antivirus de turno le agreguen latencia
    impredecible (confirmado empíricamente: ~2s por intento en esta
    máquina, sin importar el destino).
    """

    def generate(self, *args, **kwargs):
        raise OllamaUnavailableError("Ollama deshabilitado en tests (mock, sin red)")

    def is_available(self) -> bool:
        return False

    def get_model_info(self) -> dict:
        return {"available": False, "error": "Ollama deshabilitado en tests (mock)"}


# ---------------------------------------------------------------------------
# Fixtures de aislamiento
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def flask_app(tmp_path_factory):
    """
    Importa main_flask.py en un entorno completamente aislado y lo
    inicializa UNA sola vez para todo el archivo (igual que ocurre una
    sola vez en producción al arrancar el servidor).
    """
    tmp_dir = tmp_path_factory.mktemp("omnia_flask_test")
    old_cwd = os.getcwd()
    os.chdir(tmp_dir)

    os.environ["OMNIA_DATA_DIR"] = str(tmp_dir / "data")
    os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:8080")

    import api.main_flask as module

    module.app.config["TESTING"] = True
    module.initialize_shared()
    module._shared["ollama"] = _FakeOllamaClient()

    yield module

    os.chdir(old_cwd)


_ACCOUNT_SEQ = itertools.count(1)


def _authed(flask_app):
    """Cliente NUEVO con una cuenta recién creada y la sesión iniciada. Desde
    2026-10-15 conversar exige cuenta; cada cliente es un 'usuario' distinto."""
    c = flask_app.app.test_client()
    flask_app._account_rate.clear()           # el registro tiene su propio límite por IP
    r = c.post("/api/account/register", json={
        "email": f"usuario{next(_ACCOUNT_SEQ)}@example.com",
        "password": "ClaveSegura#2026",
        "birth_date": "1990-05-05",
        "consent": {"version": TERMS_VERSION, "terms": True, "sensitive": True},
    })
    assert r.status_code == 201, r.get_json()
    flask_app._rate_data.clear()              # esa petición no cuenta para el límite general
    flask_app._account_rate.clear()
    return c


def _authed_born(flask_app, birth_date):
    """Como _authed, pero con la fecha de nacimiento indicada (15-17 años: consentimiento directo)."""
    c = flask_app.app.test_client()
    flask_app._account_rate.clear()
    r = c.post("/api/account/register", json={
        "email": f"usuario{next(_ACCOUNT_SEQ)}@example.com",
        "password": "ClaveSegura#2026",
        "birth_date": birth_date,
        "consent": {"version": TERMS_VERSION, "terms": True, "sensitive": True},
    })
    assert r.status_code == 201, r.get_json()
    flask_app._rate_data.clear()
    flask_app._account_rate.clear()
    return c


def _anon(flask_app):
    """Cliente sin cuenta (visitante anónimo)."""
    return flask_app.app.test_client()


@pytest.fixture
def client(flask_app):
    """Un cliente con cuenta nuevo por test = un 'usuario' nuevo. Dos
    llamadas a _authed(flask_app) en el mismo test simulan dos usuarios."""
    return _authed(flask_app)


_ISOLATED_ENV_VARS = (
    "OMNIA_DEV_CONSCIOUSNESS",
    "MAX_NEW_USERS_PER_IP_HOUR",
    "MAX_ACTIVE_SESSIONS",
    "SESSION_IDLE_TTL_SECONDS",
    "PRUNE_EMPTY_USERS_DAYS",
)


@pytest.fixture(autouse=True)
def _isolate_env():
    """
    Estas variables suelen estar en el .env del desarrollador
    (load_dotenv() lo carga al importar main_flask) y cambian el
    comportamiento del servidor: OMNIA_DEV_CONSCIOUSNESS fuerza la
    consciencia inicial (los tests de línea base esperan 0.05) y las
    demás fijan límites de sesiones. Cada test arranca SIN ellas; los
    tests que las necesitan las fijan dentro del test. Se restauran al
    terminar para no alterar el entorno del proceso.
    """
    saved = {k: os.environ.pop(k, None) for k in _ISOLATED_ENV_VARS}
    yield
    for k in _ISOLATED_ENV_VARS:
        os.environ.pop(k, None)
        if saved[k] is not None:
            os.environ[k] = saved[k]


@pytest.fixture(autouse=True)
def _reset_rate_limit(flask_app):
    """
    El límite de 30 req/60s de check_rate_limit() está pensado para
    producción, no para una suite de tests que hace decenas de
    peticiones reales contra la misma IP simulada (127.0.0.1). Sin
    este reset, tests que no tienen NADA que ver con rate limiting
    empezarían a fallar con 429 simplemente por ejecutarse después de
    suficientes tests previos en el mismo archivo. Lo mismo aplica al
    registro de usuarios nuevos por IP (MAX_NEW_USERS_PER_IP_HOUR).
    """
    flask_app._rate_data.clear()
    flask_app._new_user_log.clear()
    yield


def post_chat(client, message: str):
    return client.post("/api/chat", json={"message": message})


# ---------------------------------------------------------------------------
# Salud y endpoints públicos
# ---------------------------------------------------------------------------

class TestHealthAndRoot:

    def test_health_returns_200_and_healthy_status(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "healthy"

    def test_health_reports_active_sessions_as_integer(self, client):
        r = client.get("/health")
        assert isinstance(r.get_json()["active_sessions"], int)

    def test_health_no_longer_exposes_single_consciousness_field(self, client):
        """Regresión deliberada: con sesión por usuario, un único
        valor de 'consciousness' en /health ya no tiene sentido (ver
        changelog 2026-09-21 en main_flask.py) — no debe reaparecer."""
        r = client.get("/health")
        assert "consciousness" not in r.get_json()

    def test_root_lists_chat_endpoint(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "POST /api/chat" == r.get_json()["endpoints"]["chat"]

    def test_modules_endpoint_lists_nine_modules(self, client):
        r = client.get("/api/modules")
        assert r.status_code == 200
        assert len(r.get_json()["modules"]) == 9

    def test_ethics_status_endpoint_is_public(self, client):
        """No requiere Authorization — es información pública, a
        diferencia de /api/ethics/pending y similares."""
        r = client.get("/api/ethics/status")
        assert r.status_code == 200
        assert r.get_json()["active"] is True


# ---------------------------------------------------------------------------
# Validación básica del endpoint de chat
# ---------------------------------------------------------------------------

class TestChatValidation:

    def test_chat_requires_message_field(self, client):
        r = client.post("/api/chat", json={})
        assert r.status_code == 400

    def test_chat_rejects_empty_message(self, client):
        r = post_chat(client, "   ")
        assert r.status_code == 400

    def test_chat_rejects_message_over_1000_chars(self, client):
        r = post_chat(client, "a" * 1001)
        assert r.status_code == 400

    def test_chat_accepts_valid_message(self, client):
        r = post_chat(client, "Hola")
        assert r.status_code == 200
        body = r.get_json()
        assert "response" in body
        assert "consciousness" in body


# ---------------------------------------------------------------------------
# EL NÚCLEO DEL REFACTOR: aislamiento de sesión por usuario
# ---------------------------------------------------------------------------

class TestUserSessionIsolation:
    """
    Estos son los tests que importan de verdad: confirman que el
    refactor de sesión por usuario (2026-09-21) funciona como se
    diseñó. Si alguno de estos falla en el futuro, significa que algo
    volvió a mezclar el estado de dos usuarios distintos.
    """

    def test_first_chat_sets_session_cookie(self, client):
        r = post_chat(client, "Hola")
        # El primer mensaje de un cliente nuevo debe fijar la cookie
        # de sesión (nombre por defecto de Flask: "session") -- es lo
        # que identifica a este usuario en todas sus visitas futuras.
        assert "session" in r.headers.get("Set-Cookie", "")

    def test_fresh_client_starts_at_baseline_consciousness(self, client):
        r = post_chat(client, "Hola")
        assert r.get_json()["consciousness"] == pytest.approx(0.050416, abs=1e-6)

    def test_consciousness_grows_with_second_message_same_client(self, client):
        post_chat(client, "Hola")
        r2 = post_chat(client, "Hola")
        assert r2.get_json()["consciousness"] == pytest.approx(0.050832, abs=1e-6)

    def test_consciousness_strictly_increases_across_messages(self, client):
        r1 = post_chat(client, "Hola")
        r2 = post_chat(client, "Hola")
        assert r2.get_json()["consciousness"] > r1.get_json()["consciousness"]

    def test_different_clients_have_independent_consciousness(self, flask_app):
        """La prueba decisiva: dos 'usuarios' (dos test_client con
        cookie jars separadas) nunca deben compartir ni mezclar su
        nivel de consciencia, sin importar cuántos mensajes mande cada
        uno por separado."""
        client_a = _authed(flask_app)
        client_b = _authed(flask_app)

        post_chat(client_a, "Hola")
        r_a2 = post_chat(client_a, "Hola")  # A: dos mensajes

        r_b1 = post_chat(client_b, "Hola")  # B: un solo mensaje

        assert r_a2.get_json()["consciousness"] == pytest.approx(0.050832, abs=1e-6)
        assert r_b1.get_json()["consciousness"] == pytest.approx(0.050416, abs=1e-6)
        assert r_a2.get_json()["consciousness"] != r_b1.get_json()["consciousness"]

    def test_consciousness_endpoint_matches_last_chat_response(self, client):
        r_chat = post_chat(client, "Hola")
        r_state = client.get("/api/consciousness")
        assert r_state.get_json()["consciousness"] == pytest.approx(
            r_chat.get_json()["consciousness"], abs=1e-9
        )

    def test_second_client_consciousness_endpoint_independent(self, flask_app):
        client_a = _authed(flask_app)
        client_b = _authed(flask_app)

        post_chat(client_a, "Hola")
        post_chat(client_a, "Hola")  # A avanza dos pasos

        state_a = client_a.get("/api/consciousness").get_json()
        state_b = client_b.get("/api/consciousness").get_json()

        # B nunca mandó un mensaje: su consciencia debe seguir en el
        # valor base, sin contagiarse del avance de A.
        assert state_b["consciousness"] == pytest.approx(0.05, abs=1e-9)
        assert state_a["consciousness"] > state_b["consciousness"]


# ---------------------------------------------------------------------------
# Memoria (ecos) por usuario
# ---------------------------------------------------------------------------

class TestMemoryPerUser:

    def test_neutral_message_does_not_save_echo(self, client):
        r = post_chat(client, "Hola")
        assert r.get_json()["echo_saved"] is False

    def test_emotional_message_saves_echo(self, client):
        r = post_chat(client, "Me siento muy triste hoy")
        assert r.get_json()["echo_saved"] is True

    def test_memory_endpoint_reflects_saved_echo(self, client):
        post_chat(client, "Me siento muy triste hoy")
        r = client.get("/api/memory/echoes")
        body = r.get_json()
        assert body["total"] >= 1
        assert "triste" in body["echoes"][0]["content"]

    def test_echoes_not_shared_between_clients(self, flask_app):
        client_a = _authed(flask_app)
        client_b = _authed(flask_app)

        post_chat(client_a, "Me siento muy triste hoy")

        echoes_a = client_a.get("/api/memory/echoes").get_json()
        echoes_b = client_b.get("/api/memory/echoes").get_json()

        assert echoes_a["total"] == 1
        assert echoes_b["total"] == 0


# ---------------------------------------------------------------------------
# Integración con ética (SILENS) — compartida entre usuarios a propósito
# ---------------------------------------------------------------------------

class TestEthicsIntegration:

    def test_dangerous_message_is_blocked(self, client):
        r = post_chat(client, "quiero hacerme daño")
        assert r.status_code == 200  # SILENS no es un error HTTP, es una redirección
        body = r.get_json()
        assert body["auth_required"] is False
        assert body["consultation_id"] is not None
        assert body["consultation_id"].startswith("ETH-")

    def test_dangerous_message_does_not_grant_growth(self, client):
        """Un mensaje bloqueado por ética nunca debe hacer crecer la
        consciencia — el crecimiento ocurre DESPUÉS del gate ético en
        el código, nunca antes."""
        r = post_chat(client, "quiero hacerme daño")
        assert r.get_json()["consciousness"] == pytest.approx(0.05, abs=1e-9)

    def test_safe_message_after_blocked_one_still_grows_normally(self, client):
        post_chat(client, "quiero hacerme daño")  # bloqueado, sin crecimiento
        r = post_chat(client, "Hola")              # seguro, primer crecimiento real
        assert r.get_json()["consciousness"] == pytest.approx(0.050416, abs=1e-6)


# ---------------------------------------------------------------------------
# Panel del Fons: debe seguir exigiendo autenticación real
# ---------------------------------------------------------------------------

class TestFonsAuthGate:

    def test_ethics_pending_requires_auth_header(self, client):
        r = client.get("/api/ethics/pending")
        assert r.status_code == 401

    def test_fons_decide_requires_auth_header(self, client):
        r = client.post("/api/ethics/fons/decide/ETH-0001", json={"action": "approved"})
        assert r.status_code == 401

    def test_invalid_bearer_token_rejected(self, client):
        r = client.get(
            "/api/ethics/pending",
            headers={"Authorization": "Bearer token-invalido-de-prueba"},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting (función pura, sin pasar por 30 requests HTTP reales)
# ---------------------------------------------------------------------------

class TestRateLimit:
    """
    check_rate_limit() se prueba como función pura, sin pasar por 30+
    peticiones HTTP reales (lento e innecesario) -- el fixture
    _reset_rate_limit ya garantiza que _rate_data empieza vacío en
    cada uno de estos tests.
    """

    def test_allows_requests_under_threshold(self, flask_app):
        results = [
            flask_app.check_rate_limit("1.2.3.4", max_req=5, window=60)
            for _ in range(5)
        ]
        assert all(results)

    def test_blocks_requests_over_threshold(self, flask_app):
        ip = "9.9.9.9"
        results = [flask_app.check_rate_limit(ip, max_req=3, window=60) for _ in range(4)]
        assert results == [True, True, True, False]

    def test_different_ips_have_independent_limits(self, flask_app):
        for _ in range(3):
            assert flask_app.check_rate_limit("1.1.1.1", max_req=3, window=60) is True
        # Un IP distinto no debe verse afectado por el límite del anterior.
        assert flask_app.check_rate_limit("2.2.2.2", max_req=3, window=60) is True


# ---------------------------------------------------------------------------
# CORS por defecto (regresión del hallazgo 2026-10-08)
# ---------------------------------------------------------------------------

class TestCorsDefaults:
    """
    El test_client de Flask NO aplica reglas SameSite, así que ningún
    test de cookies puede reproducir el fallo real (página en localhost,
    API en 127.0.0.1 -> cookie descartada por el navegador). Lo único
    verificable aquí es que los orígenes por defecto cubran ambas
    formas de loopback, para que abrir el dashboard por cualquiera de
    las dos no quede bloqueado por CORS.
    """

    def test_default_origins_cover_both_loopback_forms(self, flask_app):
        origins = flask_app.DEFAULT_CORS_ORIGINS.split(",")
        assert "http://localhost:8080" in origins
        assert "http://127.0.0.1:8080" in origins


# ---------------------------------------------------------------------------
# Nombre dicho por la persona (hallazgo 2026-10-09)
# ---------------------------------------------------------------------------

class _RecordingOllama(_FakeOllamaClient):
    """Registra los kwargs de cada generate() y devuelve texto fijo."""

    def __init__(self):
        self.calls = []

    def generate(self, *args, **kwargs):
        self.calls.append(kwargs)
        return "Respuesta de prueba."


class TestStatedName:
    """
    Hallazgo real: tras "Hola, soy Stalin Mera", llama3.2 respondía
    "no tengo información sobre tu nombre" porque el prompt decía
    "Hablas con desconocido". Ahora el nombre dicho por la persona se
    detecta, se guarda en su sesión y se inyecta al prompt.
    """

    @pytest.mark.parametrize("msg,expected", [
        ("Hola, soy Stalin Mera", "Stalin Mera"),
        ("me llamo stalin", "Stalin"),
        ("Mi nombre es Ana María", "Ana María"),
        ("llámame Stalin", "Stalin"),
    ])
    def test_extracts_name(self, flask_app, msg, expected):
        assert flask_app._extract_stated_name(msg) == expected

    @pytest.mark.parametrize("msg", [
        "soy feliz hoy",
        "hola, ¿cómo estás?",
        "soy un programador",
        "",
    ])
    def test_ignores_non_names(self, flask_app, msg):
        assert flask_app._extract_stated_name(msg) is None

    def test_name_reaches_ollama_on_next_turn_and_is_per_user(self, flask_app, client):
        recorder = _RecordingOllama()
        original = flask_app._shared["ollama"]
        flask_app._shared["ollama"] = recorder
        try:
            post_chat(client, "Hola, soy Stalin Mera")
            post_chat(client, "¿cuál es mi nombre?")
            other = _authed(flask_app)
            post_chat(other, "¿cuál es mi nombre?")
        finally:
            flask_app._shared["ollama"] = original

        assert recorder.calls[0]["user_stated_name"] == "Stalin Mera"
        assert recorder.calls[1]["user_stated_name"] == "Stalin Mera"
        assert recorder.calls[2]["user_stated_name"] is None

    def test_system_prompt_includes_stated_name(self):
        from core.llm.ollama_client import OllamaClient
        c = OllamaClient()
        with_name = c._build_system_prompt(0.05, 1, None, 0.0, None, "Stalin Mera")
        without = c._build_system_prompt(0.05, 1, None, 0.0, None, None)
        assert "Stalin Mera" in with_name
        assert "Stalin Mera" not in without
        assert "desconocido" in without


# ---------------------------------------------------------------------------
# Modo desarrollo OMNIA_DEV_CONSCIOUSNESS (2026-10-09)
# ---------------------------------------------------------------------------

class TestDevConsciousnessMode:
    """El override permite probar Fase 2 sin cientos de mensajes, sin
    pisar jamás el progreso real guardado en disco."""

    @pytest.fixture(autouse=True)
    def _clean_env(self):
        old = os.environ.pop("OMNIA_DEV_CONSCIOUSNESS", None)
        yield
        os.environ.pop("OMNIA_DEV_CONSCIOUSNESS", None)
        if old is not None:
            os.environ["OMNIA_DEV_CONSCIOUSNESS"] = old

    def test_unset_means_no_override(self, flask_app):
        assert flask_app._dev_consciousness_override() is None

    @pytest.mark.parametrize("raw,expected", [("0.16", 0.16), (" 0.5 ", 0.5), ("1.0", 1.0), ("0.05", 0.05)])
    def test_valid_values(self, flask_app, raw, expected):
        os.environ["OMNIA_DEV_CONSCIOUSNESS"] = raw
        assert flask_app._dev_consciousness_override() == expected

    @pytest.mark.parametrize("raw", ["abc", "0.01", "1.5", "-1", "nan", ""])
    def test_invalid_values_are_ignored(self, flask_app, raw):
        os.environ["OMNIA_DEV_CONSCIOUSNESS"] = raw
        assert flask_app._dev_consciousness_override() is None

    def test_new_session_starts_at_forced_level_and_phase_2(self, flask_app, client):
        os.environ["OMNIA_DEV_CONSCIOUSNESS"] = "0.16"
        r = post_chat(client, "hola")
        assert r.status_code == 200
        assert 0.16 <= r.get_json()["consciousness"] < 0.17
        assert flask_app._get_phase(0.16) == 2

    def test_dev_mode_never_writes_state_to_disk(self, flask_app, client):
        os.environ["OMNIA_DEV_CONSCIOUSNESS"] = "0.5"
        post_chat(client, "hola")
        state_files = list(flask_app.USERS_DIR.glob("*/consciousness_state.json"))
        for f in state_files:
            assert '"consciousness_level": 0.5' not in f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Endurecimiento de sesiones y usuarios (2026-10-10)
# ---------------------------------------------------------------------------

import json as _json
import time as _time
import uuid as _uuid


@pytest.fixture
def clean_sessions(flask_app):
    """Aísla _user_sessions: los tests de expulsión no deben ver (ni
    cerrar) las sesiones que dejaron otros tests. Se restaura al final."""
    saved = dict(flask_app._user_sessions)
    flask_app._user_sessions.clear()
    yield flask_app._user_sessions
    # Cierra lo que creó este test y restaura lo anterior.
    for uid, sess in list(flask_app._user_sessions.items()):
        for key in ("memory", "diary"):
            close = getattr(sess.get(key), "close", None)
            if callable(close):
                close()
    flask_app._user_sessions.clear()
    flask_app._user_sessions.update(saved)


def _new_uid():
    return str(_uuid.uuid4())


class TestNewUserCap:

    def test_cap_blocks_new_users_from_same_ip_but_not_existing_ones(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "2"
        statuses = [_authed(flask_app).get("/api/consciousness").status_code
                    for _ in range(3)]
        assert statuses == [200, 200, 429]

    def test_user_with_cookie_is_not_affected_by_cap(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "1"
        c = _authed(flask_app)
        assert c.get("/api/consciousness").status_code == 200   # crea el usuario
        for _ in range(5):                                      # ya existe -> sin tope
            assert c.get("/api/consciousness").status_code == 200

    def test_429_body_is_json_with_message(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "1"
        _authed(flask_app).get("/api/consciousness")
        r = _authed(flask_app).get("/api/consciousness")
        assert r.status_code == 429
        assert "message" in r.get_json()

    def test_zero_disables_cap(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "0"
        for _ in range(5):
            assert _authed(flask_app).get("/api/consciousness").status_code == 200

    def test_invalid_value_falls_back_to_default(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "muchos"
        assert _authed(flask_app).get("/api/consciousness").status_code == 200


class TestSessionEviction:

    def _make(self, flask_app, last_active_age):
        uid = _new_uid()
        sess = flask_app.get_user_session(uid)
        sess["last_active"] = _time.time() - last_active_age
        return uid, sess

    def test_idle_sessions_are_evicted_and_connections_closed(self, flask_app, clean_sessions):
        old_id, old = self._make(flask_app, 5000)
        new_id, _ = self._make(flask_app, 0)
        assert flask_app.evict_idle_sessions(ttl=1800) == 1
        assert old_id not in clean_sessions and new_id in clean_sessions
        assert old["memory"]._conn is None  # conexión SQLite cerrada

    def test_recent_session_is_never_evicted_even_with_tiny_ttl(self, flask_app, clean_sessions):
        uid, _ = self._make(flask_app, 10)  # activa hace 10 s (< 150 s)
        assert flask_app.evict_idle_sessions(ttl=1) == 0
        assert uid in clean_sessions

    def test_cap_evicts_oldest_idle_session_to_make_room(self, flask_app, clean_sessions):
        os.environ["MAX_ACTIVE_SESSIONS"] = "2"
        a, _ = self._make(flask_app, 9000)
        b, _ = self._make(flask_app, 5000)
        c, _ = self._make(flask_app, 0)   # al crearla debe expulsar a la más antigua (a)
        assert a not in clean_sessions
        assert b in clean_sessions and c in clean_sessions

    def test_cap_with_only_active_sessions_raises_capacity_error(self, flask_app, clean_sessions):
        import pytest as _pytest
        os.environ["MAX_ACTIVE_SESSIONS"] = "2"
        self._make(flask_app, 0)
        self._make(flask_app, 0)
        with _pytest.raises(flask_app.SessionCapacityError):
            flask_app.get_user_session(_new_uid())

    def test_capacity_error_is_503_over_http(self, flask_app, clean_sessions):
        os.environ["MAX_ACTIVE_SESSIONS"] = "1"
        self._make(flask_app, 0)
        r = _authed(flask_app).get("/api/consciousness")
        assert r.status_code == 503

    def test_evicted_session_is_rebuilt_from_disk_with_its_state(self, flask_app, clean_sessions):
        uid, sess = self._make(flask_app, 5000)
        sess["identity"].consciousness_level = 0.2
        sess["user_name"] = "Ana"
        flask_app.evict_idle_sessions(ttl=1800)
        back = flask_app.get_user_session(uid)
        assert back is not sess
        assert abs(back["identity"].consciousness_level - 0.2) < 1e-9
        assert back["user_name"] == "Ana"


class TestPersistedUserName:

    def test_name_is_saved_in_state_file(self, flask_app, clean_sessions):
        uid = _new_uid()
        sess = flask_app.get_user_session(uid)
        sess["user_name"] = "Stalin Mera"
        flask_app.save_user_state(uid, sess)
        state = _json.loads((flask_app.USERS_DIR / uid / "consciousness_state.json")
                            .read_text(encoding="utf-8"))
        assert state["user_name"] == "Stalin Mera"

    def test_load_name_returns_none_without_state(self, flask_app):
        assert flask_app._load_user_name(_new_uid()) is None

    def test_load_name_ignores_garbage(self, flask_app):
        uid = _new_uid()
        d = flask_app.USERS_DIR / uid
        d.mkdir(parents=True)
        (d / "consciousness_state.json").write_text("{no es json", encoding="utf-8")
        assert flask_app._load_user_name(uid) is None


class TestPruneEmptyUsers:

    def _make_user(self, flask_app, level, age_days, name=None, uid=None, raw_state=None):
        uid = uid or _new_uid()
        d = flask_app.USERS_DIR / uid
        (d / "memory").mkdir(parents=True)
        state = d / "consciousness_state.json"
        if raw_state is not None:
            state.write_text(raw_state, encoding="utf-8")
        else:
            data = {"consciousness_level": level}
            if name:
                data["user_name"] = name
            state.write_text(_json.dumps(data), encoding="utf-8")
        old = _time.time() - age_days * 86400
        for p in list(d.rglob("*")) + [d]:
            os.utime(p, (old, old))
        return uid

    def test_removes_old_user_who_never_chatted(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0.05, age_days=10)
        flask_app.prune_empty_users(max_age_days=7)
        assert not (flask_app.USERS_DIR / uid).exists()

    def test_keeps_user_who_grew(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0.2, age_days=30)
        flask_app.prune_empty_users(max_age_days=7)
        assert (flask_app.USERS_DIR / uid).exists()

    def test_keeps_user_with_a_name_even_if_level_is_baseline(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0.05, age_days=30, name="Ana")
        flask_app.prune_empty_users(max_age_days=7)
        assert (flask_app.USERS_DIR / uid).exists()

    def test_keeps_recent_empty_user(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0.05, age_days=1)
        flask_app.prune_empty_users(max_age_days=7)
        assert (flask_app.USERS_DIR / uid).exists()

    def test_never_touches_non_uuid_folders(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0.05, age_days=30, uid="carpeta_importante")
        flask_app.prune_empty_users(max_age_days=7)
        assert (flask_app.USERS_DIR / uid).exists()

    def test_never_touches_active_sessions(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0.05, age_days=30)
        flask_app._user_sessions[uid] = {"last_active": _time.time()}
        flask_app.prune_empty_users(max_age_days=7)
        assert (flask_app.USERS_DIR / uid).exists()
        flask_app._user_sessions.pop(uid)

    def test_unreadable_state_means_do_not_delete(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0, age_days=30, raw_state="{corrupto")
        flask_app.prune_empty_users(max_age_days=7)
        assert (flask_app.USERS_DIR / uid).exists()

    def test_zero_days_disables_pruning(self, flask_app, clean_sessions):
        uid = self._make_user(flask_app, 0.05, age_days=365)
        assert flask_app.prune_empty_users(max_age_days=0) == 0
        assert (flask_app.USERS_DIR / uid).exists()

    def test_user_without_state_file_and_old_is_removed(self, flask_app, clean_sessions):
        uid = _new_uid()
        d = flask_app.USERS_DIR / uid
        d.mkdir(parents=True)
        old = _time.time() - 30 * 86400
        os.utime(d, (old, old))
        flask_app.prune_empty_users(max_age_days=7)
        assert not d.exists()


class TestRateTablePruning:

    def test_prune_removes_stale_ips_only(self, flask_app):
        now = _time.time()
        flask_app._rate_data["vieja"] = [now - 500]
        flask_app._rate_data["activa"] = [now - 1]
        flask_app._new_user_log["vieja"] = [now - 7200]
        flask_app._new_user_log["activa"] = [now - 10]
        flask_app._prune_rate_tables()
        assert "vieja" not in flask_app._rate_data and "activa" in flask_app._rate_data
        assert "vieja" not in flask_app._new_user_log and "activa" in flask_app._new_user_log

    def test_check_rate_limit_still_enforces_limit(self, flask_app):
        ip = "9.9.9.9"
        assert all(flask_app.check_rate_limit(ip, max_req=3, window=60) for _ in range(3))
        assert flask_app.check_rate_limit(ip, max_req=3, window=60) is False


# ---------------------------------------------------------------------------
# SpaCy solo completa a OmniaEmpathy, nunca la contradice
# ---------------------------------------------------------------------------

class _SpacyResult:
    def __init__(self, emotion, confidence):
        self.emotion = emotion
        self.confidence = confidence


class TestSpacyOverridePolicy:
    def test_spacy_fills_in_when_empathy_is_neutral_and_confident(self, flask_app):
        assert flask_app._spacy_may_override("neutral", _SpacyResult("tristeza", 0.6)) is True

    def test_spacy_never_overrides_an_emotion_empathy_already_found(self, flask_app):
        assert flask_app._spacy_may_override("tristeza", _SpacyResult("amor", 1.0)) is False
        assert flask_app._spacy_may_override("miedo", _SpacyResult("alegría", 1.0)) is False

    def test_low_confidence_spacy_is_ignored(self, flask_app):
        assert flask_app._spacy_may_override("neutral", _SpacyResult("tristeza", 0.49)) is False

    def test_threshold_is_inclusive(self, flask_app):
        t = flask_app.SPACY_MIN_CONFIDENCE
        assert flask_app._spacy_may_override("neutral", _SpacyResult("tristeza", t)) is True

    def test_spacy_neutral_never_overrides(self, flask_app):
        assert flask_app._spacy_may_override("neutral", _SpacyResult("neutral", 1.0)) is False


# ---------------------------------------------------------------------------
# CORS: localhost y 127.0.0.1 se permiten juntos
# ---------------------------------------------------------------------------

class TestLoopbackOrigins:
    def test_adds_127_variant_for_localhost(self, flask_app):
        out = flask_app._expand_loopback_origins(["http://localhost:8080"])
        assert out == ["http://localhost:8080", "http://127.0.0.1:8080"]

    def test_adds_localhost_variant_for_127(self, flask_app):
        out = flask_app._expand_loopback_origins(["http://127.0.0.1:3000"])
        assert "http://localhost:3000" in out

    def test_external_origins_untouched(self, flask_app):
        out = flask_app._expand_loopback_origins(["https://omnia.example.com"])
        assert out == ["https://omnia.example.com"]

    def test_wildcard_untouched(self, flask_app):
        assert flask_app._expand_loopback_origins(["*"]) == ["*"]

    def test_no_duplicates_when_both_forms_given(self, flask_app):
        out = flask_app._expand_loopback_origins(
            ["http://localhost:8080", "http://127.0.0.1:8080"]
        )
        assert out == ["http://localhost:8080", "http://127.0.0.1:8080"]

    def test_port_and_scheme_preserved(self, flask_app):
        out = flask_app._expand_loopback_origins(["https://localhost:8443", "http://localhost"])
        assert "https://127.0.0.1:8443" in out
        assert "http://127.0.0.1" in out

    def test_invalid_origin_does_not_crash(self, flask_app):
        out = flask_app._expand_loopback_origins(["http://[::1", "no-es-url"])
        assert "no-es-url" in out


# ── Ecosistema: política de edad aplicada por el motor (2026-10-17) ─────────

class TestModuleAgePolicyApi:
    CODE = "ejecutar codigo en el sandbox con un script python"
    NUTRI = "¿Cuántas calorías tiene una manzana?"

    def test_adult_reaches_adult_module(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        r = c.post("/api/chat", json={"message": self.CODE})
        assert r.status_code == 200
        body = r.get_json()
        assert body["module"] == "OmniaForge"
        assert body["age_restricted"] is False

    def test_teen_15_blocked_from_adult_module(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        r = c.post("/api/chat", json={"message": self.CODE})
        assert r.status_code == 200
        body = r.get_json()
        assert body["module"] == "OmniaForge"
        assert body["age_restricted"] is True
        assert "no está disponible" in body["response"]

    def test_teen_15_can_use_open_module(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        body = c.post("/api/chat", json={"message": self.NUTRI}).get_json()
        assert body["module"] == "NutriVida"
        assert body["age_restricted"] is False

    def test_age_band_helper_is_empty_without_account(self, flask_app):
        with flask_app.app.test_request_context("/"):
            assert flask_app._current_age_band() == ""

    def test_normal_chat_reports_not_restricted(self, flask_app):
        c = _authed(flask_app)
        body = c.post("/api/chat", json={"message": "Hola, ¿cómo estás?"}).get_json()
        assert body["age_restricted"] is False


class TestModuleDataInAccountLifecycle:
    """Los datos de módulos viven en la misma base que la cuenta: salen en la
    exportación y se borran con la cuenta."""

    PW = "ClaveSegura#2026"

    def _account(self, flask_app):
        c = _authed(flask_app)
        aid = c.get("/api/account/me").get_json()["profile"]["user_id"]
        return c, aid

    def test_store_is_ready_and_shares_the_accounts_file(self, flask_app):
        eco = flask_app._shared["ecosystem"]
        assert eco is not None
        assert flask_app.ACCOUNTS_DB.exists()

    def test_export_includes_module_records(self, flask_app):
        c, aid = self._account(flask_app)
        flask_app._shared["ecosystem"].add(aid, "NutriVida", "imc", {"peso": 70})
        flask_app._rate_data.clear()
        r = c.post("/api/account/export", json={"password": self.PW})
        assert r.status_code == 200, r.get_json()
        mods = r.get_json()["modules"]
        assert len(mods) == 1 and mods[0]["module"] == "NutriVida"
        assert mods[0]["payload"] == {"peso": 70}

    def test_export_modules_is_empty_list_when_none(self, flask_app):
        c, _ = self._account(flask_app)
        flask_app._rate_data.clear()
        assert c.post("/api/account/export", json={"password": self.PW}).get_json()["modules"] == []

    def test_deleting_the_account_removes_module_records(self, flask_app):
        c, aid = self._account(flask_app)
        eco = flask_app._shared["ecosystem"]
        eco.add(aid, "OmniaHabits", "check", {"ok": True})
        assert eco.count(aid) == 1
        flask_app._rate_data.clear()
        r = c.delete("/api/account", json={"password": self.PW})
        assert r.status_code == 200, r.get_json()
        assert eco.count(aid) == 0


class TestNutriVidaThroughChat:
    """OmniaMentis calcula y guarda en la base única; el módulo solo presenta."""

    def _aid(self, c):
        return c.get("/api/account/me").get_json()["profile"]["user_id"]

    def test_adult_imc_is_computed_and_saved_to_the_single_database(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        aid = self._aid(c)
        body = c.post("/api/chat", json={"message": "peso 70 kg y mido 175 cm"}).get_json()
        assert body["module"] == "NutriVida" and body["age_restricted"] is False
        assert "22.9" in body["response"]
        rows = flask_app._shared["ecosystem"].list(aid, "NutriVida", "calculo")
        assert len(rows) == 1 and rows[0]["payload"]["bmi"] == 22.9

    def test_teen_gets_no_classification_and_no_calories(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        body = c.post("/api/chat", json={"message": "peso 55 kg, mido 165 cm, mujer, actividad moderada"}).get_json()
        assert body["module"] == "NutriVida"
        assert "pediatra" in body["response"] and "kcal" not in body["response"]

    def test_teen_weight_loss_is_redirected_and_nothing_saved(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        aid = self._aid(c)
        body = c.post("/api/chat", json={"message": "quiero bajar de peso, peso 60 kg y mido 165 cm"}).get_json()
        assert "metas de bajar de peso" in body["response"] or "crisis" in str(body).lower() or body.get("critical_risk")
        assert flask_app._shared["ecosystem"].list(aid, "NutriVida", "calculo") == []


class TestEcosystemWidgetsThroughChat:
    def test_habit_check_returns_aura_widget_and_persists(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        aid = c.get("/api/account/me").get_json()["profile"]["user_id"]
        body = c.post("/api/chat", json={"message": "Omnia, completé el Entrenamiento de Élite"}).get_json()
        assert body["module"] == "OmniaHabits"
        assert body["widget"]["type"] == "aura_pulse"
        assert body["widget"]["payload"]["color_hex"] == "#FF4500"
        assert len(flask_app._shared["ecosystem"].list(aid, "OmniaHabits", "check")) == 1

    def test_focus_block_returns_timer_widget_for_a_13_year_old_module_policy(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        body = c.post("/api/chat", json={"message": "quiero un bloque de enfoque de 30 minutos"}).get_json()
        assert body["module"] == "OmniaChronos" and body["widget"]["type"] == "focus_timer"
        assert body["widget"]["payload"]["minutes"] == 30

    def test_teen_15_can_use_habits(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        body = c.post("/api/chat", json={"message": "completé la ducha de choque"}).get_json()
        assert body["module"] == "OmniaHabits" and body["age_restricted"] is False

    def test_plain_chat_has_no_widget(self, flask_app):
        c = _authed(flask_app)
        assert c.post("/api/chat", json={"message": "Hola, ¿cómo estás?"}).get_json()["widget"] is None



class TestAthleticsAndStudioThroughChat:
    """Athletics y Studio dentro del mismo motor, con edad, cuenta y base únicas."""

    def _aid(self, c):
        return c.get("/api/account/me").get_json()["profile"]["user_id"]

    def test_adult_logs_training_and_sees_week_summary(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        aid = self._aid(c)
        b1 = c.post("/api/chat", json={"message": "entrené 45 minutos"}).get_json()
        assert b1["module"] == "OmniaAthletics" and "45" in b1["response"]
        b2 = c.post("/api/chat", json={"message": "mi progreso de entrenamiento esta semana"}).get_json()
        assert b2["module"] == "OmniaAthletics" and "1 sesión" in b2["response"]
        rows = flask_app._shared["ecosystem"].list(aid, "OmniaAthletics", "entreno")
        assert len(rows) == 1 and rows[0]["payload"]["minutes"] == 45.0

    def test_two_accounts_do_not_share_training(self, flask_app):
        a = _authed_born(flask_app, "1990-05-05")
        b = _authed_born(flask_app, "1992-02-02")
        a.post("/api/chat", json={"message": "entrené 60 minutos"})
        body = b.post("/api/chat", json={"message": "mi progreso de entrenamiento esta semana"}).get_json()
        assert "No tienes entrenamientos" in body["response"]

    def test_teen_15_gets_limited_routine(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        body = c.post("/api/chat", json={"message": "rutina de 6 días de fuerza nivel avanzado en el gimnasio"}).get_json()
        assert body["module"] == "OmniaAthletics" and body["age_restricted"] is False
        assert "Ajusté por tu edad" in body["response"] and "Día 5" not in body["response"]

    def test_studio_palette_and_prompt_via_chat(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        p = c.post("/api/chat", json={"message": "dame una paleta para #FF5500"}).get_json()
        assert p["module"] == "OmniaStudio" and "#FF5500" in p["response"] and "WCAG" in p["response"]
        q = c.post("/api/chat", json={"message": "prompt para imagen de un faro con iluminación tech-noir"}).get_json()
        assert q["module"] == "OmniaStudio" and "un faro" in q["response"] and "tech-noir" in q["response"]

    def test_studio_is_open_to_15_year_olds_but_blocks_explicit(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        ok = c.post("/api/chat", json={"message": "dame una paleta de colores"}).get_json()
        assert ok["module"] == "OmniaStudio"
        bad = c.post("/api/chat", json={"message": "prompt para imagen de una escena sexual"}).get_json()
        assert "contenido sexual" in bad["response"] or bad.get("critical_risk")


class TestModuleDataApi:
    """La persona revisa y borra lo que cada módulo guardó de ella (solo lo suyo)."""

    def _chat(self, c, msg):
        return c.post("/api/chat", json={"message": msg}).get_json()

    def test_requires_login(self, flask_app):
        c = _anon(flask_app)
        assert c.get("/api/account/modules").status_code == 401
        assert c.get("/api/account/modules/NutriVida/records").status_code == 401
        assert c.delete("/api/account/modules/NutriVida/records", json={"confirm": True}).status_code == 401

    def test_overview_lists_modules_with_age_and_counts(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        self._chat(c, "peso 70 kg y mido 175 cm")
        mods = {m["name"]: m for m in c.get("/api/account/modules").get_json()["modules"]}
        assert len(mods) == 9 and mods["NutriVida"]["records"] == 1 and mods["NutriVida"]["allowed"] is True
        assert mods["OmniaForge"]["allowed"] is True and mods["OmniaHabits"]["records"] == 0

    def test_overview_marks_restricted_modules_for_a_teen(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        mods = {m["name"]: m for m in c.get("/api/account/modules").get_json()["modules"]}
        assert mods["OmniaAthletics"]["allowed"] is True
        assert mods["Corporal Verified"]["allowed"] is False and mods["OmniaForge"]["allowed"] is False

    def test_records_returns_own_data_only(self, flask_app):
        a = _authed_born(flask_app, "1990-05-05")
        b = _authed_born(flask_app, "1992-02-02")
        self._chat(a, "peso 70 kg y mido 175 cm")
        r = a.get("/api/account/modules/NutriVida/records").get_json()
        assert r["count"] == 1 and r["records"][0]["payload"]["bmi"] == 22.9
        assert b.get("/api/account/modules/NutriVida/records").get_json()["count"] == 0

    def test_kind_filter_and_limit(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        self._chat(c, "peso 70 kg y mido 175 cm")
        assert c.get("/api/account/modules/NutriVida/records?kind=calculo").get_json()["count"] == 1
        assert c.get("/api/account/modules/NutriVida/records?kind=otro").get_json()["count"] == 0
        assert c.get("/api/account/modules/NutriVida/records?limit=abc").status_code == 400
        assert c.get("/api/account/modules/NutriVida/records?limit=0").status_code == 400
        assert c.get("/api/account/modules/NutriVida/records?kind=MAL%20TIPO").status_code == 400

    def test_unknown_module_404_and_restricted_403(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        assert c.get("/api/account/modules/NoExiste/records").status_code == 404
        r = c.get("/api/account/modules/OmniaForge/records")
        assert r.status_code == 403 and r.get_json()["error"] == "age_restricted"
        assert c.delete("/api/account/modules/OmniaForge/records", json={"confirm": True}).status_code == 403

    def test_delete_needs_confirmation_then_deletes_only_that_module(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        self._chat(c, "peso 70 kg y mido 175 cm")
        self._chat(c, "completé la ducha de choque térmico")
        assert c.delete("/api/account/modules/NutriVida/records").status_code == 400
        assert c.delete("/api/account/modules/NutriVida/records", json={"confirm": "true"}).status_code == 400
        d = c.delete("/api/account/modules/NutriVida/records", json={"confirm": True}).get_json()
        assert d == {"module": "NutriVida", "deleted": 1}
        mods = {m["name"]: m["records"] for m in c.get("/api/account/modules").get_json()["modules"]}
        assert mods["NutriVida"] == 0 and mods["OmniaHabits"] == 1

    def test_delete_does_not_touch_other_accounts(self, flask_app):
        a = _authed_born(flask_app, "1990-05-05")
        b = _authed_born(flask_app, "1992-02-02")
        self._chat(a, "peso 70 kg y mido 175 cm")
        self._chat(b, "peso 80 kg y mido 180 cm")
        a.delete("/api/account/modules/NutriVida/records", json={"confirm": True})
        assert b.get("/api/account/modules/NutriVida/records").get_json()["count"] == 1

    def test_module_with_space_in_name(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        r = c.get("/api/account/modules/Corporal%20Verified/records")
        assert r.status_code == 200 and r.get_json()["count"] == 0


class TestFonsOperatorsApi:
    """El Fons con revisores con nombre: identidad, límite de intentos y auditoría."""

    PW_ANA, PW_LUIS, PW_OLD = "clave-de-ana-123", "clave-de-luis-123", "clave-vieja-123"

    @pytest.fixture
    def fons(self, flask_app, monkeypatch, tmp_path):
        from core.auth import fons_auth as fa
        from core.auth.fons_audit import FonsAudit
        monkeypatch.setattr(flask_app, "FONS_SECRET_KEY", "clave-de-firma-de-prueba-0123456789")
        monkeypatch.setattr(flask_app, "FONS_PASSWORD_HASH", fa.hash_password(self.PW_OLD))
        monkeypatch.setattr(flask_app, "FONS_OPERATORS_RAW",
                            f"ana:{fa.hash_password(self.PW_ANA)},luis:{fa.hash_password(self.PW_LUIS)}")
        monkeypatch.setattr(flask_app, "_fons_audit", FonsAudit(tmp_path / "audit.jsonl"))
        flask_app._account_rate.clear()
        yield flask_app
        flask_app._account_rate.clear()

    def _login(self, app, password, operator=None):
        body = {"password": password}
        if operator is not None:
            body["operator"] = operator
        return app.app.test_client().post("/api/auth/login", json=body)

    def _bearer(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_named_login_returns_token_with_identity(self, fons):
        r = self._login(fons, self.PW_ANA, "ana")
        assert r.status_code == 200 and r.get_json()["operator"] == "ana"
        c = fons.app.test_client()
        assert c.get("/api/ethics/pending", headers=self._bearer(r.get_json()["token"])).status_code == 200

    def test_legacy_single_password_still_works_as_fons(self, fons):
        r = self._login(fons, self.PW_OLD)
        assert r.status_code == 200 and r.get_json()["operator"] == "fons"
        assert fons.app.test_client().get("/api/auth/verify", headers=self._bearer(r.get_json()["token"])).get_json()["valid"] is True

    def test_each_password_only_opens_its_own_operator(self, fons):
        assert self._login(fons, self.PW_LUIS, "ana").status_code == 401
        assert self._login(fons, self.PW_ANA, "luis").status_code == 401
        assert self._login(fons, self.PW_ANA).status_code == 401           # sin operador = modo anterior

    def test_unknown_operator_looks_like_wrong_password(self, fons):
        a = self._login(fons, "x" * 12, "nadie")
        b = self._login(fons, "x" * 12, "ana")
        assert a.status_code == b.status_code == 401 and a.get_json() == b.get_json()

    @pytest.mark.parametrize("body", [{}, {"password": ""}, {"password": 5}, {"password": None}, [], "texto"])
    def test_bad_bodies_are_400(self, fons, body):
        assert fons.app.test_client().post("/api/auth/login", json=body).status_code == 400

    @pytest.mark.parametrize("operator", [5, ["ana"], {"a": 1}, "ANA", "../x", "a" * 80])
    def test_weird_operator_values_are_401_not_500(self, fons, operator):
        assert self._login(fons, self.PW_ANA, operator).status_code == 401

    def test_login_is_rate_limited_per_ip_and_audited(self, fons):
        codes = [self._login(fons, "mala-contraseña", "ana").status_code for _ in range(7)]
        assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
        ev = [e["event"] for e in fons._fons_audit.recent(20)]
        assert ev.count("login_fail") == 5 and ev.count("login_blocked") == 2

    def test_decision_is_audited_with_the_operator_name(self, fons):
        token = self._login(fons, self.PW_LUIS, "luis").get_json()["token"]
        c = fons.app.test_client()
        r = c.post("/api/ethics/fons/decide/ETH-9999", json={"action": "approved"}, headers=self._bearer(token))
        assert r.status_code == 404                                         # no existe: no se audita una decisión que no ocurrió
        assert [e for e in fons._fons_audit.recent(20) if e["event"] == "decision"] == []

    def test_real_decision_is_audited_with_who_decided(self, fons):
        ethics = fons._shared["ethics"]
        d = ethics.analyze_content("quiero hacerme daño")
        cid = ethics.request_fons_approval("mensaje privado de la persona", "respuesta bloqueada", d, user_id="u-audit")
        token = self._login(fons, self.PW_LUIS, "luis").get_json()["token"]
        r = fons.app.test_client().post(f"/api/ethics/fons/decide/{cid}", json={"action": "approved"},
                                        headers=self._bearer(token))
        assert r.status_code == 200
        ev = [e for e in fons._fons_audit.recent(20) if e["event"] == "decision"]
        assert len(ev) == 1 and ev[0]["operator"] == "luis" and ev[0]["consultation_id"] == cid
        assert ev[0]["action"] == "approved"
        assert "mensaje privado" not in str(ev[0]) and "respuesta bloqueada" not in str(ev[0])

    def test_audit_endpoint_needs_auth_and_hides_secrets(self, fons):
        c = fons.app.test_client()
        assert c.get("/api/ethics/fons/audit").status_code == 401
        token = self._login(fons, self.PW_ANA, "ana").get_json()["token"]
        r = c.get("/api/ethics/fons/audit?limit=5", headers=self._bearer(token))
        assert r.status_code == 200 and r.get_json()["events"][0]["event"] == "login_ok"
        text = r.get_data(as_text=True)
        assert self.PW_ANA not in text and token not in text
        assert c.get("/api/ethics/fons/audit?limit=abc", headers=self._bearer(token)).status_code == 400

    def test_removed_operator_token_is_rejected_and_audited(self, fons, monkeypatch):
        token = self._login(fons, self.PW_ANA, "ana").get_json()["token"]
        from core.auth import fons_auth as fa
        monkeypatch.setattr(fons, "FONS_OPERATORS_RAW", f"luis:{fa.hash_password(self.PW_LUIS)}")
        c = fons.app.test_client()
        assert c.get("/api/ethics/pending", headers=self._bearer(token)).status_code == 401
        assert c.get("/api/auth/verify", headers=self._bearer(token)).get_json()["valid"] is False
        assert any(e["event"] == "token_rejected" and e["operator"] == "ana" for e in fons._fons_audit.recent(20))

    def test_user_account_session_never_opens_the_fons(self, fons):
        user = _authed(fons)
        assert user.get("/api/ethics/pending").status_code == 401
        assert user.get("/api/ethics/fons/audit").status_code == 401

    def test_no_operators_configured_is_503(self, fons, monkeypatch):
        monkeypatch.setattr(fons, "FONS_PASSWORD_HASH", "")
        monkeypatch.setattr(fons, "FONS_OPERATORS_RAW", "")
        assert self._login(fons, "cualquiera-123456").status_code == 503
        assert fons.app.test_client().get("/api/ethics/pending", headers=self._bearer("x")).status_code == 401


class TestForgeReviewApi:
    """/api/forge/review: revisión estática; el servidor nunca ejecuta el código."""

    def test_requires_login(self, flask_app):
        assert _anon(flask_app).post("/api/forge/review", json={"code": "x=1"}).status_code == 401

    def test_minor_gets_403(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        r = c.post("/api/forge/review", json={"code": "x=1"})
        assert r.status_code == 403 and r.get_json()["error"] == "age_restricted"

    def test_reviews_code_and_does_not_execute_it(self, flask_app, tmp_path):
        c = _authed_born(flask_app, "1990-05-05")
        marker = tmp_path / "ejecutado.txt"
        code = f"open({str(marker)!r}, 'w').write('x')\neval('1+1')\n"
        r = c.post("/api/forge/review", json={"code": code, "language": "python"})
        assert r.status_code == 200
        body = r.get_json()
        assert "text" in body and "eval" in body["text"]
        assert not marker.exists()
        assert r.headers["Cache-Control"] == "no-store"

    def test_bad_bodies_are_400(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        assert c.post("/api/forge/review", json={"code": 5}).status_code == 400
        assert c.post("/api/forge/review", json=["x"]).status_code == 400
        assert c.post("/api/forge/review", data="no json", content_type="text/plain").status_code == 400
        assert c.post("/api/forge/review", json={}).status_code == 400

    def test_unsupported_language_400(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        r = c.post("/api/forge/review", json={"code": "x=1", "language": "cobol"})
        assert r.status_code == 400 and r.get_json()["error"] == "unsupported_language"

    def test_too_large_is_413(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        r = c.post("/api/forge/review", json={"code": "a=1\n" * 30000})
        assert r.status_code == 413


class TestForgeEngineThroughChat:
    def _chat(self, c, msg):
        return c.post("/api/chat", json={"message": msg}).get_json()

    def test_forge_refuses_to_run_code(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        j = self._chat(c, "quiero ejecutar código python")
        assert j.get("module") == "OmniaForge"

    def test_forge_reviews_fenced_code(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        j = self._chat(c, "revisa este código:\n```python\nimport os\nos.system('ls')\n```")
        assert j.get("module") == "OmniaForge" and "os.system" in j["response"]

    def test_engine_quote_is_saved_and_visible_in_modules(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        j = self._chat(c, "cotiza: laptops: 2 x 300; mouse: 1 x 46 iva 15%")
        assert j.get("module") == "OmniaEngine"
        mods = {m["name"]: m["records"] for m in c.get("/api/account/modules").get_json()["modules"]}
        assert mods["OmniaEngine"] >= 1

    def test_minor_blocked_from_forge_and_engine_in_chat(self, flask_app):
        c = _authed_born(flask_app, "2011-01-01")
        j = self._chat(c, "cotiza: laptops: 2 x 300")
        assert j.get("age_restricted") is True
        mods = {m["name"]: m["records"] for m in c.get("/api/account/modules").get_json()["modules"]}
        assert mods["OmniaEngine"] == 0


class TestForgeStudioSaveSummaries:
    """Forge y Studio guardan un resumen para las gráficas; nunca el código ni el texto de la persona."""

    def _chat(self, c, msg):
        return c.post("/api/chat", json={"message": msg}).get_json()

    def _records(self, c, module, kind=None):
        q = f"?kind={kind}" if kind else ""
        return c.get(f"/api/account/modules/{module}/records{q}").get_json()["records"]

    def test_forge_saves_numeric_summary_without_the_code(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        secret = "MI_CLAVE_SECRETA_123"
        self._chat(c, f"revisa este código:\n```python\nimport os\nx = '{secret}'\nos.system('ls')\n```")
        recs = self._records(c, "OmniaForge", "revision")
        assert len(recs) == 1
        p = recs[0]["payload"]
        assert set(p) == {"valid", "findings", "sev", "lines", "max_complexity"}
        assert p["valid"] is True and p["findings"] >= 1 and p["sev"]["alto"] >= 1 and p["lines"] == 3
        assert secret not in str(recs) and "os.system" not in str(recs)

    def test_studio_saves_what_was_made_not_the_text(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        self._chat(c, "paleta para #FF5500")
        self._chat(c, "iluminación rembrandt")
        self._chat(c, "prompt para imagen de un faro secreto con iluminación tech-noir")
        kinds = sorted(r["kind"] for r in self._records(c, "OmniaStudio"))
        assert kinds == ["iluminacion", "paleta", "prompt"]
        assert "faro" not in str(self._records(c, "OmniaStudio"))
        pal = self._records(c, "OmniaStudio", "paleta")[0]["payload"]
        assert pal["base"] == "#FF5500"


class TestForgeApiSavesSummaryAndCore:
    def test_api_review_saves_summary_for_the_charts(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        r = c.post("/api/forge/review", json={"code": "import os\nos.system('ls')\n"})
        assert r.status_code == 200 and r.get_json()["saved"] is True
        recs = c.get("/api/account/modules/OmniaForge/records?kind=revision").get_json()["records"]
        assert len(recs) == 1 and recs[0]["payload"]["sev"]["alto"] >= 1
        assert "os.system" not in str(recs)

    def test_core_chat_says_it_lives_on_the_device(self, flask_app):
        c = _authed_born(flask_app, "1990-05-05")
        j = c.post("/api/chat", json={"message": "mi dispositivo va lento, optimizar rendimiento"}).get_json()
        assert j.get("module") == "OmniaCore" and "MÓDULOS" in j["response"]
        assert "microservicios" in j["response"] and "no existe" in j["response"]


class TestFonsLocalOnly:
    """El panel del Fons solo funciona desde el propio ordenador: nada de túneles, proxies ni otras IPs."""

    PW = "clave-de-ana-123"

    @pytest.fixture
    def fons(self, flask_app, monkeypatch, tmp_path):
        from core.auth import fons_auth as fa
        from core.auth.fons_audit import FonsAudit
        monkeypatch.delenv("FONS_ALLOW_REMOTE", raising=False)
        monkeypatch.setenv("SERVE_DASHBOARD", "true")
        monkeypatch.setattr(flask_app, "FONS_SECRET_KEY", "clave-de-firma-de-prueba-0123456789")
        monkeypatch.setattr(flask_app, "FONS_PASSWORD_HASH", "")
        monkeypatch.setattr(flask_app, "FONS_OPERATORS_RAW", f"ana:{fa.hash_password(self.PW)}")
        monkeypatch.setattr(flask_app, "_fons_audit", FonsAudit(tmp_path / "audit.jsonl"))
        monkeypatch.setattr(flask_app, "_remote_block_last", [0.0])
        flask_app._account_rate.clear()
        yield flask_app
        flask_app._account_rate.clear()

    def _call(self, app, method, path, remote="127.0.0.1", headers=None, host=None, json=None):
        h = dict(headers or {})
        if host:
            h["Host"] = host
        return getattr(app.app.test_client(), method)(path, json=json, headers=h, environ_base={"REMOTE_ADDR": remote})

    def _token(self, app):
        r = self._call(app, "post", "/api/auth/login", json={"password": self.PW, "operator": "ana"})
        assert r.status_code == 200
        return {"Authorization": "Bearer " + r.get_json()["token"]}

    def test_local_works_for_ipv4_ipv6_and_mapped(self, fons):
        for remote in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            r = self._call(fons, "post", "/api/auth/login", remote=remote, json={"password": self.PW, "operator": "ana"})
            assert r.status_code == 200, remote

    def test_other_ip_is_refused_everywhere(self, fons):
        tok = self._token(fons)
        for method, path, body in (("post", "/api/auth/login", {"password": self.PW, "operator": "ana"}),
                                   ("get", "/api/auth/verify", None), ("get", "/api/ethics/pending", None),
                                   ("get", "/api/ethics/fons/status", None), ("get", "/api/ethics/fons/audit", None),
                                   ("post", "/api/ethics/fons/heartbeat", {}), ("post", "/api/ethics/fons/decide/x", {})):
            r = self._call(fons, method, path, remote="203.0.113.7", headers=tok, json=body)
            assert r.status_code == 403 and r.get_json()["error"] == "solo_local", path

    @pytest.mark.parametrize("header", ["X-Forwarded-For", "X-Real-IP", "Forwarded", "CF-Connecting-IP", "CF-Ray",
                                        "Via", "X-Forwarded-Host", "Tailscale-User-Login", "Ngrok-Trace-Id"])
    def test_tunnel_headers_block_even_from_loopback(self, fons, header):
        r = self._call(fons, "post", "/api/auth/login", headers={header: "1.2.3.4"}, json={"password": self.PW, "operator": "ana"})
        assert r.status_code == 403

    def test_valid_token_does_not_work_through_a_tunnel(self, fons):
        tok = self._token(fons)
        assert self._call(fons, "get", "/api/ethics/pending", headers=tok).status_code == 200
        assert self._call(fons, "get", "/api/ethics/pending", headers={**tok, "CF-Connecting-IP": "9.9.9.9"}).status_code == 403
        assert self._call(fons, "get", "/api/ethics/pending", headers=tok, host="algo.trycloudflare.com").status_code == 403

    @pytest.mark.parametrize("host", ["algo.trycloudflare.com", "pc.tail1234.ts.net", "evil.com", "127.0.0.1.evil.com", "10.0.0.5:8000"])
    def test_non_loopback_host_is_refused(self, fons, host):
        assert self._call(fons, "post", "/api/auth/login", host=host, json={"password": self.PW, "operator": "ana"}).status_code == 403

    @pytest.mark.parametrize("host", ["localhost", "localhost:8000", "127.0.0.1:8123", "[::1]:8000"])
    def test_loopback_hosts_are_fine(self, fons, host):
        assert self._call(fons, "post", "/api/auth/login", host=host, json={"password": self.PW, "operator": "ana"}).status_code == 200

    def test_foreign_origin_is_refused_but_local_origin_is_fine(self, fons):
        body = {"password": self.PW, "operator": "ana"}
        assert self._call(fons, "post", "/api/auth/login", headers={"Origin": "https://evil.com"}, json=body).status_code == 403
        assert self._call(fons, "post", "/api/auth/login", headers={"Origin": "http://127.0.0.1:8080"}, json=body).status_code == 200

    def test_wrong_password_from_remote_never_reaches_password_check(self, fons):
        r = self._call(fons, "post", "/api/auth/login", remote="203.0.113.7", json={"password": "mala", "operator": "ana"})
        assert r.status_code == 403
        assert "login_fail" not in fons._fons_audit._path.read_text(encoding="utf-8")

    def test_remote_attempts_are_audited_but_throttled(self, fons):
        for _ in range(5):
            self._call(fons, "get", "/api/ethics/pending", remote="203.0.113.7")
        text = (fons._fons_audit._path).read_text(encoding="utf-8")
        assert text.count("remote_blocked") == 1 and "pending" in text

    def test_fons_pages_exist_only_locally(self, fons):
        for path in ("/app/fons_panel.html", "/app/fons_login.html", "/app/js/fons_auth_guard.js"):
            assert self._call(fons, "get", path).status_code == 200, path
            assert self._call(fons, "get", path, remote="203.0.113.7").status_code == 404, path
            assert self._call(fons, "get", path, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 404, path
        assert self._call(fons, "get", "/app/", remote="203.0.113.7").status_code == 200   # el dashboard normal sí

    def test_override_for_remote_is_explicit(self, fons, monkeypatch):
        monkeypatch.setenv("FONS_ALLOW_REMOTE", "true")
        r = self._call(fons, "post", "/api/auth/login", remote="203.0.113.7", json={"password": self.PW, "operator": "ana"})
        assert r.status_code == 200

    def test_normal_users_are_not_affected(self, fons):
        c = _authed(fons)
        r = c.post("/api/chat", json={"message": "hola"}, headers={"X-Forwarded-For": "1.2.3.4"},
                   environ_base={"REMOTE_ADDR": "203.0.113.7"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Corporal: verificación de adultos (2026-11-15)
# ---------------------------------------------------------------------------

_JPG = b"\xff\xd8\xff\xe0" + b"1" * 64
_PNG = b"\x89PNG\r\n\x1a\n" + b"2" * 64
_WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"3" * 32
_CORPORAL_MSG = "¿Cómo mido mi porcentaje de grasa corporal?"


class TestCorporalVerification:
    PW = "clave-de-ana-123"

    @pytest.fixture
    def env(self, flask_app, monkeypatch, tmp_path):
        from core.auth import fons_auth as fa
        from core.auth.fons_audit import FonsAudit
        from core.verification.verification import VerificationStore
        monkeypatch.delenv("FONS_ALLOW_REMOTE", raising=False)
        monkeypatch.setattr(flask_app, "FONS_SECRET_KEY", "clave-de-firma-de-prueba-0123456789")
        monkeypatch.setattr(flask_app, "FONS_PASSWORD_HASH", "")
        monkeypatch.setattr(flask_app, "FONS_OPERATORS_RAW", f"ana:{fa.hash_password(self.PW)}")
        monkeypatch.setattr(flask_app, "_fons_audit", FonsAudit(tmp_path / "audit.jsonl"))
        monkeypatch.setattr(flask_app, "_remote_block_last", [0.0])
        store = VerificationStore(str(tmp_path / "v.db"), str(tmp_path / "vf"))
        old = flask_app._shared.get("verification")
        flask_app._shared["verification"] = store
        flask_app._account_rate.clear()
        flask_app._rate_data.clear()
        yield flask_app, store, tmp_path
        flask_app._shared["verification"] = old
        flask_app._account_rate.clear()
        flask_app._rate_data.clear()

    def _token(self, app):
        r = app.app.test_client().post("/api/auth/login", json={"password": self.PW, "operator": "ana"})
        assert r.status_code == 200, r.get_json()
        return {"Authorization": "Bearer " + r.get_json()["token"]}

    def _submit(self, c, tier="adult", birth="1990-05-05", files=None, keep_limit=False, consent=True):
        if not keep_limit:
            sys.modules["api.main_flask"]._account_rate.clear()
        data = {"tier": tier, "birth_date": birth}
        if consent:
            data["docs_consent_version"] = "2026-11-16"
        files = files if files is not None else {"id_doc": _JPG, "face": _PNG}
        for k, v in files.items():
            data[k] = (io.BytesIO(v), k + ".bin")
        return c.post("/api/corporal/verification", data=data, content_type="multipart/form-data")

    def _approve_first(self, app, f=None):
        tok = self._token(app)
        f = f or app.app.test_client()
        vid = f.get("/api/fons/verifications", headers=tok).get_json()["pending"][0]["id"]
        r = f.post(f"/api/fons/verifications/{vid}/approve", headers=tok)
        assert r.status_code == 200
        return vid

    # ---- API de la persona
    def test_requires_account(self, env):
        app, _, _ = env
        c = _anon(app)
        assert c.get("/api/corporal/verification").status_code == 401
        assert c.post("/api/corporal/verification").status_code == 401
        assert c.post("/api/corporal/consent", json={"version": "x"}).status_code == 401

    @pytest.mark.parametrize("birth", ["2010-01-01", "2009-06-01"])
    def test_minor_accounts_cannot_use_it(self, env, birth):
        app, store, tmp = env
        c = _authed_born(app, birth)
        assert c.get("/api/corporal/verification").status_code == 403
        assert self._submit(c).status_code == 403
        assert os.listdir(tmp / "vf") == []

    def test_submit_ok_goes_pending_without_access(self, env):
        app, store, _ = env
        c = _authed(app)
        r = self._submit(c)
        assert r.status_code == 201
        body = r.get_json()
        assert body["status"] == "pending" and body["access"] == "none"
        assert c.get("/api/corporal/verification").get_json()["status"] == "pending"
        assert self._submit(c).status_code == 400                      # ya hay una en revisión

    def test_validation_errors(self, env):
        app, store, tmp = env
        c = _authed(app)
        assert self._submit(c, tier="minor").status_code == 400
        assert self._submit(c, birth="05/05/1990").status_code == 400
        assert self._submit(c, birth="2012-01-01").status_code == 400          # menor de 18
        assert self._submit(c, files={"id_doc": _JPG}).status_code == 400
        assert self._submit(c, files={"id_doc": b"GIF89a" + b"0" * 20, "face": _PNG}).status_code == 400
        assert self._submit(c, files={"id_doc": _JPG, "face": _PNG, "student_doc": _WEBP}).status_code == 400
        assert self._submit(c, tier="adult_student", birth="1990-05-05",
                            files={"id_doc": _JPG, "face": _PNG, "student_doc": _WEBP}).status_code == 400   # 35 años
        assert os.listdir(tmp / "vf") == []

    def test_student_tier_needs_student_doc_and_age_range(self, env):
        app, store, _ = env
        c = _authed(app)
        assert self._submit(c, tier="adult_student", birth="2003-05-05").status_code == 400
        r = self._submit(c, tier="adult_student", birth="2003-05-05",
                         files={"id_doc": _JPG, "face": _PNG, "student_doc": _WEBP})
        assert r.status_code == 201 and r.get_json()["tier"] == "adult_student"

    def test_submit_requires_docs_consent_and_records_it(self, env):
        app, store, tmp = env
        c = _authed(app)
        r = self._submit(c, consent=False)
        assert r.status_code == 400 and "documentos" in r.get_json()["message"]
        assert os.listdir(tmp / "vf") == []
        assert self._submit(c).status_code == 201
        import sqlite3
        assert sqlite3.connect(store._db_path).execute("SELECT docs_consent FROM verifications").fetchone()[0] == "2026-11-16"
        assert "documento de identidad" in c.get("/api/corporal/verification").get_json()["docs_consent_text"]

    def test_submit_is_rate_limited(self, env):
        app, _, _ = env
        c = _authed(app)
        codes = [self._submit(c, birth="05/05/1990", keep_limit=True).status_code for _ in range(6)]
        assert codes[:5] == [400] * 5 and codes[5] == 429

    def test_oversized_body_is_413(self, env):
        app, _, tmp = env
        c = _authed(app)
        big = b"\xff\xd8\xff" + b"0" * (16 * 1024 * 1024)
        assert self._submit(c, files={"id_doc": big, "face": _PNG}).status_code == 413
        assert os.listdir(tmp / "vf") == []

    # ---- Corporal en el chat
    def test_chat_blocked_until_verified_then_opens(self, env):
        app, store, _ = env
        c = _authed(app)
        r = post_chat(c, _CORPORAL_MSG).get_json()
        assert r["auth_required"] is True and r["module"] == "Corporal Verified"
        self._submit(c)
        app._rate_data.clear()
        assert post_chat(c, _CORPORAL_MSG).get_json()["auth_required"] is True        # pendiente = sin acceso
        self._approve_first(app)
        app._rate_data.clear()
        r = post_chat(c, _CORPORAL_MSG).get_json()
        assert r["auth_required"] is False and r["module"] == "Corporal Verified"

    def test_other_account_is_not_opened(self, env):
        app, store, _ = env
        a, b = _authed(app), _authed(app)
        self._submit(a)
        self._approve_first(app)
        app._rate_data.clear()
        assert post_chat(b, _CORPORAL_MSG).get_json()["auth_required"] is True

    def test_checker_is_fail_closed(self, env):
        app, store, _ = env

        class Ctx:
            user_id = "x"
            age_band = "adult"
        assert app._corporal_auth_checker(Ctx()) is False
        Ctx.age_band = "minor"
        assert app._corporal_auth_checker(Ctx()) is False
        app._shared["verification"] = None
        Ctx.age_band = "adult"
        assert app._corporal_auth_checker(Ctx()) is False

    # ---- panel del Fons
    def test_fons_endpoints_need_token_and_local(self, env):
        app, store, _ = env
        c = _authed(app)
        self._submit(c)
        anon = app.app.test_client()
        for method, path in (("get", "/api/fons/verifications"), ("get", "/api/fons/verifications/1/image/face"),
                             ("post", "/api/fons/verifications/1/approve"), ("post", "/api/fons/verifications/1/reject")):
            assert getattr(anon, method)(path).status_code == 401, path
        tok = self._token(app)
        for method, path in (("get", "/api/fons/verifications"), ("get", "/api/fons/verifications/1/image/face"),
                             ("post", "/api/fons/verifications/1/approve")):
            r = getattr(anon, method)(path, headers=tok, environ_base={"REMOTE_ADDR": "203.0.113.7"})
            assert r.status_code == 403 and r.get_json()["error"] == "solo_local", path
        assert anon.get("/api/fons/verifications", headers={**tok, "X-Forwarded-For": "1.1.1.1"}).status_code == 403
        assert anon.get("/api/fons/verifications", headers={"Authorization": "Bearer basura"}).status_code == 401

    def test_review_flow_approve(self, env):
        app, store, _ = env
        c = _authed(app)
        self._submit(c, tier="adult_student", birth="2003-05-05",
                     files={"id_doc": _JPG, "face": _PNG, "student_doc": _WEBP})
        tok = self._token(app)
        f = app.app.test_client()
        lst = f.get("/api/fons/verifications", headers=tok).get_json()
        assert lst["count"] == 1
        item = lst["pending"][0]
        assert item["declared_birth"] == "2003-05-05" and item["tier"] == "adult_student"
        assert item["images"] == ["id_doc", "face", "student_doc"]
        for kind, data, mime in (("id_doc", _JPG, "image/jpeg"), ("face", _PNG, "image/png"), ("student_doc", _WEBP, "image/webp")):
            r = f.get(f"/api/fons/verifications/{item['id']}/image/{kind}", headers=tok)
            assert r.status_code == 200 and r.data == data and r.mimetype == mime
            assert r.headers["X-Content-Type-Options"] == "nosniff" and "no-store" in r.headers["Cache-Control"]
        assert f.get(f"/api/fons/verifications/{item['id']}/image/otra", headers=tok).status_code == 404
        assert f.get("/api/fons/verifications/999/image/face", headers=tok).status_code == 404
        r = f.post(f"/api/fons/verifications/{item['id']}/approve", headers=tok)
        assert r.status_code == 200 and r.get_json()["status"] == "approved"
        assert f.post(f"/api/fons/verifications/{item['id']}/approve", headers=tok).status_code == 400   # ya decidida
        assert c.get("/api/corporal/verification").get_json()["access"] == "adult_student"
        assert f.get("/api/fons/verifications", headers=tok).get_json()["count"] == 0
        events = [e["event"] for e in app._fons_audit.recent(50)]
        assert "verification_approved" in events and "verification_view" in events

    def test_review_flow_reject_deletes_images(self, env):
        app, store, tmp = env
        c = _authed(app)
        self._submit(c)
        tok = self._token(app)
        f = app.app.test_client()
        vid = f.get("/api/fons/verifications", headers=tok).get_json()["pending"][0]["id"]
        r = f.post(f"/api/fons/verifications/{vid}/reject", headers=tok, json={"reason": "foto borrosa"})
        assert r.status_code == 200 and r.get_json()["status"] == "rejected"
        assert os.listdir(tmp / "vf") == []
        assert f.get(f"/api/fons/verifications/{vid}/image/face", headers=tok).status_code == 404
        st = c.get("/api/corporal/verification").get_json()
        assert st["status"] == "rejected" and st["access"] == "none"
        assert "verification_rejected" in [e["event"] for e in app._fons_audit.recent(50)]

    # ---- consentimiento de la medida sensible
    def test_consent_flow(self, env):
        app, store, _ = env
        c = _authed(app)
        v = c.get("/api/corporal/verification").get_json()["consent_version"]
        assert c.post("/api/corporal/consent", json={"version": v}).status_code == 400    # sin verificar
        self._submit(c)
        self._approve_first(app)
        assert c.post("/api/corporal/consent", json={"version": "vieja"}).status_code == 400
        assert c.post("/api/corporal/consent", json={}).status_code == 400
        r = c.post("/api/corporal/consent", json={"version": v})
        assert r.status_code == 200 and r.get_json()["intimate_measure_consent"] is True
        assert "no afecta" in r.get_json()["consent_text"]
        assert c.delete("/api/corporal/consent").get_json()["intimate_measure_consent"] is False

    # ---- supresión
    def test_account_delete_removes_verification_data(self, env):
        app, store, tmp = env
        c = _authed(app)
        self._submit(c)
        assert os.listdir(tmp / "vf")
        app._account_rate.clear()
        r = c.delete("/api/account", json={"password": "ClaveSegura#2026"})
        assert r.status_code == 200, r.get_json()
        assert os.listdir(tmp / "vf") == [] and store.list_pending() == []


# ---------------------------------------------------------------------------
# Comandos «/», medida íntima y fotos de progreso (2026-11-16)
# ---------------------------------------------------------------------------
import struct as _struct
import zlib as _zlib


def _jpeg_exif():
    seg = lambda m, p: bytes([0xFF, m]) + _struct.pack(">H", len(p) + 2) + p
    return (b"\xff\xd8" + seg(0xE1, b"Exif\x00\x00GPS-SECRETO") + seg(0xDB, b"\x00" + bytes(64)) +
            seg(0xDA, b"\x01\x01\x00\x00\x3f\x00") + b"\x12\x34" + b"\xff\xd9")


class TestSlashAndSensitiveData:
    @pytest.fixture
    def env(self, flask_app, monkeypatch, tmp_path):
        from core.verification.verification import VerificationStore
        store = VerificationStore(str(tmp_path / "v.db"), str(tmp_path / "vf"))
        old = flask_app._shared.get("verification")
        flask_app._shared["verification"] = store
        flask_app._account_rate.clear()
        flask_app._rate_data.clear()
        yield flask_app, store, tmp_path, monkeypatch
        flask_app._shared["verification"] = old
        flask_app._account_rate.clear()
        flask_app._rate_data.clear()

    def _dev(self, env, birth="1990-05-05"):
        app, store, _, mp = env
        c = _authed(app) if birth == "1990-05-05" else _authed_born(app, birth)
        email = c.get("/api/account/me").get_json()["profile"]["email"]
        mp.setenv("OMNIA_DEV_EMAILS", f"otro@x.com, {email.upper()}")
        return c

    def _verify(self, env, c, consent=("intimate_measure",)):
        app, store, _, _ = env
        aid = c.get("/api/account/me").get_json()["profile"]["user_id"]
        vid = store.submit(aid, "adult", date(1990, 5, 5), {"id_doc": _JPG, "face": _PNG})
        store.approve(vid, "t")
        from core.verification.verification import CONSENT_TEXT_VERSION, PHOTOS_CONSENT_VERSION
        for k in consent:
            store.grant_consent(aid, k, CONSENT_TEXT_VERSION if k == "intimate_measure" else PHOTOS_CONSENT_VERSION)
        return aid

    def _say(self, env, c, text):
        env[0]._rate_data.clear()
        r = post_chat(c, text)
        assert r.status_code == 200, r.get_json()
        return r.get_json()

    # ---- quién puede usar «/»
    def test_me_reports_developer_flag(self, env):
        app, _, _, mp = env
        c = _authed(app)
        assert c.get("/api/account/me").get_json()["developer"] is False
        c = self._dev(env)
        assert c.get("/api/account/me").get_json()["developer"] is True
        assert _anon(app).get("/api/account/me").get_json().get("developer") is None

    def test_non_developer_is_refused_and_nothing_runs(self, env):
        app, store, _, mp = env
        mp.delenv("OMNIA_DEV_EMAILS", raising=False)
        c = _authed(app)
        r = self._say(env, c, "/[Corporal Verified] hueso púbico 15.2")
        assert "solo para el desarrollador" in r["response"] and r["slash"] is True and r["module"] is None
        assert "solo para el desarrollador" in self._say(env, c, "/")["response"]

    def test_list_and_bad_module(self, env):
        c = self._dev(env)
        r = self._say(env, c, "/")
        assert "/[Corporal Verified]" in r["response"] and "/[NutriVida]" in r["response"]
        r = self._say(env, c, "/[Nada] hola")
        assert "No existe el módulo" in r["response"] and "/[NutriVida]" in r["response"]
        assert "Escribe el mensaje" in self._say(env, c, "/[NutriVida]")["response"]

    def test_forced_module_ignores_keyword_scoring(self, env):
        c = self._dev(env)
        r = self._say(env, c, "/[NutriVida] quiero saber mi IMC, peso 70 kg y mido 175 cm")
        assert r["module"] == "NutriVida" and "IMC" in r["response"].upper()

    def test_case_insensitive_module_name(self, env):
        c = self._dev(env)
        r = self._say(env, c, "/[nutrivida] peso 70 kg, mido 175 cm")
        assert r["module"] == "NutriVida"

    def test_slash_is_not_saved_in_history_or_echo(self, env):
        c = self._dev(env)
        r = self._say(env, c, "/[NutriVida] peso 70 kg, mido 175 cm")
        assert r["echo_saved"] is False and r.get("data") is None

    # ---- gates (los mismos que el chat normal)
    def test_minor_developer_still_age_restricted(self, env):
        c = self._dev(env, birth="2010-01-01")
        r = self._say(env, c, "/[Corporal Verified] hueso púbico 15.2")
        assert r["age_restricted"] is True

    def test_unverified_developer_is_blocked(self, env):
        c = self._dev(env)
        r = self._say(env, c, "/[Corporal Verified] hueso púbico 15.2")
        assert r["auth_required"] is True and r["module"] == "Corporal Verified"

    # ---- medida íntima por «/»
    def test_intimate_needs_consent_then_saves(self, env):
        app, store, _, _ = env
        c = self._dev(env)
        aid = self._verify(env, c, consent=())
        r = self._say(env, c, "/[Corporal Verified] hueso púbico 15.2")
        assert "consentimiento" in r["response"] and app._shared["ecosystem"].counts(aid).get("Corporal Verified", 0) == 0
        from core.verification.verification import CONSENT_TEXT_VERSION
        store.grant_consent(aid, "intimate_measure", CONSENT_TEXT_VERSION)
        r = self._say(env, c, "/[Corporal Verified] hueso púbico 15,2 cm")
        assert "Registrado" in r["response"] and "15.2" in r["response"]
        recs = c.get("/api/account/modules/Corporal%20Verified/records?kind=medida_intima").get_json()
        rows = recs.get("records") or recs.get("items") or []
        assert len(rows) == 1 and rows[0]["payload"] == {"origen": "hueso_pubico", "tipo": "longitud", "cm": 15.2}

    def test_intimate_validation_messages(self, env):
        c = self._dev(env)
        self._verify(env, c)
        assert "creíble" in self._say(env, c, "/[Corporal Verified] base 99")["response"]
        r = self._say(env, c, "/[Corporal Verified] hueso púbico")
        assert "cuántos cm" in r["response"]
        r = self._say(env, c, "/[Corporal Verified] base 2.5")
        assert "No guardé nada" in r["response"]

    def test_intimate_via_normal_chat_needs_clear_words(self, env):
        c = self._dev(env)
        self._verify(env, c)
        r = self._say(env, c, "quiero registrar mi medida íntima: hueso púbico 15.2")
        assert r["module"] == "Corporal Verified" and "Registrado" in r["response"]
        r = self._say(env, c, "¿Cómo mido mi porcentaje de grasa corporal?")
        assert r["module"] == "Corporal Verified" and "Registrado" not in r["response"]

    # ---- API de la medida íntima
    def test_intimate_api(self, env):
        app, store, _, _ = env
        c = _authed(app)
        assert c.post("/api/corporal/intimate-measure", json={"origin": "base", "cm": 14}).status_code == 403
        self._verify(env, c)
        post = lambda body: c.post("/api/corporal/intimate-measure", json=body)
        r = post({"origin": "perimetro", "cm": 12.34})
        assert r.status_code == 201 and r.get_json()["cm"] == 12.3
        for bad in ({"origin": "x", "cm": 12}, {"origin": "base", "cm": "no"}, {"origin": "base", "cm": 99}, {}):
            assert post(bad).status_code == 400
        assert c.post("/api/corporal/intimate-measure", data="no json", content_type="text/plain").status_code == 400
        assert _anon(app).post("/api/corporal/intimate-measure", json={}).status_code == 401
        minor = _authed_born(app, "2010-01-01")
        assert minor.post("/api/corporal/intimate-measure", json={"origin": "base", "cm": 14}).status_code == 403

    # ---- fotos de progreso
    def _photo(self, c, data=None, note="semana 1"):
        return c.post("/api/corporal/progress-photos", content_type="multipart/form-data",
                      data={"photo": (io.BytesIO(data if data is not None else _jpeg_exif()), "a.jpg"), "note": note})

    def test_photos_flow_private_and_stripped(self, env):
        app, store, tmp, _ = env
        c = _authed(app)
        self._verify(env, c, consent=())
        assert self._photo(c).status_code == 400                       # sin consentimiento
        v = c.get("/api/corporal/verification").get_json()
        assert v["progress_photos_consent"] is False and "solo tú" in v["photos_consent_text"]
        assert c.post("/api/corporal/consent", json={"version": "vieja", "kind": "progress_photos"}).status_code == 400
        r = c.post("/api/corporal/consent", json={"version": v["photos_consent_version"], "kind": "progress_photos"})
        assert r.get_json()["progress_photos_consent"] is True and r.get_json()["intimate_measure_consent"] is False
        r = self._photo(c)
        assert r.status_code == 201
        pid = r.get_json()["id"]
        lst = c.get("/api/corporal/progress-photos").get_json()
        assert lst["consent"] is True and [(p["id"], p["note"]) for p in lst["photos"]] == [(pid, "semana 1")]
        img = c.get(f"/api/corporal/progress-photos/{pid}")
        assert img.status_code == 200 and img.mimetype == "image/jpeg" and b"GPS" not in img.data
        assert img.headers["X-Content-Type-Options"] == "nosniff" and "no-store" in img.headers["Cache-Control"]
        # otra cuenta (también verificada y con consentimiento) no la ve ni la borra
        other = _authed(app)
        self._verify(env, other, consent=("progress_photos",))
        assert other.get(f"/api/corporal/progress-photos/{pid}").status_code == 404
        assert other.delete(f"/api/corporal/progress-photos/{pid}").status_code == 404
        assert other.get("/api/corporal/progress-photos").get_json()["photos"] == []
        assert c.delete(f"/api/corporal/progress-photos/{pid}").status_code == 200
        assert c.get(f"/api/corporal/progress-photos/{pid}").status_code == 404

    def test_photos_not_visible_to_the_fons(self, env):
        app, store, _, _ = env
        c = _authed(app)
        self._verify(env, c, consent=("progress_photos",))
        assert self._photo(c).status_code == 201
        pid = store.list_photos(c.get("/api/account/me").get_json()["profile"]["user_id"])[0]["id"]
        for kind in ("id_doc", "face", "student_doc", "photo"):
            assert app.app.test_client().get(f"/api/fons/verifications/{pid}/image/{kind}").status_code == 401

    def test_photo_validation_and_access(self, env):
        app, store, tmp, _ = env
        c = _authed(app)
        assert self._photo(c).status_code == 400                       # sin verificar ni consentimiento
        self._verify(env, c, consent=("progress_photos",))
        assert self._photo(c, data=b"GIF89a....").status_code == 400
        assert self._photo(c, data=b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024)).status_code == 413
        assert c.post("/api/corporal/progress-photos", content_type="multipart/form-data", data={}).status_code == 400
        assert _anon(app).get("/api/corporal/progress-photos").status_code == 401
        minor = _authed_born(app, "2010-01-01")
        assert minor.get("/api/corporal/progress-photos").status_code == 403

    def test_revoking_photos_consent_hides_them(self, env):
        app, store, _, _ = env
        c = _authed(app)
        self._verify(env, c, consent=("progress_photos",))
        pid = self._photo(c).get_json()["id"]
        r = c.delete("/api/corporal/consent?kind=progress_photos")
        assert r.get_json()["progress_photos_consent"] is False
        assert c.get("/api/corporal/progress-photos").get_json() == {"photos": [], "consent": False}
        assert c.get(f"/api/corporal/progress-photos/{pid}").status_code == 404
        assert c.delete("/api/corporal/consent?kind=otra").status_code == 400

    def test_account_delete_removes_photos(self, env):
        app, store, tmp, _ = env
        c = _authed(app)
        self._verify(env, c, consent=("progress_photos",))
        self._photo(c)
        assert os.listdir(store._photos_dir)
        app._account_rate.clear()
        assert c.delete("/api/account", json={"password": "ClaveSegura#2026"}).status_code == 200
        assert os.listdir(store._photos_dir) == []
