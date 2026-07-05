// --- Estado Global ---
let scripts = [];
let currentCategory = "Todos";
let searchQuery = "";
let sortOption = "date_desc";
let currentScriptId = null;
let isExecuting = false;
let uploadedFilePath = null;
let refreshInterval = null;

// --- Inicialización ---
document.addEventListener('DOMContentLoaded', async () => {
    initLucideIcons();
    setupEventListeners();
    
    // Cargar categorías conocidas desde el backend
    await loadCategories();
    
    // Cargar scripts desde la API del backend
    await loadScripts();
    
    // Configurar refresco automático cada 5 segundos para detectar nuevos scripts
    startAutoRefresh();
});

// --- Refresco Automático ---
function startAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    
    refreshInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/scripts');
            if (response.ok) {
                const newScriptsData = await response.json();
                const oldCount = scripts ? scripts.length : 0;
                const newCount = newScriptsData.length;
                
                // Si hay cambios en la cantidad de scripts, notificar al usuario
                if (newCount !== oldCount) {
                    showToast(`¡Nuevo script detectado! (${newCount} scripts disponibles)`, 'success');
                }
                
                scripts = newScriptsData;
                renderStats();
                renderCategories();
                renderScripts();
            }
        } catch (error) {
            console.error('Error en refresco automático:', error);
        }
    }, 5000); // Cada 5 segundos
}

async function loadScripts() {
    try {
        const response = await fetch('/api/scripts');
        if (response.ok) {
            const scriptsData = await response.json();
            scripts = scriptsData;
            renderStats();
            renderCategories();
            renderScripts();
        } else {
            console.error('Error cargando scripts:', response.status);
            alert('No se pudieron cargar los scripts. Por favor verifica que el servidor esté ejecutándose correctamente.');
        }
    } catch (error) {
        console.error('Error al conectar con la API de scripts:', error);
        alert('Error de conexión con el servidor. Asegúrate de que Flask esté corriendo en http://localhost:5000');
    }
}


function initLucideIcons() { lucide.createIcons(); }

// --- Funciones Auxiliares ---

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateStr).toLocaleDateString('es-ES', options);
}

function getStatusColor(status) {
    switch(status) {
        case 'Activo':
            return 'bg-green-500/10 text-green-400 border-green-500/20';
        case 'En desarrollo':
            return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
        case 'Descontinuado':
            return 'bg-red-500/10 text-red-400 border-red-500/20';
        default:
            return 'bg-slate-700 text-slate-300 border-slate-600';
    }
}

// --- Cambio de estado del script ---

async function updateStatus(scriptId, newStatus) {
    try {
        const response = await fetch('/api/update_status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script_id: scriptId, status: newStatus })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // Actualizar el estado en la lista global de scripts
            const script = scripts.find(s => s.id === scriptId);
            if (script) {
                script.estado = newStatus;
            }
            showToast(`Estado cambiado a "${newStatus}"`, 'success');

            // Re-renderizar para reflejar los cambios en la vista principal y estadísticas
            renderStats();
            renderScripts();
        } else {
            showToast(`Error: ${result.error}`, 'error');
        }
    } catch (err) {
        showToast(`Error de conexión: ${err.message}`, 'error');
    }
}

// Cierra cualquier menú desplegable de estado abierto al hacer clic fuera
document.addEventListener('click', (e) => {
    const openDropdown = document.querySelector('.status-dropdown.show');
    if (openDropdown && !e.target.closest('.status-badge')) {
        openDropdown.remove();
    }
});

function toggleStatusDropdown(scriptId, currentStatus, event) {
    event.stopPropagation();

    // Cerrar cualquier dropdown de estado ya abierto
    const existing = document.querySelector('.status-dropdown.show');
    if (existing) existing.remove();

    const statuses = ['Activo', 'En desarrollo', 'Descontinuado'];

    // Crear el menú desplegable
    const dropdown = document.createElement('div');
    dropdown.className = 'status-dropdown show absolute z-50 mt-1 bg-white dark:bg-cardbg border border-gray-200 dark:border-slate-600 rounded-lg shadow-xl overflow-hidden';
    dropdown.style.minWidth = '180px';

    statuses.forEach(status => {
        const btn = document.createElement('button');
        btn.className = `w-full px-3 py-2 text-sm text-left flex items-center gap-2 transition-colors ${status === currentStatus ? getStatusColor(status) : 'text-slate-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700'}`;
        btn.textContent = status;
        btn.onclick = (e) => {
            e.stopPropagation();
            if (status !== currentStatus) {
                updateStatus(scriptId, status);
            }
            dropdown.remove();
        };
        dropdown.appendChild(btn);
    });

    document.body.appendChild(dropdown);

    // Posicionar el dropdown cerca del badge clicado
    const rect = event.currentTarget.getBoundingClientRect();
    dropdown.style.top = `${rect.bottom + window.scrollY}px`;
    dropdown.style.left = `${rect.left + window.scrollX}px`;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    
    let icon, bgColor;
    switch(type) {
        case 'success':
            icon = 'check-circle';
            bgColor = 'bg-green-500/10 border-green-500/30 text-green-400';
            break;
        case 'error':
            icon = 'alert-circle';
            bgColor = 'bg-red-500/10 border-red-500/30 text-red-400';
            break;
        default:
            icon = 'info';
            bgColor = 'bg-blue-500/10 border-blue-500/30 text-blue-400';
    }
    
    toast.className = `flex items-center gap-3 px-4 py-3 rounded-lg bg-white dark:bg-cardbg border ${bgColor} shadow-lg animate-slide-in-right pointer-events-auto min-w-[300px]`;
    toast.innerHTML = `
        <i data-lucide="${icon}" class="w-5 h-5"></i>
        <span class="text-sm text-slate-700 dark:text-slate-200">${message}</span>
    `;
    
    container.appendChild(toast);
    initLucideIcons();
    
    setTimeout(() => {
        toast.classList.add('animate-slide-out-right');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    let text;
    
    if (element.tagName === 'TEXTAREA') {
        text = element.value;
    } else {
        text = element.textContent.trim();
    }

    navigator.clipboard.writeText(text).then(() => {
        showToast('Comando copiado al portapapeles', 'success');
    }).catch(err => {
        console.error('Error al copiar:', err);
        showToast('Error al copiar al portapapeles', 'error');
    });
}

// --- Setup de Event Listeners ---

function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const mobileSearchInput = document.getElementById('mobileSearchInput');
    
    if(searchInput) searchInput.addEventListener('input', (e) => { 
        searchQuery = e.target.value.toLowerCase(); 
        renderScripts(); 
    });
    
    if(mobileSearchInput) mobileSearchInput.addEventListener('input', (e) => { 
        searchQuery = e.target.value.toLowerCase(); 
        renderScripts(); 
    });
    
    document.getElementById('sortSelect').addEventListener('change', (e) => { 
        sortOption = e.target.value; 
        renderScripts(); 
    });
    
    const themeToggle = document.getElementById('themeToggle');
    if(themeToggle) {
        themeToggle.addEventListener('click', () => { 
            document.documentElement.classList.toggle('dark'); 
        });
    }
    
    // Listener para el input de archivo (solo en modal Text2Image OCR)
    const fileInput = document.getElementById('m_file_input');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const fileLabel = document.getElementById('m_file_label');
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                const sizeKB = (file.size / 1024).toFixed(1);
                fileLabel.textContent = `${file.name} (${sizeKB} KB)`;
            } else {
                fileLabel.textContent = 'Haz clic para seleccionar un archivo (PDF, JPG, PNG)';
            }
        });
    }
}

// --- Renderizado Principal ---

function renderStats() {
    const container = document.getElementById('statsContainer');
    
    // Cálculos de estadísticas
    const totalScripts = scripts.length;
    const activeScripts = scripts.filter(s => s.estado === 'Activo').length;
    const categoriesCount = new Set(scripts.map(s => s.categoria)).size;
    const lastUpdate = scripts.reduce((prev, current) => (new Date(prev.fecha) > new Date(current.fecha)) ? prev : current).fecha;

    // HTML de las tarjetas de estadísticas
    container.innerHTML = `
        ${createStatCard('Total Scripts', totalScripts, 'code-2', '#3b82f6')}
        ${createStatCard('Activos', activeScripts, 'check-circle', '#22c55e')}
        ${createStatCard('Categorías', categoriesCount, 'layers', '#06b6d4')}
        ${createStatCard('Última Actualización', formatDate(lastUpdate), 'calendar', '#f59e0b')}
    `;
}

function createStatCard(title, value, icon, color) {
    return `
        <div class="bg-gray-100 dark:bg-cardbg border border-gray-200 dark:border-slate-700/50 p-4 rounded-xl flex items-center gap-4 hover:border-${color.replace('#','')}/30 transition-colors">
            <div class="p-2 rounded-lg bg-opacity-10" style="background-color: ${color}20; color: ${color}">
                <i data-lucide="${icon}" class="w-6 h-6"></i>
            </div>
            <div>
                <p class="text-slate-500 dark:text-slate-400 text-xs font-medium uppercase tracking-wider">${title}</p>
                <h3 class="text-xl font-bold text-slate-800 dark:text-white">${value}</h3>
            </div>
        </div>
    `;
}

// Almacén de categorías conocidas (incluye las sin scripts)
let knownCategories = new Set();

async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        if (response.ok) {
            const data = await response.json();
            knownCategories = new Set(data.categories || []);
        }
    } catch (e) {
        // Si falla, usar categorías de scripts como fallback
        knownCategories = new Set(scripts.map(script => script.categoria));
    }
}

function renderCategories() {
    const container = document.getElementById('categoryFilters');
    
    // Combinar categorías de scripts con categorías conocidas (sin scripts)
    const scriptCategories = new Set(scripts.map(script => script.categoria));
    const allCategories = new Set([...scriptCategories, ...knownCategories]);
    const categoryList = ["Todos", ...Array.from(allCategories).sort()];
    
    let html = categoryList.map(cat => `
        <button onclick="filterByCategory('${cat}')" 
                class="px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border ${currentCategory === cat ? 'bg-primary text-white border-primary shadow-[0_0_10px_-3px_rgba(59,130,246,0.5)]' : 'bg-gray-100 dark:bg-slate-800/50 text-slate-600 dark:text-slate-400 border-gray-200 dark:border-slate-700 hover:border-primary dark:hover:border-slate-500 hover:text-white'}">
            ${cat}
        </button>
    `).join('');
    
    container.innerHTML = html;
}

async function addCategoryPrompt() {
    const name = window.prompt('Nombre de la nueva categoría:');
    
    if (!name || !name.trim()) return;
    
    const trimmedName = name.trim();
    
    // Verificar duplicados (case-insensitive)
    const exists = knownCategories.has(trimmedName.toLowerCase());
    if (exists) {
        showToast(`La categoría "${trimmedName}" ya existe`, 'error');
        return;
    }

    try {
        const response = await fetch('/api/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: trimmedName })
        });
        
        const data = await response.json();
        
        if (data.success) {
            knownCategories.add(trimmedName);
            showToast(`Categoría "${trimmedName}" añadida correctamente`, 'success');
            renderCategories();
            renderScripts();
            renderStats();
        } else {
            showToast(data.error || 'Error al añadir categoría', 'error');
        }
    } catch (error) {
        showToast('Error de conexión al añadir categoría', 'error');
    }
}

function filterByCategory(category) {
    currentCategory = category;
    renderCategories(); // Re-renderizar para actualizar estilos de botones
    renderScripts();
}

// --- Lógica de Scripts (Filtrado y Ordenamiento) ---

function getFilteredAndSortedScripts() {
    let filtered = scripts.filter(script => {
        const matchesCategory = currentCategory === "Todos" || script.categoria === currentCategory;
        
        // Búsqueda en nombre, descripción o tags
        const searchLower = searchQuery.toLowerCase();
        const matchesSearch = !searchQuery || 
            script.nombre.toLowerCase().includes(searchLower) || 
            script.descripcion.toLowerCase().includes(searchLower) ||
            script.tags.some(tag => tag.toLowerCase().includes(searchLower));

        return matchesCategory && matchesSearch;
    });

    // Ordenamiento
    filtered.sort((a, b) => {
        if (sortOption === 'name_asc') {
            return a.nombre.localeCompare(b.nombre);
        } else if (sortOption === 'date_desc') {
            return new Date(b.fecha) - new Date(a.fecha);
        } else if (sortOption === 'status_active') {
            // Activos primero, luego por fecha
            const statusDiff = (b.estado === 'Activo' ? 1 : 0) - (a.estado === 'Activo' ? 1 : 0);
            return statusDiff !== 0 ? statusDiff : new Date(b.fecha) - new Date(a.fecha);
        }
        return 0;
    });

    return filtered;
}

function renderScripts() {
    const grid = document.getElementById('scriptsGrid');
    const data = getFilteredAndSortedScripts();

    if (data.length === 0) {
        grid.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-500">
                <i data-lucide="search-x" class="w-16 h-16 mb-4 opacity-50"></i>
                <p>No se encontraron scripts con esos criterios.</p>
            </div>`;
        initLucideIcons();
        return;
    }

    grid.innerHTML = data.map(script => `
        <article class="bg-white dark:bg-cardbg border border-gray-200 dark:border-slate-700 rounded-xl p-5 card-hover-effect flex flex-col h-full group relative overflow-hidden">
            <!-- Decoración de fondo sutil -->
            <div class="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-bl-[100px] -mr-10 -mt-10 transition-all duration-300 group-hover:bg-primary/10"></div>

            <!-- Header Tarjeta -->
            <div class="flex justify-between items-start mb-4 relative z-10">
                <div class="w-12 h-12 rounded-lg bg-gray-100 dark:bg-slate-800 border border-gray-200 dark:border-slate-600 flex items-center justify-center text-primary group-hover:scale-110 transition-transform duration-300">
                    <i data-lucide="${script.icono}" class="w-6 h-6"></i>
                </div>
                <span class="status-badge px-2.5 py-1 rounded-full text-xs font-medium border cursor-pointer hover:opacity-80 transition-opacity relative inline-block ${getStatusColor(script.estado)}" onclick="toggleStatusDropdown(${script.id}, '${script.estado}', event)">
                    ${script.estado} <i data-lucide="chevron-down" class="w-3 h-3 inline ml-1"></i>
                </span>
            </div>

            <!-- Contenido -->
            <h3 class="text-lg font-bold text-slate-800 dark:text-white mb-2 group-hover:text-primary transition-colors">${script.nombre}</h3>
            <p class="text-slate-600 dark:text-slate-400 text-sm line-clamp-3 mb-4 flex-grow">${script.descripcion}</p>

            <!-- Tags -->
            <div class="flex flex-wrap gap-2 mb-5">
                ${script.tags.map(tag => `<span class="px-2 py-1 bg-gray-100 dark:bg-slate-800/50 text-xs text-slate-600 dark:text-slate-300 rounded border border-gray-200 dark:border-slate-700">${tag}</span>`).join('')}
            </div>

            <!-- Footer Tarjeta -->
            <div class="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-slate-800 mt-auto">
                <span class="text-xs text-slate-500 font-mono">v${script.version}</span>
                
                <div class="flex gap-2">
                    <button onclick="openModal(${script.id})" class="p-2 rounded-lg bg-primary/10 text-primary hover:bg-primary hover:text-white transition-all" title="Ver detalles">
                        <i data-lucide="eye" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>
        </article>
    `).join('');

    initLucideIcons(); // Re-inicializar iconos en el nuevo HTML
}

// --- Modal Lógica (UNIFICADA Y CORREGIDA) ---

function openModal(id) {
    const script = scripts.find(s => s.id === id);
    if (!script) return;

    currentScriptId = script.id;  // Guardar ID actual para la ejecución

    // Rellenar datos básicos
    document.getElementById('m_icon').innerHTML = `<i data-lucide="${script.icono}" class="w-8 h-8"></i>`;
    document.getElementById('m_title').textContent = script.nombre;
    document.getElementById('m_version').textContent = `v${script.version}`;
    document.getElementById('m_date').textContent = formatDate(script.fecha);
    document.getElementById('m_description').textContent = script.descripcion;
    
    // Dependencias
    const depList = document.getElementById('m_dependencies');
    if (script.dependencias && Array.isArray(script.dependencias)) {
        depList.innerHTML = script.dependencias.map(dep => `<li class="text-slate-700 dark:text-slate-300 text-sm font-mono">• ${dep}</li>`).join('');
    } else {
        depList.innerHTML = '<li class="text-slate-400 dark:text-slate-500 text-sm font-mono">N/A</li>';
    }

    // Tags
    const tagsContainer = document.getElementById('m_tags');
    if (script.tags && Array.isArray(script.tags)) {
        tagsContainer.innerHTML = script.tags.map(tag => 
            `<span class="px-2 py-1 bg-primary/10 text-primary text-xs rounded border border-primary/20">${tag}</span>`
        ).join('');
    } else {
        tagsContainer.innerHTML = '';
    }

    // Comandos
    document.getElementById('m_install_cmd').textContent = `pip install ${script.dependencias ? script.dependencias.join(' ') : ''}`;

    // Mostrar/ocultar sección de subida de archivos según requires_upload del script
    const fileUploadSection = document.getElementById('m_file_upload_section');
    if (script.requires_upload) {
        fileUploadSection.classList.remove('hidden');
    } else {
        fileUploadSection.classList.add('hidden');
    }

    // Resetear el input de archivo al abrir el modal
    const fileInput = document.getElementById('m_file_input');
    const fileLabel = document.getElementById('m_file_label');
    if (fileInput) fileInput.value = '';
    if (fileLabel) fileLabel.textContent = 'Haz clic para seleccionar un archivo (PDF, JPG, PNG)';

    // Links GitHub
    const githubLink = document.getElementById('m_github_link');
    if (script.github) {
        githubLink.href = script.github;
        githubLink.classList.remove('hidden');
    } else {
        githubLink.classList.add('hidden');
    }

    // Resetear consola al abrir el modal para que esté limpia
    resetConsole();

    // Mostrar Modal con animación
    const modal = document.getElementById('scriptModal');
    const content = document.getElementById('modalContent');
    
    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        content.classList.remove('scale-95');
        content.classList.add('scale-100');
    }, 10);

    initLucideIcons(); // Iconos dentro del modal
}

function closeModal() {
    const modal = document.getElementById('scriptModal');
    const content = document.getElementById('modalContent');

    modal.classList.add('opacity-0');
    content.classList.remove('scale-100');
    content.classList.add('scale-95');

    setTimeout(() => {
        modal.classList.add('hidden');
        currentScriptId = null; // Limpiar ID al cerrar
    }, 300); 
}

function resetConsole() {
    const consoleSection = document.getElementById('m_console_section');
    const consoleOutput = document.getElementById('m_console_output');
    
    if (consoleSection) {
        consoleSection.classList.add('hidden');
    }
    if (consoleOutput) {
        consoleOutput.innerHTML = '';
    }
}

// ===== FUNCIÓN DE EJECUCIÓN CON CONSOLA =====

async function executeScript() {
    const btn = document.getElementById('m_run_btn');
    const consoleSection = document.getElementById('m_console_section');
    const consoleOutput = document.getElementById('m_console_output');

    if (isExecuting) return;  // Evitar doble ejecución
    isExecuting = true;

    // Obtener el script actual
    const script = scripts.find(s => s.id === currentScriptId);
    if (!script) {
        addConsoleLine('[ERROR] No se encontró el script seleccionado', 'error');
        btn.disabled = false;
        isExecuting = false;
        return;
    }

    // Usar el comando del script directamente
    const commandText = (script.comando || '').trim();
    if (!commandText) {
        addConsoleLine('[ERROR] No se encontró un comando de ejecución para este script', 'error');
        btn.disabled = false;
        isExecuting = false;
        return;
    }

    // Mostrar la sección de consola si estaba oculta
    consoleSection.classList.remove('hidden');
    
    // Actualizar el prompt con el comando del script
    const promptLine = document.getElementById('m_console_prompt');
    if (promptLine) {
        promptLine.innerHTML = `
            <span>user@host</span><span class="text-slate-500">:</span><span class="text-blue-400">~/scripts</span><span class="text-slate-500">$</span> 
            <span class="text-green-300">${commandText}</span>
        `;
    }

    // Deshabilitar botón y mostrar estado de carga
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> Ejecutando...`;
    initLucideIcons();

    addConsoleLine('Iniciando ejecución...', 'info');

    // Preparar datos para enviar al servidor
    const payload = {
        script_id: currentScriptId,
        command: commandText
    };

    // Si el script requiere subida de archivos, subir el archivo antes de ejecutar
    let filePathToSend = null;
    if (script.requires_upload) {
        const fileInput = document.getElementById('m_file_input');
        if (!fileInput || !fileInput.files.length) {
            addConsoleLine('[ERROR] Selecciona un archivo antes de ejecutar', 'error');
            btn.disabled = false;
            isExecuting = false;
            return;
        }

        // Subir el archivo al servidor antes de ejecutar
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
            addConsoleLine('Subiendo archivo...', 'info');
            const uploadResponse = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                const uploadError = await uploadResponse.json();
                throw new Error(uploadError.error || 'Error al subir el archivo');
            }

            const uploadResult = await uploadResponse.json();
            filePathToSend = uploadResult.filepath;
            addConsoleLine(`Archivo subido: ${uploadResult.filename}`, 'success');
        } catch (err) {
            addConsoleLine(`[ERROR] Error al subir el archivo: ${err.message}`, 'error');
            btn.disabled = false;
            isExecuting = false;
            return;
        }
    }

    // Incluir la ruta del archivo subido en el payload
    if (filePathToSend) {
        payload.uploaded_file_path = filePathToSend;
    }

    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // result.output es un array de objetos {type, text}
            if (Array.isArray(result.output)) {
                result.output.forEach(item => {
                    addConsoleLine(item.text, item.type || 'output');
                });
            } else {
                addConsoleLine(String(result.output), 'output');
            }
            addConsoleLine('Proceso finalizado con éxito.', 'success');
        } else {
            addConsoleLine(`[ERROR] ${result.error || 'Error desconocido al ejecutar el script.'}`, 'error');
        }

    } catch (err) {
        addConsoleLine(`[ERROR] No se pudo conectar con el servidor: ${err.message}`, 'error');
    } finally {
        // Restaurar botón
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="play-circle" class="w-4 h-4"></i> Ejecutar Script`;
        isExecuting = false;
        initLucideIcons();

        // Scroll al final de la consola
        const consoleDiv = document.getElementById('m_console');
        if (consoleDiv) {
            consoleDiv.scrollTop = consoleDiv.scrollHeight;
        }
    }
}

// --- Función para añadir líneas a la consola ---

function addConsoleLine(text, type = 'output') {
    const consoleOutput = document.getElementById('m_console_output');
    if (!consoleOutput) return;
    
    const line = document.createElement('div');
    
    // Colores según tipo de mensaje
    switch(type) {
        case 'error':
            line.className = 'text-red-400';
            break;
        case 'success':
            line.className = 'text-green-400';
            break;
        case 'info':
            line.className = 'text-yellow-400';
            break;
        default:
            line.className = 'text-slate-300';
    }

    line.textContent = text;
    consoleOutput.appendChild(line);
}