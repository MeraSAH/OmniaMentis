#!/usr/bin/env python3
"""
* UBICACIÓN: OmniaMentis/scripts/set_fons_password.py
* PROPÓSITO: Utilidad de línea de comandos para generar el hash de la
*            contraseña de El Fons (PBKDF2-HMAC-SHA256) y la clave de
*            firma de sesión, necesarias para proteger
*            manifestation/web_interface/fons_panel.html y los
*            endpoints /api/ethics/*.
* DEPENDENCIAS: getpass, secrets (stdlib), src/core/auth/fons_auth.py
* CREADO: 2026-06-30
* ÚLTIMA MODIFICACIÓN: 2026-06-30
* ESTADO: Producción
*
* USO (VS Code Terminal / PowerShell, Windows 11 Pro):
*     cd C:\\Users\\Usuario\\OmniaMentis
*     .venv\\Scripts\\activate.bat
*     set PYTHONPATH=%CD%\\src
*     python scripts\\set_fons_password.py
*
* El script NUNCA guarda la contraseña ni el hash en disco por sí
* mismo — solo imprime los comandos `set` a ejecutar (o a agregar en
* iniciar_flask.bat) para definir FONS_PASSWORD_HASH y
* FONS_SECRET_KEY antes de iniciar el servidor.
"""

import getpass
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.auth.fons_auth import hash_password  # noqa: E402


def main() -> None:
    print("=" * 70)
    print("🔐 CONFIGURACIÓN DE CONTRASEÑA DEL PANEL DEL FONS")
    print("=" * 70)
    print()
    print("Esta contraseña protege manifestation/web_interface/fons_panel.html")
    print("y todos los endpoints /api/ethics/* (datos de moderación SILENS).")
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

    print("\n✅ Hash generado correctamente.\n")
    print("=" * 70)
    print("COPIA ESTOS COMANDOS en iniciar_flask.bat (antes de")
    print("'call .venv\\Scripts\\activate.bat') o ejecútalos manualmente")
    print("en la terminal antes de iniciar el servidor cada vez:")
    print("=" * 70)
    print()
    print(f"set FONS_PASSWORD_HASH={password_hash}")
    print(f"set FONS_SECRET_KEY={secret_key}")
    print()
    print("=" * 70)
    print("⚠️  IMPORTANTE:")
    print("   - NUNCA subas estos valores a git. Van en variables de")
    print("     entorno locales o en un .env no versionado (ya cubierto")
    print("     por .gitignore: líneas '.env' / '.env.local').")
    print("   - Si cambias FONS_SECRET_KEY, todas las sesiones activas")
    print("     del Fons se invalidan de inmediato (comportamiento")
    print("     esperado, no un bug).")
    print("   - Guarda la contraseña en un gestor de contraseñas: este")
    print("     script no la conserva en ningún lado tras ejecutarse.")
    print("=" * 70)


if __name__ == "__main__":
    main()