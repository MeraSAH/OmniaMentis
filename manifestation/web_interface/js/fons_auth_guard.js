/*
 * UBICACIÓN: OmniaMentis/manifestation/web_interface/js/fons_auth_guard.js
 * PROPÓSITO: Guard de autenticación para fons_panel.html. Verifica el
 *            token de sesión al cargar la página, redirige a
 *            fons_login.html si es inválido/ausente, y expone
 *            fonsFetch() como reemplazo de fetch() que agrega el
 *            header Authorization automáticamente y maneja 401
 *            redirigiendo al login.
 * DEPENDENCIAS: fons_login.html, backend /api/ethics/* protegido con
 *            @require_fons_auth (src/api/main_flask.py)
 * CREADO: 2026-06-30
 * ÚLTIMA MODIFICACIÓN: 2026-06-30
 * ESTADO: Producción
 *
 * USO en fons_panel.html:
 *   1. Agregar <script src="js/fons_auth_guard.js"></script> como
 *      PRIMER script del <body>, antes de cualquier código que haga
 *      fetch(...) a /api/ethics/*.
 *   2. Reemplazar esas llamadas fetch(`${API}/api/ethics/...`) por
 *      fonsFetch('/api/ethics/...') — misma firma de retorno
 *      (Response), resuelve la URL base internamente.
 *   3. Agregar un botón "Cerrar sesión" con onclick="fonsLogout()".
 */

(function () {
  const LOGIN_PAGE = 'fons_login.html';

  function getToken() {
    return sessionStorage.getItem('fons_token');
  }

  function isLocallyExpired() {
    const expiresAt = sessionStorage.getItem('fons_token_expires_at');
    if (!expiresAt) return true;
    return Date.now() > Number(expiresAt);
  }

  function redirectToLogin() {
    sessionStorage.removeItem('fons_token');
    sessionStorage.removeItem('fons_token_expires_at');
    window.location.href = LOGIN_PAGE;
  }

  // Guard síncrono al cargar: si no hay token o ya expiró según el
  // reloj del cliente, ni siquiera se intenta renderizar el panel.
  const token = getToken();
  if (!token || isLocallyExpired()) {
    redirectToLogin();
  }

  function resolveApiUrl() {
    return localStorage.getItem('omnia_api_url') || 'http://localhost:8000';
  }

  window.fonsFetch = async function fonsFetch(path, options = {}) {
    const API = resolveApiUrl();
    const url = path.startsWith('http') ? path : `${API}${path}`;
    const currentToken = getToken();

    const headers = {
      ...(options.headers || {}),
      Authorization: `Bearer ${currentToken}`,
    };

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
      // El backend rechazó el token (expirado o inválido del lado
      // del servidor, aunque el cliente creyera que seguía vigente).
      redirectToLogin();
      throw new Error('Sesión expirada');
    }

    return response;
  };

  window.fonsLogout = function fonsLogout() {
    redirectToLogin();
  };
})();