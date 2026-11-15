#!/usr/bin/env python3
"""
* UBICACIÓN: OmniaMentis/scripts/omnia_desktop.py
* PROPÓSITO: Lanzador de escritorio (Windows y Linux). Arranca el servidor de OmniaMentis SOLO en tu
*            equipo (127.0.0.1), espera a que esté listo y abre el dashboard en una ventana de aplicación.
*            Al cerrar la ventana, apaga el servidor.
* USO:       python scripts/omnia_desktop.py            (ventana de aplicación)
*            python scripts/omnia_desktop.py --no-window (solo servidor; abre la URL tú mismo)
*            python scripts/omnia_desktop.py --check     (comprueba el entorno sin arrancar nada)
* NOTAS:     - Ollama debe estar instalado y en marcha aparte; este lanzador no lo gestiona.
*            - El servidor NO queda expuesto a la red: escucha solo en 127.0.0.1.
*            - Usa un perfil de navegador propio (data/desktop_profile): no toca tu Chrome/Edge habitual.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, List, Mapping, Optional

FROZEN = bool(getattr(sys, "frozen", False))      # True dentro del .exe (PyInstaller)
# Como script: la carpeta del proyecto es la de arriba. Como .exe: la carpeta donde está OmniaMentis.exe.
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
CREATE_NO_WINDOW = 0x08000000                     # Windows: no abrir una consola para el servidor
PREFERRED_PORT = 8000

_WINDOWS_BROWSERS = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
)
_LINUX_BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser")


def find_python(root: Path, platform: str = sys.platform, frozen: bool = FROZEN,
                which: Callable[[str], Optional[str]] = shutil.which,
                exists: Callable[[str], bool] = os.path.exists,
                current: str = sys.executable) -> Optional[str]:
    """El Python que ejecutará el servidor. Como script, el que ejecuta este archivo; como .exe, el entorno
    virtual del proyecto (.venv) o, si no hay, el Python del sistema (el .exe NO lleva Flask dentro)."""
    if not frozen:
        return current
    win = platform.startswith("win")
    venv = root / (".venv/Scripts/python.exe" if win else ".venv/bin/python")
    if exists(str(venv)):
        return str(venv)
    for name in (("python", "py") if win else ("python3", "python")):
        found = which(name)
        if found:
            return found
    return None


def python_has_flask(python: str) -> bool:
    try:
        flags = CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
        return subprocess.run([python, "-c", "import flask"], capture_output=True, timeout=60,
                              creationflags=flags).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def say(*parts: object) -> None:
    """print() que no falla en el .exe sin consola (donde sys.stdout es None)."""
    if sys.stdout is not None:
        print(*parts)


def notify(message: str, title: str = "OmniaMentis") -> None:
    """Mensaje para la persona: en consola si la hay; en el .exe sin consola, una ventana de Windows."""
    if sys.stdout is not None and not FROZEN:
        print(message)
        return
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
            return
        except Exception:
            pass
    if sys.stdout is not None:
        print(message)


def find_free_port(preferred: int = PREFERRED_PORT) -> int:
    """El puerto preferido si está libre; si no, uno libre cualquiera."""
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return s.getsockname()[1]
    raise RuntimeError("No hay ningún puerto libre en 127.0.0.1.")


def build_env(root: Path, port: int, base: Mapping[str, str]) -> dict:
    """Entorno del servidor: solo local, sirviendo el dashboard y con el código fuente en el PYTHONPATH."""
    env = dict(base)
    src = str(root / "src")
    env.update({
        "HOST": "127.0.0.1",
        "PORT": str(port),
        "SERVE_DASHBOARD": "true",
        "PYTHONPATH": src + (os.pathsep + base["PYTHONPATH"] if base.get("PYTHONPATH") else ""),
        "PYTHONUNBUFFERED": "1",
    })
    return env


def find_browser(platform: str = sys.platform,
                 which: Callable[[str], Optional[str]] = shutil.which,
                 exists: Callable[[str], bool] = os.path.exists,
                 expand: Callable[[str], str] = os.path.expandvars) -> Optional[str]:
    """Chrome, Edge, Chromium o Brave (los que saben abrir una ventana de aplicación)."""
    if platform.startswith("win"):
        for p in _WINDOWS_BROWSERS:
            path = expand(p)
            if "%" not in path and exists(path):
                return path
        return None
    for name in _LINUX_BROWSERS:
        found = which(name)
        if found:
            return found
    return None


def app_command(browser: str, url: str, profile_dir: Path) -> List[str]:
    return [browser, f"--app={url}", f"--user-data-dir={profile_dir}", "--no-first-run", "--no-default-browser-check"]


def wait_for_health(url: str, timeout: float = 120.0, interval: float = 0.5,
                    opener: Callable[..., object] = urllib.request.urlopen,
                    alive: Callable[[], bool] = lambda: True,
                    sleep: Callable[[float], None] = time.sleep,
                    clock: Callable[[], float] = time.monotonic) -> bool:
    """True cuando `url` responde 200; False si se acaba el tiempo o el servidor murió."""
    deadline = clock() + timeout
    while clock() < deadline:
        if not alive():
            return False
        try:
            with opener(url, timeout=3) as r:  # type: ignore[call-arg]
                if getattr(r, "status", 200) == 200:
                    return True
        except Exception:
            pass
        sleep(interval)
    return False


def check_environment(root: Path = ROOT, python: Optional[str] = None) -> List[str]:
    """Lista de problemas (vacía si todo está bien)."""
    problems = []
    if not (root / "src" / "api" / "main_flask.py").is_file():
        problems.append("No encuentro src/api/main_flask.py: OmniaMentis.exe debe estar dentro de la carpeta de OmniaMentis.")
    if not (root / "manifestation" / "web_interface" / "omnia_dashboard.html").is_file():
        problems.append("No encuentro manifestation/web_interface/omnia_dashboard.html.")
    py = python if python is not None else find_python(root)
    if py is None:
        problems.append("No encuentro Python. Instala Python o crea el entorno .venv del proyecto.")
    elif not python_has_flask(py):
        problems.append(f"Flask no está instalado en {py} (ejecuta: pip install -r requirements.txt).")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Lanzador de escritorio de OmniaMentis")
    ap.add_argument("--no-window", action="store_true", help="solo arranca el servidor")
    ap.add_argument("--check", action="store_true", help="comprueba el entorno y sale")
    ap.add_argument("--port", type=int, default=PREFERRED_PORT)
    ap.add_argument("--timeout", type=float, default=120.0, help="segundos de espera a que el servidor esté listo")
    args = ap.parse_args(argv)

    python = find_python(ROOT)
    problems = check_environment(ROOT, python)
    browser = find_browser()
    if args.check:
        for p in problems:
            say("PROBLEMA:", p)
        say("Navegador para la ventana de aplicación:", browser or "ninguno (se usará el navegador por defecto)")
        say("Todo listo." if not problems else "Hay problemas que arreglar.")
        return 1 if problems else 0
    if problems:
        notify("OmniaMentis no puede arrancar:\n\n" + "\n".join("• " + p for p in problems))
        return 1

    port = find_free_port(args.port)
    url = f"http://127.0.0.1:{port}/app/"
    (ROOT / "logs").mkdir(exist_ok=True)
    log = open(ROOT / "logs" / "desktop_server.log", "ab")
    server = subprocess.Popen([python, str(ROOT / "src" / "api" / "main_flask.py")], cwd=str(ROOT),
                              env=build_env(ROOT, port, os.environ), stdout=log, stderr=subprocess.STDOUT,
                              creationflags=CREATE_NO_WINDOW if sys.platform.startswith("win") else 0)
    try:
        say(f"Arrancando OmniaMentis en {url} (puede tardar mientras carga el modelo)…")
        if not wait_for_health(f"http://127.0.0.1:{port}/health", args.timeout, alive=lambda: server.poll() is None):
            notify("El servidor no llegó a estar listo. Revisa logs\\desktop_server.log (¿está Ollama en marcha?).")
            return 2
        say("Listo.")
        if args.no_window:
            say(f"Abre {url} en tu navegador. Ctrl+C para apagar.")
            server.wait()
        elif browser:
            profile = ROOT / "data" / "desktop_profile"
            profile.mkdir(parents=True, exist_ok=True)
            window = subprocess.Popen(app_command(browser, url, profile))   # no necesita consola propia
            window.wait()                 # con perfil propio, este proceso vive mientras la ventana esté abierta
        else:
            webbrowser.open(url)
            say("Cierra esta ventana de texto o pulsa Ctrl+C para apagar OmniaMentis.")
            server.wait()
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)   # el servidor guarda las sesiones al cerrar
            except subprocess.TimeoutExpired:
                server.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
