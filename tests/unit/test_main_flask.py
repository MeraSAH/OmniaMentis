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

import os
import sys
from pathlib import Path

import pytest

SRC_PATH = Path(__file__).parent.parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from core.llm.ollama_client import OllamaUnavailableError


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


@pytest.fixture
def client(flask_app):
    """Un test_client() nuevo por test = un 'usuario' nuevo: cookie
    jar vacía, sin sesión previa. Dos llamadas a esta fixture en el
    mismo test (dos clientes) simulan dos usuarios distintos."""
    return flask_app.app.test_client()


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
        client_a = flask_app.app.test_client()
        client_b = flask_app.app.test_client()

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
        client_a = flask_app.app.test_client()
        client_b = flask_app.app.test_client()

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
        client_a = flask_app.app.test_client()
        client_b = flask_app.app.test_client()

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
            other = flask_app.app.test_client()
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
        statuses = [flask_app.app.test_client().get("/api/consciousness").status_code
                    for _ in range(3)]
        assert statuses == [200, 200, 429]

    def test_user_with_cookie_is_not_affected_by_cap(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "1"
        c = flask_app.app.test_client()
        assert c.get("/api/consciousness").status_code == 200   # crea el usuario
        for _ in range(5):                                      # ya existe -> sin tope
            assert c.get("/api/consciousness").status_code == 200

    def test_429_body_is_json_with_message(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "1"
        flask_app.app.test_client().get("/api/consciousness")
        r = flask_app.app.test_client().get("/api/consciousness")
        assert r.status_code == 429
        assert "message" in r.get_json()

    def test_zero_disables_cap(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "0"
        for _ in range(5):
            assert flask_app.app.test_client().get("/api/consciousness").status_code == 200

    def test_invalid_value_falls_back_to_default(self, flask_app):
        os.environ["MAX_NEW_USERS_PER_IP_HOUR"] = "muchos"
        assert flask_app.app.test_client().get("/api/consciousness").status_code == 200


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
        r = flask_app.app.test_client().get("/api/consciousness")
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