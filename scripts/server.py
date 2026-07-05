from flask import Flask, request, jsonify, send_from_directory, url_for, make_response
from flask_cors import CORS  # Para permitir peticiones desde el frontend
import subprocess
import os
import shlex # Para dividir comandos de forma segura
import tempfile
import shutil
import base64
import re
import time
from datetime import datetime

# Directorio raíz del proyecto (donde está index.html)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Carpeta base donde están los scripts Python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=os.path.join(PROJECT_ROOT, 'static'))

@app.route('/')
def index():
    """Sirve el archivo index.html desde la raíz del proyecto"""
    return send_from_directory(PROJECT_ROOT, 'index.html')

# Ruta para servir archivos estáticos (CSS, JS, imágenes)
@app.route('/static/<path:filename>')
def static_files(filename):
    """Sirve archivos estáticos desde la carpeta static/"""
    return send_from_directory(
        os.path.join(PROJECT_ROOT, 'static'), 
        filename,
        conditional=True
    )

# Almacén de scripts detectados automáticamente (se actualiza en cada petición)
SCRIPT_MAP = {}  # { script_id: {"file": ..., "deps": [...]} }

def parse_metadata(filepath):
    """Lee los metadatos embebidos como comentarios YAML al inicio de un archivo Python.
    
    Formato esperado:
    # --- METADATA ---
    # name: Nombre del Script
    # description: Descripción del script
    # category: Categoría
    # status: Activo
    # version: 1.0.0
    # icon: file-code-2
    # tags: Tag1,Tag2,Tag3
    # dependencies: dep1,dep2,dep3
    # command: python script.py <args>
    # requires_upload: true/false
    # --- END METADATA ---
    
    Si no se encuentra el bloque de metadatos, se generan valores por defecto.
    """
    defaults = {
        'name': os.path.splitext(os.path.basename(filepath))[0].title(),
        'description': f"Herramienta en Python para {os.path.splitext(os.path.basename(filepath))[0]}",
        'category': 'Utilidades',
        'status': 'Activo',
        'version': '1.0.0',
        'icon': 'file-code-2',
        'tags': ['Python'],
        'dependencies': [],
        'command': f"python {os.path.basename(filepath)}",
        'requires_upload': False,
    }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = []
            metadata_started = False
            for line in f:
                stripped = line.strip()
                if not metadata_started:
                    if stripped == '# --- METADATA ---':
                        metadata_started = True
                        continue
                    elif stripped.startswith('#'):
                        # Comentarios antes del bloque de metadatos, se ignoran
                        continue
                    else:
                        # Fin de comentarios sin bloque de metadatos
                        break
                
                if stripped == '# --- END METADATA ---':
                    break
                if stripped.startswith('# '):
                    lines.append(stripped[2:])  # Quitar "# " del inicio
        
        # Parsear las líneas de metadatos
        for line in lines:
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'name':
                defaults['name'] = value
            elif key == 'description':
                defaults['description'] = value
            elif key == 'category':
                defaults['category'] = value
            elif key == 'status':
                defaults['status'] = value
            elif key == 'version':
                defaults['version'] = value
            elif key == 'icon':
                defaults['icon'] = value
            elif key == 'tags':
                # Tags separados por comas
                defaults['tags'] = [t.strip() for t in value.split(',') if t.strip()]
            elif key == 'dependencies':
                # Dependencias separadas por comas
                defaults['dependencies'] = [d.strip() for d in value.split(',') if d.strip()]
            elif key == 'command':
                defaults['command'] = value
            elif key == 'requires_upload':
                defaults['requires_upload'] = value.lower() in ('true', 'yes', '1')

    except Exception as e:
        print(f"Error leyendo metadatos de {filepath}: {e}")

    return defaults

def scan_scripts_directory():
    """Escanea el directorio scripts/ y detecta todos los archivos .py.
    
    Para cada archivo encontrado, lee los metadatos embebidos y actualiza SCRIPT_MAP.
    Esto permite que cualquier nuevo script añadido al directorio sea automáticamente disponible.
    """
    global SCRIPT_MAP
    SCRIPT_MAP = {}
    
    try:
        py_files = [f for f in os.listdir(BASE_DIR) if f.endswith('.py') and f != 'server.py']
    except Exception as e:
        print(f"Error escaneando directorio scripts/: {e}")
        return

    script_id = 1
    for filename in sorted(py_files):
        filepath = os.path.join(BASE_DIR, filename)
        
        if not os.path.isfile(filepath):
            continue
        
        metadata = parse_metadata(filepath)
        
        SCRIPT_MAP[script_id] = {
            "file": filename,
            "deps": metadata['dependencies'],
            "metadata": metadata
        }
        script_id += 1

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Recibe un archivo subido desde el frontend y lo guarda en una carpeta temporal"""
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió ningún archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400

    # Crear carpeta temporal para el archivo subido
    temp_dir = tempfile.mkdtemp(prefix="pyweb_upload_")
    
    # Guardar el archivo en la carpeta temporal
    filepath = os.path.join(temp_dir, file.filename)
    file.save(filepath)
    
    return jsonify({
        'success': True,
        'filename': file.filename,
        'filepath': filepath,
        'temp_dir': temp_dir
    })

# Directorio para entornos virtuales persistentes por script
_VENV_DIR = os.path.join(PROJECT_ROOT, ".venvs")

def cleanup_old_venvs():
    """Elimina los entornos virtuales persistentes que no se han usado en más de 7 días.
    
    Esto evita acumulación de espacio en disco cuando scripts son eliminados o modificados.
    Se llama automáticamente cada vez que se ejecuta un script.
    """
    try:
        if not os.path.isdir(_VENV_DIR):
            return
        now = time.time()
        for item in os.listdir(_VENV_DIR):
            venv_path = os.path.join(_VENV_DIR, item)
            if not os.path.isdir(venv_path):
                continue
            # Usar el tiempo de acceso del directorio para determinar si está en uso
            atime = os.path.getatime(venv_path)
            days_since_access = (now - atime) / 86400
            if days_since_access > 7:
                print(f"[VENV] Eliminando entorno virtual antiguo: {item} ({days_since_access:.1f} días sin uso)")
                shutil.rmtree(venv_path, ignore_errors=True)
    except Exception as e:
        print(f"[VENV] Error en limpieza automática: {e}")

def _get_persistent_venv_path(script_filename):
    """Obtiene la ruta del entorno virtual persistente para un script dado."""
    # Usar hash de las dependencias en el nombre para invalidar cuando cambian
    return os.path.join(_VENV_DIR, f"{script_filename}_venv")

def _ensure_venv_exists(venv_path):
    """Crea el entorno virtual si no existe ya."""
    if not os.path.isdir(os.path.join(venv_path, "bin")):
        os.makedirs(os.path.dirname(venv_path), exist_ok=True)
        subprocess.run(
            ["python3", "-m", "venv", venv_path],
            check=True,
            capture_output=True
        )

def get_venv_python(venv_path):
    """Obtiene la ruta del ejecutable Python dentro del entorno virtual."""
    if os.name == 'nt':  # Windows
        return os.path.join(venv_path, "Scripts", "python.exe")
    else:  # Linux/Mac
        return os.path.join(venv_path, "bin", "python")

def install_deps_if_needed(venv_python, dependencies):
    """Instala las dependencias en el entorno virtual usando pip solo si es necesario.
    
    Verifica cada dependencia antes de instalarla para evitar reinstalaciones innecesarias.
    """
    if not dependencies:
        return
    # Verificar qué dependencias ya están instaladas
    missing = []
    for dep in dependencies:
        check_cmd = [venv_python, "-c", f"import {dep.split('>=')[0].split('<=' )[0].split('==')[0].strip()}"]
        result = subprocess.run(check_cmd, capture_output=True)
        if result.returncode != 0:
            missing.append(dep)
    
    if not missing:
        return
    
    pip_cmd = [venv_python, "-m", "pip", "install", "--quiet"] + missing
    result = subprocess.run(
        pip_cmd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Error instalando dependencias {missing}: {result.stderr}")

def cleanup_venv(venv_path):
    """Elimina el entorno virtual (usado solo para limpieza manual)."""
    try:
        shutil.rmtree(venv_path)
    except Exception:
        pass  # Ignorar errores de limpieza

@app.route('/api/execute', methods=['POST'])
def execute_script():
    """Ejecuta un script Python en un entorno virtual temporal y devuelve la salida"""
    data = request.json
    
    script_id = data.get('script_id')
    command_str = data.get('command', '')  # Recibe el comando desde el frontend
    uploaded_file_path = data.get('uploaded_file_path', None)  # Ruta del archivo subido (si existe)

    if not script_id or script_id not in SCRIPT_MAP:
        return jsonify({'error': 'Script no encontrado'}), 404

    script_info = SCRIPT_MAP[script_id]
    filename = script_info["file"]
    dependencies = script_info.get("deps", [])
    script_path = os.path.join(BASE_DIR, filename)
    
    # Si se envió un comando desde el frontend, usarlo. Si no, ejecutar solo el archivo.
    metadata = script_info.get("metadata", {})
    requires_upload = metadata.get('requires_upload', False)
    
    if command_str:
        cmd = shlex.split(command_str)
        
        # DEBUG logging
        print(f"[DEBUG] command_str='{command_str}'")
        print(f"[DEBUG] cmd after split={cmd}")
        print(f"[DEBUG] requires_upload={requires_upload}")
        print(f"[DEBUG] uploaded_file_path={uploaded_file_path}")
        if uploaded_file_path:
            print(f"[DEBUG] os.path.exists(uploaded_file_path)={os.path.exists(uploaded_file_path)}")
        
        # Si el script requiere upload y hay un archivo subido, reemplazar placeholders
        # como <archivo>, <input>, <file> por la ruta real del archivo subido
        if requires_upload and uploaded_file_path and os.path.exists(uploaded_file_path):
            for i, arg in enumerate(cmd):
                # Reemplazar placeholders comunes de ruta de archivo
                if arg.lower() in ('<archivo>', '<input>', '<file>', '<archivos>'):
                    cmd[i] = uploaded_file_path
        elif not requires_upload:
            pass  # Script sin upload, usar comando tal cual
        
        print(f"[DEBUG] cmd after step1 replacement={cmd}")
    else:
        cmd = ['python3', script_path]

    # Usar entorno virtual persistente (reutilizado entre ejecuciones del mismo script)
    venv_path = _get_persistent_venv_path(filename)
    
    try:
        # 1. Asegurar que el entorno virtual existe
        os.makedirs(os.path.dirname(venv_path), exist_ok=True)
        _ensure_venv_exists(venv_path)
        venv_python = get_venv_python(venv_path)
        
        # 2. Instalar dependencias solo si faltan (mucho más rápido que reinstalar siempre)
        install_deps_if_needed(venv_python, dependencies)

        # 3. Si hay un archivo subido, copiarlo al directorio del venv para que sea accesible
        if uploaded_file_path and os.path.exists(uploaded_file_path):
            uploads_dir = os.path.join(venv_path, "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            dest_path = os.path.join(uploads_dir, os.path.basename(uploaded_file_path))
            shutil.copy2(uploaded_file_path, dest_path)
            # Actualizar el comando para usar la ruta del archivo copiado en el venv
            # Solo reemplazar argumentos que son rutas de archivos con extensiones conocidas (índice > 1)
            for i, arg in enumerate(cmd):
                if i > 1 and any(ext in arg.lower() for ext in ['.pdf', '.jpg', '.jpeg', '.png', '.webp']):
                    cmd[i] = dest_path

        # Reemplazar 'python3' o 'python' por el Python del entorno virtual
        if cmd[0] in ('python', 'python3'):
            cmd[0] = venv_python
        
        print(f"[DEBUG] Final cmd before subprocess={cmd}")

        # Timeout configurable: 180s para dar tiempo a descargas de modelos (primera ejecución)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=os.path.dirname(script_path)
        )

        output_lines = []
        
        # Salida estándar (éxito)
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip(): # Evitar líneas vacías en la consola
                    output_lines.append({'type': 'info', 'text': line})
        
        # Errores
        if result.stderr:
            for line in result.stderr.split('\n'):
                if line.strip():
                    output_lines.append({'type': 'error', 'text': line})

        return jsonify({
            'success': True,
            'exit_code': result.returncode,
            'output': output_lines,
            'command': ' '.join(cmd)
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'El script excedió el tiempo de espera (180s)'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Limpieza automática de venvs antiguos (no usados en >7 días)
        cleanup_old_venvs()


# Archivo persistente para categorías
CATEGORIES_FILE = os.path.join(BASE_DIR, 'categories.json')

# Cargar categorías desde el archivo si existe, sino usar valores por defecto
DEFAULT_CATEGORIES = ['Utilidades', 'IA', 'Automatización']
CATEGORIES = list(DEFAULT_CATEGORIES)

if os.path.exists(CATEGORIES_FILE):
    try:
        with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            CATEGORIES = data.get('categories', list(DEFAULT_CATEGORIES))
    except Exception as e:
        print(f"Error leyendo categories.json: {e}")

# Función para guardar categorías en el archivo
def save_categories():
    """Guarda la lista actual de categorías en categories.json."""
    try:
        with open(CATEGORIES_FILE, 'w', encoding='utf-8') as f:
            json.dump({"categories": CATEGORIES}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando categories.json: {e}")


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Devuelve la lista de categorías disponibles."""
    return jsonify(CATEGORIES)

@app.route('/api/categories', methods=['POST'])
def add_category():
    """Añade una nueva categoría si no existe ya."""
    data = request.json
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'El nombre de la categoría es obligatorio'}), 400
    
    if name in CATEGORIES:
        return jsonify({'error': 'La categoría ya existe'}), 409
    
    CATEGORIES.append(name)
    # Ordenar alfabéticamente
    CATEGORIES.sort()
    save_categories()
    
    return jsonify({'success': True, 'categories': CATEGORIES}), 201

@app.route('/api/categories/<category>', methods=['DELETE'])
def delete_category(category):
    """Elimina una categoría si no está en uso por ningún script."""
    category = category.strip()
    
    if category not in CATEGORIES:
        return jsonify({'error': 'Categoría no encontrada'}), 404
    
    # Verificar que ningún script usa esta categoría
    for sid, info in SCRIPT_MAP.items():
        metadata = info.get("metadata", {})
        if metadata.get('category') == category:
            return jsonify({'error': f'No se puede eliminar: hay scripts usando "{category}"'}), 400
    
    CATEGORIES.remove(category)
    return jsonify({'success': True, 'categories': CATEGORIES})

@app.route('/api/scripts/<int:script_id>/category', methods=['PUT'])
def update_script_category(script_id):
    """Actualiza la categoría de un script en su archivo Python."""
    if not script_id or script_id not in SCRIPT_MAP:
        return jsonify({'error': 'Script no encontrado'}), 404
    
    data = request.json
    new_category = data.get('category', '').strip()
    
    if not new_category:
        return jsonify({'error': 'La categoría es obligatoria'}), 400
    
    script_info = SCRIPT_MAP[script_id]
    filename = script_info["file"]
    filepath = os.path.join(BASE_DIR, filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Buscar y reemplazar la línea de category en el bloque de metadatos
        metadata_started = False
        modified = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == '# --- METADATA ---':
                metadata_started = True
                continue
            if stripped == '# --- END METADATA ---':
                break
            
            if metadata_started and stripped.startswith('# category:'):
                lines[i] = f'# category: {new_category}\n'
                modified = True
        
        if not modified:
            return jsonify({'error': 'No se encontró el campo category en los metadatos del script'}), 400
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        # Reescanear para actualizar SCRIPT_MAP con la nueva categoría
        scan_scripts_directory()
        
        return jsonify({'success': True, 'category': new_category})
    
    except Exception as e:
        print(f"Error actualizando categoría de {filename}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update_status', methods=['POST'])
def update_status():
    """Actualiza el estado (status) de un script en su archivo Python.
    
    El nuevo estado se escribe directamente en el bloque de metadatos del archivo,
    reemplazando la línea # status: <valor> por # status: <nuevo_valor>.
    
    Estados válidos: Activo, En desarrollo, Descontinuado
    """
    VALID_STATUSES = ['Activo', 'En desarrollo', 'Descontinuado']
    
    data = request.json
    script_id = data.get('script_id')
    new_status = data.get('status', '').strip()
    
    if not script_id or script_id not in SCRIPT_MAP:
        return jsonify({'error': 'Script no encontrado'}), 404
    
    if new_status not in VALID_STATUSES:
        return jsonify({'error': f'Estado inválido. Opciones válidas: {", ".join(VALID_STATUSES)}'}), 400
    
    script_info = SCRIPT_MAP[script_id]
    filename = script_info["file"]
    filepath = os.path.join(BASE_DIR, filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Buscar y reemplazar la línea de status en el bloque de metadatos
        metadata_started = False
        modified = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == '# --- METADATA ---':
                metadata_started = True
                continue
            if stripped == '# --- END METADATA ---':
                break
            
            if metadata_started and stripped.startswith('# status:'):
                lines[i] = f'# status: {new_status}\n'
                modified = True
        
        if not modified:
            return jsonify({'error': 'No se encontró el campo status en los metadatos del script'}), 400
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        # Reescanear para actualizar SCRIPT_MAP con el nuevo estado
        scan_scripts_directory()
        
        return jsonify({'success': True, 'status': new_status})
    
    except Exception as e:
        print(f"Error actualizando status de {filename}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/scripts')
def get_scripts():
    """Devuelve la lista de scripts disponibles escaneando el directorio scripts/.
    
    Cada vez que se llama a esta ruta, se reescanea el directorio para detectar
    nuevos scripts añadidos automáticamente. Esto permite que al subir un script
    al directorio, su información aparezca sin necesidad de reiniciar el servidor.
    """
    # Escanear y actualizar la lista de scripts en cada petición
    scan_scripts_directory()
    
    script_list = []
    
    for script_id, info in SCRIPT_MAP.items():
        filename = info["file"]
        metadata = info.get("metadata", {})
        
        script_list.append({
            'id': script_id,
            'nombre': metadata.get('name', filename.replace('.py', '').title()),
            'descripcion': metadata.get('description', f"Herramienta en Python para {filename.replace('.py', '')}"),
            'categoria': metadata.get('category', 'Utilidades'),
            'estado': metadata.get('status', 'Activo'),
            'version': metadata.get('version', '1.0.0'),
            'autor': 'DevSenior',
            'fecha': datetime.now().strftime('%Y-%m-%d'),  # Fecha de detección del script
            'icono': metadata.get('icon', 'file-code-2'),
            'tags': metadata.get('tags', ['Python']),
            'dependencias': info.get("deps", []),
            'comando': metadata.get('command', f"python {filename}"),
            'ruta': f"./scripts/{filename}/",
            'github': "",
            'requires_upload': metadata.get('requires_upload', False)
        })

    response = make_response(jsonify(script_list))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


# Habilitar CORS para permitir peticiones desde el frontend
CORS(app)

if __name__ == '__main__':
    # Usar 0.0.0.0 para permitir conexiones desde cualquier IP (necesario si usas proxy o nginx)
    app.run(host='127.0.0.1', port=5000, debug=True)