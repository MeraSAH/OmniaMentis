"""
* UBICACIÓN: OmniaMentis/src/core/auth/fons_auth.py
* PROPÓSITO: Autenticación del panel del Fons mediante contraseña
*            hasheada (PBKDF2-HMAC-SHA256) y tokens de sesión firmados
*            con HMAC. Protege fons_panel.html y los endpoints
*            /api/ethics/* que exponen datos de moderación SILENS.
* DEPENDENCIAS: hashlib, hmac, base64, os, time (stdlib — sin C
*            extensions, ver decisión de diseño abajo)
* CREADO: 2026-06-30
* ÚLTIMA MODIFICACIÓN: 2026-06-30
* ESTADO: Producción
*
* DECISIÓN DE DISEÑO: se evita bcrypt/argon2 deliberadamente. Este
* proyecto ya sufrió problemas serios de compilación en Windows con
* pydantic-core (ver fix_fastapi.py, recrear_venv.bat,
* instalar_rust_gnu.bat en la raíz del repo). PBKDF2-HMAC-SHA256 con
* 200,000 iteraciones es stdlib puro, sin wheels nativos que compilar,
* y sigue siendo criptográficamente adecuado para un panel de un solo
* operador (El Fons) — no es un sistema multiusuario de alto volumen
* que justifique la complejidad operativa de Argon2id.
*
* Los tokens de sesión son stateless (autocontenidos y firmados): no
* requieren una tabla de sesiones en base de datos, lo cual es
* apropiado para un panel de administración de un único operador.
"""

import base64
import hashlib
import hmac
import os
import time
from typing import Optional

PBKDF2_ITERATIONS: int = 200_000
SALT_BYTES: int = 16


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """
    Genera un hash de contraseña con PBKDF2-HMAC-SHA256.

    Args:
        password: Contraseña en texto plano. No puede estar vacía.
        salt: Salt opcional en bytes. Exponer este parámetro es solo
            para tests deterministas — en producción NUNCA pasar un
            salt fijo; se genera aleatoriamente por defecto.

    Returns:
        str: hash codificado en base64 (salt + derived key concatenados).

    Raises:
        ValueError: Si password está vacía.
    """
    if not password:
        raise ValueError("La contraseña no puede estar vacía")
    salt = salt if salt is not None else os.urandom(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return base64.b64encode(salt + derived_key).decode("ascii")


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifica una contraseña contra un hash almacenado, usando
    comparación de tiempo constante para evitar ataques de timing.

    Args:
        password: Contraseña en texto plano a verificar.
        stored_hash: Hash previamente generado con hash_password().

    Returns:
        bool: True si la contraseña es correcta. False también ante
            cualquier error de formato del hash (fail-closed).
    """
    if not password or not stored_hash:
        return False
    try:
        raw = base64.b64decode(stored_hash)
        salt, expected_key = raw[:SALT_BYTES], raw[SALT_BYTES:]
        if not salt or not expected_key:
            return False
        derived_key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(derived_key, expected_key)
    except (ValueError, TypeError):
        return False


def create_session_token(secret_key: str, ttl_seconds: int = 8 * 3600) -> str:
    """
    Crea un token de sesión firmado con HMAC-SHA256 y expiración
    autocontenida (stateless).

    Args:
        secret_key: Clave secreta del servidor (env var FONS_SECRET_KEY).
        ttl_seconds: Tiempo de vida del token en segundos (default: 8h).

    Returns:
        str: token opaco codificado en base64 URL-safe.

    Raises:
        ValueError: Si secret_key está vacío.
    """
    if not secret_key:
        raise ValueError("secret_key no puede estar vacío")
    expiry = int(time.time()) + ttl_seconds
    payload = f"fons:{expiry}"
    signature = hmac.new(
        secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    token_raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("ascii")


def verify_session_token(token: str, secret_key: str) -> bool:
    """
    Verifica un token de sesión: firma HMAC válida y no expirado.

    Args:
        token: Token devuelto por create_session_token().
        secret_key: Misma clave secreta usada para firmarlo.

    Returns:
        bool: True si el token es válido y no ha expirado. False ante
            cualquier error de formato o firma inválida (fail-closed).
    """
    if not token or not secret_key:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split(":")
        if len(parts) != 3:
            return False
        prefix, expiry_str, signature = parts
        if prefix != "fons":
            return False

        payload = f"{prefix}:{expiry_str}"
        expected_signature = hmac.new(
            secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return False

        if int(expiry_str) < int(time.time()):
            return False

        return True
    except (ValueError, TypeError, UnicodeDecodeError):
        return False