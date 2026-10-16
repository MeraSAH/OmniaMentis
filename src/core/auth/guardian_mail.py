"""
* UBICACIÓN: OmniaMentis/src/core/auth/guardian_mail.py
* PROPÓSITO: Enviar al representante legal de una persona de 13-14 años el
*            enlace de confirmación de su cuenta (consentimiento verificable).
* DEPENDENCIAS: stdlib únicamente (smtplib, ssl, email)
* CREADO: 2026-10-14
* ESTADO: Producción
*
* DECISIONES DE DISEÑO
*
* 1. Falla cerrado: sin SMTP configurado NO se puede registrar a una persona
*    de 13-14 años (la API responde 503 "guardian_mail_unavailable"). Mejor
*    cerrar ese registro que crear cuentas que nadie puede activar o, peor,
*    activarlas sin verificar a nadie.
*
* 2. Configuración por variables de entorno (se leen en cada envío, así los
*    tests y el .env pueden cambiarlas):
*      OMNIA_SMTP_HOST, OMNIA_SMTP_PORT (587), OMNIA_SMTP_USER,
*      OMNIA_SMTP_PASSWORD, OMNIA_SMTP_FROM, OMNIA_SMTP_SECURITY
*      ("starttls" por defecto, "ssl" o "none"), OMNIA_PUBLIC_URL (dirección
*      pública del dashboard; el enlace apunta a /representante.html).
*
* 3. Modo desarrollo: OMNIA_DEV_PRINT_GUARDIAN_LINK=true imprime el enlace en
*    la consola del servidor en vez de enviarlo. SOLO para probar en tu PC:
*    en producción dejaría el enlace en los logs.
*
* 4. El token va en el FRAGMENTO de la URL (#t=...): el navegador no lo envía
*    en la petición HTTP, así que no queda en logs de servidores ni proxys.
*
* 5. Minimización: el correo dice quién pidió la cuenta (su email y nombre si
*    lo dio) y qué se autoriza; no incluye contraseñas ni datos de uso.
"""

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional
from urllib.parse import urlsplit

logger = logging.getLogger("omnia.guardian_mail")

DEFAULT_PUBLIC_URL = "http://127.0.0.1:8080"
SMTP_TIMEOUT_SECONDS = 15


class MailError(Exception):
    """No se pudo entregar el correo (configuración ausente o fallo SMTP)."""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _flag(name: str) -> bool:
    return _env(name).lower() in ("1", "true", "yes", "on")


def dev_print_mode() -> bool:
    return _flag("OMNIA_DEV_PRINT_GUARDIAN_LINK")


def is_configured() -> bool:
    """¿Hay forma de entregar el enlace (SMTP completo o modo desarrollo)?"""
    if dev_print_mode():
        return True
    return bool(_env("OMNIA_SMTP_HOST") and _env("OMNIA_SMTP_FROM"))


def _public_base() -> str:
    """Dirección pública del dashboard, tolerante a errores típicos del .env:
    barra final, o la URL de una página (".../omnia_dashboard.html" o
    ".../representante.html"), que duplicaría la ruta en el enlace. Una
    dirección que no es http(s) se ignora (con aviso) y se usa la de desarrollo."""
    raw = _env("OMNIA_PUBLIC_URL", DEFAULT_PUBLIC_URL)
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        logger.warning("OMNIA_PUBLIC_URL no es una dirección http(s) válida; se usa %s", DEFAULT_PUBLIC_URL)
        return DEFAULT_PUBLIC_URL
    path = parts.path.rstrip("/")
    if path.lower().endswith(".html"):
        path = path.rsplit("/", 1)[0]
    return f"{parts.scheme}://{parts.netloc}{path}"


def build_link(token: str) -> str:
    return f"{_public_base()}/representante.html#t={token}"


def _clean_header(value: str) -> str:
    """Una línea, sin saltos: evita inyección de cabeceras con nombres raros."""
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def build_message(to: str, link: str, minor_email: str, minor_name: Optional[str]) -> EmailMessage:
    who = _clean_header(minor_email)
    if minor_name:
        who = f"{_clean_header(minor_name)} ({who})"
    msg = EmailMessage()
    msg["Subject"] = "Autorización de representante legal — OmniaMentis"
    msg["From"] = _env("OMNIA_SMTP_FROM")
    msg["To"] = to
    msg.set_content(
        "Hola,\n\n"
        f"{who} quiere crear una cuenta en OmniaMentis, una inteligencia artificial "
        "conversacional experimental. Tiene entre 13 y 14 años, y la ley exige que su madre, "
        "padre o representante legal autorice el uso de sus datos personales.\n\n"
        "Si usted es su representante legal y está de acuerdo, abra este enlace, lea los textos "
        "y confirme:\n\n"
        f"{link}\n\n"
        "El enlace es personal, sirve una sola vez y vence en 7 días. Si no reconoce esta "
        "solicitud, ignore este mensaje: la cuenta no se activará y se borrará sola.\n\n"
        "OmniaMentis no es un servicio de salud ni de emergencias. En una emergencia llame al 911.\n"
    )
    return msg


def send_guardian_link(to: str, token: str, minor_email: str, minor_name: Optional[str] = None) -> None:
    """Envía (o imprime, en modo desarrollo) el enlace. Lanza MailError si falla."""
    link = build_link(token)
    if dev_print_mode():
        logger.warning("[DEV] Enlace del representante para %s: %s", to, link)
        print(f"\n[DEV] Enlace del representante para {to}:\n{link}\n", flush=True)
        return

    host = _env("OMNIA_SMTP_HOST")
    sender = _env("OMNIA_SMTP_FROM")
    if not host or not sender:
        raise MailError("SMTP no configurado")
    try:
        port = int(_env("OMNIA_SMTP_PORT", "587"))
    except ValueError:
        raise MailError("OMNIA_SMTP_PORT inválido")
    security = _env("OMNIA_SMTP_SECURITY", "starttls").lower()
    user = _env("OMNIA_SMTP_USER")
    password = os.environ.get("OMNIA_SMTP_PASSWORD", "")

    msg = build_message(to, link, minor_email, minor_name)
    try:
        context = ssl.create_default_context()
        if security == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=SMTP_TIMEOUT_SECONDS, context=context)
        else:
            server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS)
        with server:
            if security == "starttls":
                server.starttls(context=context)
            if user:
                server.login(user, password)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError, ssl.SSLError) as e:
        # No se registra el destinatario ni el enlace: solo el tipo de fallo.
        logger.error("Fallo enviando el correo al representante: %s", type(e).__name__)
        raise MailError("No se pudo enviar el correo") from e