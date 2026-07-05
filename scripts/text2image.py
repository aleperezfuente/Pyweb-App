# --- METADATA ---
# name: Text2Image OCR
# description: Convierte imágenes y PDF a texto usando OCR avanzado con EasyOCR + PyMuPDF
# category: OCR/Imágenes
# status: Activo
# version: 1.0.0
# icon: scan-text
# tags: OCR,PDF,Imágenes,Texto,EasyOCR
# dependencies: easyocr,Pillow,PyMuPDF,opencv-python-headless,numpy
# command: python text2image.py <archivo>
# requires_upload: true
# --- END METADATA ---

import sys
import os
import warnings
import cv2
import numpy as np
from PIL import Image, ImageEnhance
import easyocr
import fitz  # PyMuPDF para PDFs

# --- OPTIMIZACIÓN: Singleton del lector OCR ---
# Se crea una sola vez al importar el módulo, evitando recargar modelos desde disco
_ocr_reader = None

def _get_ocr_reader():
    """Obtiene o crea un lector EasyOCR singleton con GPU si está disponible."""
    global _ocr_reader
    if _ocr_reader is None:
        # Intentar usar GPU si hay CUDA disponible, fallback a CPU
        try:
            import torch
            has_gpu = torch.cuda.is_available()
            print(f"[INFO] OCR: {'GPU detectada - usando aceleración' if has_gpu else 'Sin GPU - usando CPU'}", file=sys.stderr)
        except ImportError:
            has_gpu = False
        
        # Suprimir advertencia pin_memory de DataLoader cuando no hay GPU
        # EasyOCR usa pin_memory=True por defecto, lo cual solo tiene sentido con GPU
        if not has_gpu:
            warnings.filterwarnings('ignore', message='.*pin_memory.*no accelerator.*')
        
        _ocr_reader = easyocr.Reader(['es', 'en'], gpu=has_gpu, verbose=False)
    return _ocr_reader

def preprocess_image(image_path):
    """Pre-procesamiento optimizado de imagen para mejorar la calidad del OCR"""
    img = Image.open(image_path)
    
    # Convertir a escala de grises
    gray_img = img.convert('L')
    
    # Aumentar el contraste (operación rápida)
    enhancer = ImageEnhance.Contrast(gray_img)
    contrast_img = enhancer.enhance(2.0)
    
    # Aplicar umbral binario OTSU para eliminar ruido de fondo
    img_array = np.array(contrast_img, dtype=np.uint8)
    _, binary = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Escalar la imagen si es muy pequeña (mejora precisión OCR)
    height, width = binary.shape
    if max(width, height) < 1000:
        scale_factor = 2.0
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        # Usar INTER_LINEAR para mejor velocidad (suficiente para OCR)
        binary = cv2.resize(binary, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    
    return binary

def extract_text_from_image(image_path):
    """Extrae texto de una imagen usando OCR (EasyOCR) con pre-procesamiento optimizado
    
    Nota: No se usa paragraph=True porque cambia el formato de resultados a [lines, text]
    sin puntuación de confianza. Es mejor obtener detecciones individuales y agrupar
    líneas manualmente para mantener control sobre filtrado por confianza.
    
    Optimizaciones aplicadas:
    - Singleton del lector (no recarga modelos en cada llamada)
    - GPU si está disponible
    - batch_size=8 (doble throughput vs 4 anterior)
    - Pre-procesamiento simplificado (eliminado paso de nitidez lento)
    - Un solo intento OCR con pre-procesado (evita duplicación)
    """
    reader = _get_ocr_reader()
    
    # Pre-procesar la imagen para mejorar calidad del OCR
    try:
        processed_img = preprocess_image(image_path)
    except Exception as e:
        print(f"[DEBUG] Pre-procesamiento falló ({e}), usando imagen original", file=sys.stderr)
        processed_img = image_path
    
    # --- OPTIMIZACIÓN: Un solo intento con batch_size=8 ---
    results = reader.readtext(
        processed_img,
        batch_size=8,           # Doble throughput vs 4 anterior
        contrast_ths=0.5,       # Umbral de contraste para detección de texto
        text_threshold=0.3,     # Umbral de confianza del texto (más bajo = más inclusivo)
    )
    
    output_text = _process_ocr_results(results)
    if not output_text:
        # Fallback simple: intentar con imagen original si pre-procesado no encontró nada
        results = reader.readtext(
            image_path,
            batch_size=8,
            contrast_ths=0.5,
            text_threshold=0.3,
        )
        output_text = _process_ocr_results(results)
    
    return output_text if output_text else "No se pudo extraer texto del archivo."

def _process_ocr_results(results):
    """Procesa los resultados de EasyOCR (formato [bbox, text, confidence]) y devuelve texto filtrado
    
    Primero agrupa detecciones adyacentes en líneas horizontales.
    Luego agrupa líneas cercanas verticalmente en párrafos para un formato más legible.
    
    Estrategia:
    1. Filtrar por confianza mínima (>30%)
    2. Ordenar por posición Y (vertical)
    3. Agrupar detecciones con Y similar en líneas horizontales (umbral configurable)
    4. Dentro de cada línea, ordenar por X y concatenar textos con espacio
    5. Agrupar líneas cercanas verticalmente en párrafos (umbral configurable)
    """
    if not results:
        return None
    
    # Paso 1: Filtrar por confianza (>30%) y extraer texto + posición
    filtered = []
    for detection in results:
        if len(detection) < 3:
            continue
        bbox, text, confidence = detection[0], detection[1], detection[2]
        if confidence > 0.3 and text.strip():
            # Extraer coordenadas del bounding box
            y_min = int(bbox[0][1]) if len(bbox) >= 4 else 0
            y_max = int(bbox[2][1]) if len(bbox) >= 4 else 0
            x_coord = int(bbox[0][0]) if len(bbox) >= 4 else 0
            # Usar el centro Y para mejor agrupamiento
            y_center = (y_min + y_max) / 2.0
            filtered.append((x_coord, y_center, text.strip(), confidence))
    
    if not filtered:
        return None
    
    # Paso 2: Ordenar por posición vertical (de arriba a abajo), luego horizontal
    filtered.sort(key=lambda x: (x[1], x[0]))
    
    # Paso 3: Agrupar detecciones en líneas horizontales
    # Dos detecciones están en la misma línea si sus centros Y difieren menos de LINE_THRESHOLD
    LINE_Y_THRESHOLD = 8   # píxeles de diferencia en centro-Y para considerar misma línea
    lines = []  # lista de listas de (x, text)
    
    current_line_detections = [(filtered[0][0], filtered[0][2])]  # (x, text)
    line_y_ref = filtered[0][1]  # centro Y de referencia para la línea actual
    
    for i in range(1, len(filtered)):
        x_coord, y_center, text, confidence = filtered[i]
        
        if abs(y_center - line_y_ref) <= LINE_Y_THRESHOLD:
            # Misma línea horizontal -> agregar a la línea actual
            current_line_detections.append((x_coord, text))
        else:
            # Nueva línea -> procesar la línea actual y empezar una nueva
            # Ordenar detecciones de la línea por X (izquierda a derecha)
            current_line_detections.sort(key=lambda x: x[0])
            line_text = ' '.join(det[1] for det in current_line_detections)
            lines.append((line_y_ref, line_text))
            
            # Empezar nueva línea
            current_line_detections = [(x_coord, text)]
            line_y_ref = y_center
    
    # Procesar la última línea
    current_line_detections.sort(key=lambda x: x[0])
    line_text = ' '.join(det[1] for det in current_line_detections)
    lines.append((line_y_ref, line_text))
    
    if not lines:
        return None
    
    # Paso 4: Agrupar líneas en párrafos cuando están cerca verticalmente
    PARAGRAPH_GAP = 30   # píxeles de diferencia Y para considerar nuevo párrafo
    paragraphs = []
    current_lines = [lines[0][1]]
    current_y = lines[0][0]
    
    for i in range(1, len(lines)):
        y_coord, text = lines[i]
        
        if abs(y_coord - current_y) > PARAGRAPH_GAP:
            paragraphs.append('\n'.join(current_lines))
            current_lines = [text]
            current_y = y_coord
        else:
            current_lines.append(text)
    
    # Agregar último grupo de líneas
    if current_lines:
        paragraphs.append('\n'.join(current_lines))
    
    return '\n\n'.join(paragraphs)

def extract_text_from_pdf(pdf_path):
    """Extrae texto de un PDF usando PyMuPDF (capa de texto) o OCR si no tiene capa
    
    Optimizaciones aplicadas:
    - Resolución reducida de 3x a 2x para renderizado (imágenes más pequeñas = OCR más rápido)
    - Singleton del lector OCR compartido entre páginas
    """
    try:
        doc = fitz.open(pdf_path)
        text_content = ""
        
        for page_num, page in enumerate(doc):
            # Primero intentar extracción directa de texto (si el PDF tiene capa de texto)
            page_text = page.get_text()
            
            if page_text and len(page_text.strip()) > 50:
                # Si hay suficiente texto extraído directamente, usarlo (sin OCR)
                text_content += f"--- Página {page_num + 1} ---\n\n{page_text}\n\n"
            else:
                # --- OPTIMIZACIÓN: Reducir resolución de 3x a 2x ---
                # Imágenes más pequeñas = OCR significativamente más rápido
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                
                temp_img_path = f"{pdf_path}.page{page_num + 1}.png"
                pix.save(temp_img_path)
                
                try:
                    ocr_text = extract_text_from_image(temp_img_path)
                    if ocr_text and not ocr_text.startswith("Error"):
                        text_content += f"--- Página {page_num + 1} ---\n\n{ocr_text}\n\n"
                    else:
                        text_content += f"--- Página {page_num + 1} ---\n\n[No se pudo extraer texto]\n\n"
                finally:
                    if os.path.exists(temp_img_path):
                        os.remove(temp_img_path)
        
        return text_content.strip()
    except Exception as e:
        return f"Error procesando PDF: {str(e)}"

def main():
    if len(sys.argv) < 2:
        print("Uso: python text2image.py <ruta_archivo>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"Error: El archivo '{file_path}' no existe.")
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()

    output_text = ""

    # Lógica de detección por extensión
    if ext == '.pdf':
        output_text = extract_text_from_pdf(file_path)
    elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
        output_text = extract_text_from_image(file_path)
    else:
        print(f"Error: Formato no soportado '{ext}'. Soporta: jpg, jpeg, png, webp, pdf")
        sys.exit(1)

    # Generar nombre para el archivo .txt de salida (mismo nombre, extensión .txt)
    base_name = os.path.splitext(file_path)[0]
    txt_output_path = f"{base_name}.txt"
    
    # Guardar el texto extraído en un archivo .txt
    if output_text and not output_text.startswith("Error"):
        with open(txt_output_path, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"[INFO] Texto guardado en: {txt_output_path}")
    
    # Salida por consola (para redirigir a un archivo si se desea desde la terminal)
    if output_text:
        print(output_text)
    else:
        print("No se pudo extraer texto del archivo.")

if __name__ == "__main__":
    main()