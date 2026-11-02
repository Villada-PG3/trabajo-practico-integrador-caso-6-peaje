/**
 * Utilidades compartidas para hablar con la API de Django.
 * Se carga desde base.html, así que está disponible en todas las páginas.
 */

// Lee una cookie por nombre (se usa para el token CSRF de Django)
function getCookie(name) {
    const match = document.cookie
        .split('; ')
        .find(fila => fila.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=')[1]) : null;
}

/**
 * fetch con sesión (cookies) + token CSRF + JSON.
 * Devuelve siempre { ok, status, data } y nunca lanza por un 4xx/5xx.
 * Si la sesión expiró (401) manda al login.
 */
async function apiFetch(url, { method = 'GET', body } = {}) {
    const opciones = {
        method,
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') || ''
        }
    };
    if (body !== undefined) opciones.body = JSON.stringify(body);

    const respuesta = await fetch(url, opciones);

    let data = null;
    try {
        data = await respuesta.json();
    } catch (e) {
        // La respuesta no era JSON (ej. página de error de Django)
    }

    if (respuesta.status === 401) {
        window.location.href = '/login/';
    }
    return { ok: respuesta.ok, status: respuesta.status, data };
}

// Texto de error legible a partir de una respuesta de apiFetch
function mensajeError(res) {
    if (res.data && res.data.detail) return res.data.detail;
    if (res.status === 403) return 'La sesión de seguridad venció. Recargá la página (F5) e intentá de nuevo.';
    return `Error del servidor (código ${res.status}).`;
}

// Botón "Salir" del menú superior
async function cerrarSesion() {
    try {
        await apiFetch('/api/logout/', { method: 'POST' });
    } catch (e) {
        console.warn('No se pudo avisar al servidor del cierre de sesión', e);
    }
    localStorage.clear();
    window.location.href = '/login/';
}