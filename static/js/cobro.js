/**
 * Lógica del panel de operador de peaje: sesión, cobro e impresión de tickets.
 */
// Se ejecuta cuando todo el HTML terminó de cargarse en pantalla
document.addEventListener('DOMContentLoaded', () => {
    // 1. Inicia datos de sesión en el menú superior
    inicializarDatosSesion();

    // 2. Conecta el evento de subida de imagen
    const inputImagen = document.getElementById('imagen-patente');
    if (inputImagen) {
        inputImagen.addEventListener('change', procesarImagenSubida);
    }
});

// Carga legajo y casilla en el navbar
function inicializarDatosSesion() {
    const legajo = localStorage.getItem('legajo') || '12345';
    const turno = JSON.parse(localStorage.getItem('turno_actual') || '{}');
    
    const lblLegajo = document.getElementById('lbl-legajo');
    const lblCasilla = document.getElementById('lbl-casilla');

    if (lblLegajo) lblLegajo.textContent = legajo;
    if (lblCasilla) lblCasilla.textContent = turno.casilla || '1';
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

// Emite el ticket al presionar cualquiera de los 7 botones de categoría
async function emitirTicket(idCategoria, nombreCategoria, importe) {
    const patenteInput = document.getElementById('patente-input');
    const patente = (patenteInput && patenteInput.value.trim()) ? patenteInput.value.trim().toUpperCase() : 'S/PATENTE';
    
    const numTicket = '0004-' + Math.floor(100000 + Math.random() * 900000);
    const fechaHora = new Date().toLocaleString();

    // Guardar registro de la venta en localStorage
    const ventaData = {
        numero_ticket: numTicket,
        categoria_nombre: nombreCategoria,
        importe: importe,
        patente: patente
    };

    const ventasGuardadas = JSON.parse(localStorage.getItem('ventas_turno') || '[]');
    ventasGuardadas.push(ventaData);
    localStorage.setItem('ventas_turno', JSON.stringify(ventasGuardadas));

    // Rellenar Modal del Ticket
    document.getElementById('tkn-numero').textContent = numTicket;
    document.getElementById('tkn-fecha').textContent = fechaHora;
    document.getElementById('tkn-categoria').textContent = nombreCategoria;
    document.getElementById('tkn-patente').textContent = patente;
    document.getElementById('tkn-importe').textContent = `$${importe.toFixed(2)}`;

    // Generar imagen del Código QR
    const qrData = encodeURIComponent(`TICKET:${numTicket}|Monto:${importe}|Patente:${patente}`);
    document.getElementById('qr-img').src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${qrData}`;

    // Desplegar Modal en pantalla
    const ticketModal = new bootstrap.Modal(document.getElementById('ticketModal'));
    ticketModal.show();

    // Limpiar input de patente para la siguiente operación
    if (patenteInput) patenteInput.value = '';
}