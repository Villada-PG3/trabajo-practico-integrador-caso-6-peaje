/**
 * Lógica del panel de operador de peaje: sesión, cobro e impresión de tickets.
 */
// Turno abierto que devolvió el servidor (se carga al iniciar la página)
let turnoActual = null;
// Evita emitir dos tickets si el operador hace doble clic en un botón
let emitiendo = false;

// Se ejecuta cuando todo el HTML terminó de cargarse en pantalla
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Conecta el evento de subida de imagen
    const inputImagen = document.getElementById('imagen-patente');
    if (inputImagen) {
        inputImagen.addEventListener('change', procesarImagenSubida);
    }

    // 2. Verifica con el servidor que haya un turno abierto
    const hayTurno = await inicializarDatosSesion();
    if (!hayTurno) return;

    // 3. Arma los botones de categoría con las tarifas de la base
    await cargarTarifas();
});

// Pregunta al servidor por el turno abierto y completa legajo/casilla en el navbar
async function inicializarDatosSesion() {
    const res = await apiFetch('/api/turnos/actual/');

    if (res.status === 404) {
        // No hay turno abierto: hay que abrir uno antes de cobrar
        window.location.href = '/apertura-turno/';
        return false;
    }
    if (!res.ok) {
        alert(mensajeError(res));
        return false;
    }

    turnoActual = res.data.turno;
    localStorage.setItem('legajo', turnoActual.legajo);

    const lblLegajo = document.getElementById('lbl-legajo');
    const lblCasilla = document.getElementById('lbl-casilla');
    if (lblLegajo) lblLegajo.textContent = turnoActual.legajo;
    if (lblCasilla) lblCasilla.textContent = String(turnoActual.casilla_numero).padStart(2, '0');
    return true;
}

// Crea un botón por cada categoría con su tarifa vigente
async function cargarTarifas() {
    const grid = document.getElementById('categories-grid');
    const res = await apiFetch('/api/tarifas/');

    grid.innerHTML = '';
    if (!res.ok || res.data.tarifas.length === 0) {
        grid.innerHTML = '<div class="col-12 text-center text-danger py-4">No hay tarifas vigentes cargadas.</div>';
        return;
    }

    res.data.tarifas.forEach(t => {
        const col = document.createElement('div');
        col.className = 'col-md-6';

        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'btn btn-category w-100 p-3 text-start d-flex align-items-center justify-content-between';
        boton.addEventListener('click', () => emitirTicket(t.categoria_id));

        const izquierda = document.createElement('div');
        izquierda.className = 'd-flex align-items-center';

        const badge = document.createElement('span');
        badge.className = 'badge-cat me-3';
        badge.textContent = t.categoria_id;

        const nombre = document.createElement('div');
        nombre.className = 'fw-bold';
        nombre.textContent = t.nombre;

        const precio = document.createElement('span');
        precio.className = 'price-tag';
        precio.textContent = '$' + parseFloat(t.monto).toFixed(0);

        izquierda.appendChild(badge);
        izquierda.appendChild(nombre);
        boton.appendChild(izquierda);
        boton.appendChild(precio);
        col.appendChild(boton);
        grid.appendChild(col);
    });
}

// Procesa la imagen subida con la IA (Tesseract)
async function procesarImagenSubida(event) {
    const file = event.target.files[0];
    if (!file) return;

    const imgPreview = document.getElementById('preview-imagen');
    const placeholder = document.getElementById('preview-placeholder');
    const loadingIndicator = document.getElementById('ocr-loading');
    
    // Este es el input donde dice "AA123CD / ABC123" en tu pantalla
    const inputPatente = document.getElementById('patente-input');

    // 1. Mostrar vista previa de la foto
    imgPreview.src = URL.createObjectURL(file);
    imgPreview.classList.remove('d-none');
    if (placeholder) placeholder.classList.add('d-none');

    // 2. Activar aviso de carga
    if (loadingIndicator) loadingIndicator.classList.remove('d-none');
    
    // Cambia el placeholder visualmente mientras piensa
    inputPatente.value = "LEYENDO...";

    try {
        // 3. Ejecutar Tesseract OCR sobre la foto
        const result = await Tesseract.recognize(file, 'eng', {
            tessedit_char_whitelist: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        });

        const textoDetectado = result.data.text;
        const patenteLimpia = extraerFormatoPatente(textoDetectado);

        // 4. Reescribir el valor en el input
        if (patenteLimpia) {
            // Éxito total: Formato perfecto detectado
            inputPatente.value = patenteLimpia;
        } else {
            // Éxito parcial: Agarra lo que pudo leer, limpia los espacios y lo pega en el input
            const textoCrudo = textoDetectado.replace(/[^A-Z0-9]/gi, '').substring(0, 7);
            inputPatente.value = textoCrudo || "";
            
            if (!textoCrudo) {
                alert("La foto no es clara. Por favor, escriba la patente a mano.");
            }
        }
    } catch (error) {
        console.error("Error al procesar OCR:", error);
        inputPatente.value = "";
        alert("Error técnico al cargar la IA. Revisa la consola con F12.");
    } finally {
        // Ocultar mensaje de carga al terminar
        if (loadingIndicator) loadingIndicator.classList.add('d-none');
    }
}

// Filtra el texto detectado buscando patentes argentinas válidas
function extraerFormatoPatente(texto) {
    if (!texto) return null;
    
    // Limpia espacios y caracteres especiales
    const limpio = texto.replace(/[^A-Z0-9]/gi, '').toUpperCase();

    // Patrón Mercosur: AA123CD
    const matchMercosur = limpio.match(/[A-Z]{2}\d{3}[A-Z]{2}/);
    if (matchMercosur) return matchMercosur[0];

    // Patrón Tradicional: ABC123
    const matchTradicional = limpio.match(/[A-Z]{3}\d{3}/);
    if (matchTradicional) return matchTradicional[0];

    return null;
}

// Emite el ticket: PRIMERO lo guarda en la base de datos y solo si se guardó lo muestra
async function emitirTicket(idCategoria) {
    if (emitiendo) return;
    emitiendo = true;

    const patenteInput = document.getElementById('patente-input');
    const patente = (patenteInput && patenteInput.value.trim()) ? patenteInput.value.trim().toUpperCase() : '';

    let res;
    try {
        res = await apiFetch('/api/ventas/', {
            method: 'POST',
            body: { categoria_id: idCategoria, patente: patente }
        });
    } catch (err) {
        res = { ok: false, status: 0, data: { detail: 'No se pudo conectar con el servidor. La venta NO se registró.' } };
    }
    emitiendo = false;

    if (!res.ok) {
        // Sin registro en la base no se emite el ticket
        alert('No se pudo registrar la venta: ' + mensajeError(res));
        if (res.status === 409) window.location.href = '/apertura-turno/';
        return;
    }

    const venta = res.data;
    const importe = parseFloat(venta.importe);

    // Rellenar Modal del Ticket con los datos que confirmó el servidor
    document.getElementById('tkn-numero').textContent = venta.ticket;
    document.getElementById('tkn-fecha').textContent = new Date(venta.fecha_hora_emision).toLocaleString();
    document.getElementById('tkn-categoria').textContent = venta.categoria;
    document.getElementById('tkn-patente').textContent = venta.patente;
    document.getElementById('tkn-importe').textContent = `$${importe.toFixed(2)}`;
    document.getElementById('tkn-casilla').textContent = String(venta.casilla_numero).padStart(2, '0');
    document.getElementById('tkn-legajo').textContent = venta.legajo;

    // Generar imagen del Código QR
    const qrData = encodeURIComponent(`TICKET:${venta.ticket}|Monto:${venta.importe}|Patente:${venta.patente}`);
    document.getElementById('qr-img').src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${qrData}`;

    // Desplegar Modal en pantalla
    const ticketModal = new bootstrap.Modal(document.getElementById('ticketModal'));
    ticketModal.show();

    // Limpiar input de patente (y la foto) para la siguiente operación
    if (patenteInput) patenteInput.value = '';
    const inputImagen = document.getElementById('imagen-patente');
    if (inputImagen) inputImagen.value = '';
    const imgPreview = document.getElementById('preview-imagen');
    const placeholder = document.getElementById('preview-placeholder');
    if (imgPreview) { imgPreview.classList.add('d-none'); imgPreview.src = ''; }
    if (placeholder) placeholder.classList.remove('d-none');
}

// Botón "Imprimir Ticket" del modal (las reglas @media print están en styles.css)
function imprimirTicket() {
    window.print();
}