# PyScripts — Dashboard Profesional de Scripts Python

Panel centralizado para visualizar, ejecutar y gestionar herramientas desarrolladas en Python. Automatización, IA y más.

## Descripción

PyScripts es una aplicación web que permite:

- **Descubrir** todos los scripts Python disponibles a través de un dashboard visual con tarjetas interactivas.
- **Ejecutar** scripts directamente desde el navegador con una consola integrada en tiempo real.
- **Gestionar** categorías, estados y metadatos sin tocar código.
- **Subir archivos** para scripts que lo requieran (OCR, análisis de imágenes).

Cada script incluye un bloque de metadatos embebido en formato YAML que describe su nombre, descripción, categoría, versión, icono, tags, dependencias y comando de ejecución. El servidor escanea automáticamente el directorio `scripts/` y detecta cualquier nuevo script añadido.

## Scripts incluidos

| Script | Categoría | Descripción |
|---|---|---|
| **Text2Image OCR** | OCR/Imágenes | Convierte imágenes y PDF a texto usando OCR avanzado con EasyOCR + PyMuPDF. Soporta GPU si está disponible. |
| **Img2RRSSDesc** | Redes Sociales/Marketing | Analiza una imagen y genera descripción, hashtags y tono optimizados para redes sociales (Instagram/TikTok) mediante LM Studio. |
| **Prueba Script** | Utilidades | Script de prueba básico que imprime un mensaje de saludo. |

## Arquitectura

```
pyweb app/
├── index.html              # Frontend principal (HTML + Tailwind CSS)
├── static/
│   ├── css/styles.css      # Estilos personalizados y animaciones
│   └── js/app.js           # Lógica del frontend (JS vanilla)
├── scripts/
│   ├── server.py            # Backend Flask (API REST + ejecución de scripts)
│   ├── text2image.py        # Script OCR con metadatos embebidos
│   ├── img2rrssdesc.py      # Script análisis imagen para redes sociales
│   ├── prueba.py             # Script de prueba
│   └── categories.json       # Categorías persistentes
├── data/                     # Directorio para datos adicionales
└── .gitignore
```

### Backend — Flask (`scripts/server.py`)

- **`GET /api/scripts`** — Escanea `scripts/`, parsea metadatos y devuelve la lista de scripts disponibles.
- **`POST /api/upload`** — Recibe archivos subidos desde el frontend y los guarda en un directorio temporal.
- **`POST /api/execute`** — Ejecuta un script en un entorno virtual aislado, instala dependencias si es necesario, y devuelve la salida por consola.
- **`GET /api/categories`** — Devuelve las categorías disponibles.
- **`POST /api/categories`** — Añade una nueva categoría.
- **`DELETE /api/categories/<category>`** — Elimina una categoría (solo si ningún script la usa).
- **`PUT /api/scripts/<id>/category`** — Actualiza la categoría de un script en su archivo Python.
- **`POST /api/update_status`** — Cambia el estado de un script (`Activo`, `En desarrollo`, `Descontinuado`).

### Frontend — Vanilla JS + Tailwind CSS

- Dashboard con grid responsivo, filtros por categoría, ordenamiento y búsqueda en tiempo real.
- Modal de detalle con información del script: descripción, dependencias, tags, comando de instalación.
- Consola integrada para ver la salida de ejecución en tiempo real.
- Soporte para subida de archivos (scripts que lo requieran).
- Modo claro/oscuro con persistencia en `localStorage`.

## Metadatos embebidos

Cada script debe incluir un bloque de metadatos al inicio del archivo:

```python
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
```

Campos:

| Campo | Descripción |
|---|---|
| `name` | Nombre visible del script en el dashboard |
| `description` | Descripción corta mostrada en la tarjeta |
| `category` | Categoría para filtrado (debe existir o se creará automáticamente) |
| `status` | Estado: `Activo`, `En desarrollo` o `Descontinuado` |
| `version` | Versión del script |
| `icon` | Nombre de un icono de [Lucide Icons](https://lucide.dev/icons/) |
| `tags` | Tags separados por comas para búsqueda |
| `dependencies` | Paquetes pip necesarios, separados por comas |
| `command` | Comando completo de ejecución (por defecto: `python <archivo>`)
| `requires_upload` | Si es `true`, el modal mostrará un campo para subir archivo |

## Instalación y uso

### Requisitos
- Python 3.8+
- [LM Studio](https://lmstudio.ai/) (solo para Img2RRSSDesc, con modelo de visión cargado)

### Pasos

```bash
# Clonar el repositorio
git clone https://github.com/aleperezfuente/Pyweb-App.git
cd Pyweb-App

# Instalar dependencias del servidor
pip install flask flask-cors

# Iniciar el servidor
python scripts/server.py
```

El servidor se ejecuta en `http://127.0.0.1:5000`.

### Añadir un nuevo script

1. Crea un archivo `.py` en la carpeta `scripts/` con el bloque de metadatos al inicio.
2. El servidor lo detectará automáticamente — no es necesario reiniciar.
3. Las dependencias se instalarán en un entorno virtual aislado la primera vez que ejecutes el script.

### Entornos virtuales persistentes

Cada script obtiene su propio entorno virtual en `.venvs/`. Esto garantiza:
- Aislamiento total entre scripts (sin conflictos de dependencias).
- Reutilización del venv entre ejecuciones (no se reinstala cada vez).
- Limpieza automática: los entornos no usados en más de 7 días se eliminan.

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Python, Flask, Flask-CORS |
| Frontend | HTML5, CSS3 (Tailwind CSS CDN), JavaScript vanilla |
| Iconos | Lucide Icons |
| Fuentes | Inter (Google Fonts) |
| OCR | EasyOCR + PyMuPDF + OpenCV |
| IA Visión | LM Studio (API compatible con OpenAI) |

## Licencia

MIT
