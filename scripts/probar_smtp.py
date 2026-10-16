r"""
* UBICACIÓN: OmniaMentis/scripts/probar_smtp.py
* PROPÓSITO: Probar tu SMTP real SIN arrancar la API: envía un correo de prueba
*            (con el mismo formato que recibe un representante legal) usando las
*            variables OMNIA_SMTP_* de tu .env.
* USO (PowerShell, desde la raíz del proyecto, con el .venv activo):
*      python scripts\probar_smtp.py destinatario@ejemplo.com
*    El destinatario puede ser tu propio correo. El enlace del mensaje lleva un
*    token de PRUEBA: no activa ninguna cuenta.
* No imprime tu contraseña ni la guarda en ningún sitio.
* CREADO: 2026-10-15
"""

import os
import smtplib
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:          # sin python-dotenv: se usan las variables del sistema
    pass

from core.auth import guardian_mail  # noqa: E402

HINTS = {
    smtplib.SMTPAuthenticationError: (
        "El servidor rechazó el usuario o la contraseña. En Gmail hay que usar una "
        "«contraseña de aplicación» (16 letras, con la verificación en dos pasos activada), "
        "no la contraseña normal, y el usuario debe ser la cuenta real, sin «+alias»."),
    smtplib.SMTPRecipientsRefused: "El servidor rechazó el correo del destinatario. Revisa que esté bien escrito.",
    smtplib.SMTPSenderRefused: "El servidor rechazó el remitente. OMNIA_SMTP_FROM debe ser la misma cuenta que OMNIA_SMTP_USER.",
    smtplib.SMTPConnectError: "No se pudo conectar con el servidor. Revisa OMNIA_SMTP_HOST y OMNIA_SMTP_PORT.",
    ssl.SSLError: "Falló el cifrado TLS. Prueba OMNIA_SMTP_SECURITY=starttls con puerto 587, o ssl con puerto 465.",
    TimeoutError: "Se agotó el tiempo de espera. Revisa el host, el puerto y tu conexión o firewall.",
    OSError: "No hay conexión con el servidor SMTP. Revisa el host, el puerto y tu conexión.",
}


def main() -> int:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Uso: python scripts\\probar_smtp.py destinatario@ejemplo.com")
        return 2
    to = sys.argv[1].strip()

    if guardian_mail.dev_print_mode():
        print("AVISO: OMNIA_DEV_PRINT_GUARDIAN_LINK está activo: no se enviará ningún correo real.")
        print("       Desactívalo en el .env (quita la línea o ponla en false) para probar el SMTP.")
    host = os.environ.get("OMNIA_SMTP_HOST", "").strip()
    print(f"Servidor: {host or '(sin configurar)'}:{os.environ.get('OMNIA_SMTP_PORT', '587')} "
          f"· seguridad: {os.environ.get('OMNIA_SMTP_SECURITY', 'starttls')} "
          f"· usuario: {os.environ.get('OMNIA_SMTP_USER', '') or '(ninguno)'} "
          f"· remitente: {os.environ.get('OMNIA_SMTP_FROM', '') or '(sin configurar)'}")
    if not guardian_mail.is_configured():
        print("ERROR: falta OMNIA_SMTP_HOST u OMNIA_SMTP_FROM en el .env.")
        return 1

    # Para ver la causa real (y darte la pista), se envía sin el envoltorio MailError.
    token = "PRUEBA" + "x" * 37
    link = guardian_mail.build_link(token)
    msg = guardian_mail.build_message(to, link, "prueba@example.com", "Prueba de OmniaMentis")
    msg.replace_header("Subject", "[PRUEBA] " + msg["Subject"])
    try:
        port = int(os.environ.get("OMNIA_SMTP_PORT", "587").strip())
        security = os.environ.get("OMNIA_SMTP_SECURITY", "starttls").strip().lower()
        user = os.environ.get("OMNIA_SMTP_USER", "").strip()
        password = os.environ.get("OMNIA_SMTP_PASSWORD", "")
        ctx = ssl.create_default_context()
        timeout = guardian_mail.SMTP_TIMEOUT_SECONDS
        server = (smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) if security == "ssl"
                  else smtplib.SMTP(host, port, timeout=timeout))
        with server:
            if security == "starttls":
                server.starttls(context=ctx)
            if user:
                server.login(user, password)
            server.send_message(msg)
    except Exception as e:                       # noqa: BLE001 — es una herramienta de diagnóstico
        hint = next((h for t, h in HINTS.items() if isinstance(e, t)), "")
        print(f"ERROR ({type(e).__name__}): {e}")
        if hint:
            print("Pista:", hint)
        return 1
    print(f"OK: correo de prueba enviado a {to}. Revisa la bandeja (y spam).")
    print(f"El enlace de prueba apunta a: {link}")
    return 0


if __name__ == "__main__":
    sys.exit(main())