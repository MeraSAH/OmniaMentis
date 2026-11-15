# OmniaMentis como aplicación (escritorio y móvil)

## 1. Escritorio (Windows y Linux)

### Opción A: sin compilar nada
- Windows: doble clic en `iniciar_escritorio.bat`. Linux: `bash iniciar_escritorio.sh`.

### Opción B: crear `OmniaMentis.exe` (Windows)
1. Doble clic en `construir_exe.bat` (instala PyInstaller en tu `.venv` y compila).
2. Aparece `OmniaMentis.exe` en la carpeta de OmniaMentis. **Debe quedarse ahí**: es solo el lanzador, y usa el Python y las
   librerías de tu `.venv` (por eso pesa pocos MB y siempre usa tu código al día).
3. Crea un acceso directo en el escritorio si quieres. Doble clic para abrir.

Qué hace al abrirlo: arranca el servidor solo en tu equipo (`127.0.0.1`), espera a que esté listo y abre una ventana de
aplicación (Chrome, Edge, Chromium o Brave; si no hay, el navegador por defecto). Al cerrar la ventana apaga el servidor.
Si algo falla muestra un mensaje; el detalle está en `logs\desktop_server.log`.

- Ollama debe estar instalado y en marcha aparte.
- Perfil de navegador propio (`data\desktop_profile`): no toca tu Chrome/Edge habitual.
- `python scripts\omnia_desktop.py --check` comprueba el entorno sin arrancar nada.
- Windows SmartScreen puede avisar la primera vez porque el .exe no está firmado: «Más información» → «Ejecutar de todos modos».

## 2. Panel del administrador (Fons): solo desde ESTE ordenador
El servidor rechaza (403) cualquier uso del panel del Fons que no venga de la propia máquina. Se exige TODO esto a la vez:
1. La conexión llega desde la propia máquina (127.0.0.1 / ::1).
2. No trae ninguna cabecera de proxy o túnel (X-Forwarded-For, CF-Connecting-IP, Forwarded, Via, Tailscale-…, etc.):
   un túnel conecta desde 127.0.0.1 pero siempre deja alguna huella.
3. El `Host` es `localhost`/`127.0.0.1`/`[::1]` (también frena el «DNS rebinding»).
4. Si el navegador envía `Origin`, también es local.

Además las pantallas `fons_login.html`, `fons_panel.html` y `js/fons_auth_guard.js` **ni siquiera se sirven** a quien viene
de fuera (404). Dentro de lo local sigue haciendo falta tu contraseña de revisor. Los intentos desde fuera quedan en
`data/fons_audit.jsonl` (evento `remote_blocked`, máximo uno por minuto).

Entra siempre por `http://127.0.0.1:<puerto>/app/fons_login.html` (el puerto lo muestra el lanzador; normalmente 8000).
`FONS_ALLOW_REMOTE=true` desactiva la protección: **no lo uses**.

## 3. Móvil / Android sin dominio propio

**Por qué no Firebase Hosting:** Firebase Hosting solo aloja archivos estáticos. El cerebro de OmniaMentis (Flask + Ollama +
tus datos) vive en tu ordenador, y no se puede mover a Firebase sin pasar al plan de pago y sin renunciar a Ollama local.
Aunque pusieras ahí la pantalla, seguiría necesitando una dirección pública hacia tu PC (y abrir tu PC a Internet).

**Opción decidida: Tailscale (gratis, sin dominio, privada):**
1. Instala Tailscale en el PC y en el móvil e inicia sesión con la MISMA cuenta.
2. En el panel web de Tailscale (login.tailscale.com → DNS) activa «MagicDNS» y «HTTPS Certificates».
3. En el PC, con OmniaMentis abierto: `tailscale serve --bg 8000` (cambia 8000 si el lanzador usó otro puerto).
4. En el móvil abre la dirección `https://<tu-pc>.<tu-red>.ts.net/app/` en Chrome → ⋮ → «Instalar aplicación».

Qué obtienes: una dirección HTTPS fija, gratuita, accesible **solo desde tus propios dispositivos** (no es pública), sin
CORS (página y API comparten origen). El PC debe estar encendido con OmniaMentis abierto. El panel del Fons seguirá
bloqueado desde el móvil (es lo que quieres).

Opcional: `SESSION_COOKIE_SECURE=true` en `.env` si solo vas a usar la dirección HTTPS.

Nota honesta: esta parte la documento según el funcionamiento de Tailscale, pero no la he podido probar desde mi entorno.

## 4. Si algún día tienes un servidor o dominio propios
`SERVE_DASHBOARD=true`, un proxy HTTPS delante y, si la página queda en otro dominio que la API, la etiqueta
`<meta name="omnia-api" content="https://api.tu-dominio">` en `omnia_dashboard.html` más `CORS_ORIGINS`.
