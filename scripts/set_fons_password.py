#!/usr/bin/env python3
"""
* UBICACIÓN: OmniaMentis/scripts/set_fons_password.py
* PROPÓSITO: Utilidad de línea de comandos para generar el hash de la
*            contraseña de El Fons (PBKDF2-HMAC-SHA256) y la clave de
*            firma de sesión, y escribirlas directamente en un archivo
*            .env en la raíz del proyecto.
* DEPENDENCIAS: getpass, secrets (stdlib), src/core/auth/fons_auth.py
* CREADO: 2026-06-30
* ÚLTIMA MODIFICACIÓN: 2026-07-05
* ESTADO: Producción
*
* CAMBIO 2026-07-05: antes este script solo IMPRIMÍA los comandos
* `set FONS_...=...` para que el usuario los copiara manualmente a
* iniciar_flask.bat. Ese flujo manual fue precisamente el que casi
* termina con esas credenciales expuestas en un commit de git público
* (ver incidente de seguridad documentado en la sesión del 2026-07-05).
* Ahora el script escribe/actualiza directamente el archivo .env de
* forma idempotente: si ya existe una línea FONS_SECRET_KEY o
* FONS_PASSWORD_HASH, la reemplaza; si no existe, la agrega. El .env
* nunca se toca manualmente ni se pega en ningún .bat.
*
* USO (VS Code Terminal / PowerShell, Windows 11 Pro):
*     cd C:\\Users\\Usuario\\OmniaMentis
*     .venv\\Scripts\\activate.bat
*     set PYTHONPATH=%CD%\\src
*     python scripts\\set_fons_password.py
"""

import getpass
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.auth.fons_auth import hash_password  # noqa: E402

ENV_FILE = PROJECT_ROOT / ".env"


def upsert_env_var(lines: list, key: str, value: str) -> list:
    """
    Reemplaza la línea KEY=... si ya existe en el archivo .env, o la
    agrega al final si no existe. Preserva el resto del archivo
    intacto (comentarios, otras variables) — nunca sobrescribe el
    .env completo, solo la línea relevante.
    """
    new_line = f"{key}={value}"
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[i] = new_line
            return lines
    lines.append(new_line)
    return lines


def main() -> None:
    print("=" * 70)
    print("🔐 CONFIGURACIÓN DE CONTRASEÑA DEL PANEL DEL FONS")
    print("=" * 70)
    print()
    print("Esta contraseña protege manifestation/web_interface/fons_panel.html")
    print("y todos los endpoints /api/ethics/* (datos de moderación SILENS).")
    print(f"Se escribirá directamente en: {ENV_FILE}")
    print()

    try:
        password = getpass.getpass("Nueva contraseña para El Fons: ")
    except (EOFError, KeyboardInterrupt):
        print("\n\n⚠️  Operación cancelada.")
        sys.exit(1)

    if len(password) < 8:
        print("\n❌ Error: la contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    confirm = getpass.getpass("Confirmar contraseña: ")
    if password != confirm:
        print("\n❌ Error: las contraseñas no coinciden.")
        sys.exit(1)

    password_hash = hash_password(password)
    secret_key = secrets.token_hex(32)

    # Leer .env existente (si existe) para no perder otras variables
    # que ya pudieras tener ahí (ej. OLLAMA_URL, PORT, etc.)
    lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f.readlines()]

    lines = upsert_env_var(lines, "FONS_PASSWORD_HASH", password_hash)
    lines = upsert_env_var(lines, "FONS_SECRET_KEY", secret_key)

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n✅ .env actualizado correctamente en: {ENV_FILE}\n")
    print("=" * 70)
    print("⚠️  IMPORTANTE:")
    print("   - El .env YA está en .gitignore — no necesitas hacer nada")
    print("     más para mantenerlo fuera de git. Verifícalo una vez con:")
    print("     git check-ignore -v .env")
    print("     (si no imprime nada, el archivo NO está ignorado — avísame)")
    print("   - Si tenías líneas 'set FONS_SECRET_KEY=...' o")
    print("     'set FONS_PASSWORD_HASH=...' pegadas en iniciar_flask.bat,")
    print("     BÓRRALAS AHORA — ya no son necesarias y son redundantes")
    print("     con el .env (además de ser el riesgo que originó el")
    print("     incidente de seguridad de esta sesión).")
    print("   - Si cambias la contraseña de nuevo más adelante, este mismo")
    print("     script actualiza el .env sin duplicar líneas.")
    print("   - Si cambias FONS_SECRET_KEY, todas las sesiones activas")
    print("     del Fons se invalidan de inmediato (comportamiento")
    print("     esperado, no un bug).")
    print("=" * 70)


if __name__ == "__main__":
    main()