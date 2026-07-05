# --- METADATA ---
# name: Img2RRSSDesc
# description: Analiza una imagen y genera descripción, hashtags y tono optimizados para redes sociales (Instagram/TikTok)
# category: Redes Sociales/Marketing
# status: Activo
# version: 1.0.0
# icon: hashtag
# tags: RedesSociales,Instagram,TikTok,Marketing,Hashtags,Caption,IA
# dependencies: Pillow,requests,LM Studio
# command: python img2rrssdesc.py <archivo>
# requires_upload: true
# --- END METADATA ---

import sys
import os
import io
import base64
import requests
from PIL import Image

def analyze_image_for_social_media(image_path):
    """Analiza una imagen y genera contenido optimizado para redes sociales.
    
    Usa LM Studio (servidor local con API compatible con OpenAI) para analizar la imagen
    y generar:
    - Descripción atractiva (caption)
    - Hashtags relevantes
    - Tono sugerido con explicación
    
    El prompt interno instruye al modelo como experto en marketing social.
    
    LM Studio por defecto escucha en http://127.0.0.1:1234/v1/chat/completions
    """
    # Abrir y validar la imagen
    try:
        img = Image.open(image_path)
        img.verify()
        # Reabrir después de verify() porque PIL lo requiere
        img = Image.open(image_path)
    except Exception as e:
        return f"Error al abrir la imagen: {str(e)}"
    
    # Redimensionar si es muy grande para reducir el tamaño de la petición API
    max_size = 1024
    if max(img.width, img.height) > max_size:
        ratio = max_size / max(img.width, img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    
    # Guardar imagen redimensionada temporalmente como base64 para la API
    import io
    import base64
    
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    
    # Determinar el tipo MIME según la extensión original
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
    }
    mime_type = mime_map.get(ext, 'image/jpeg')
    
    # Prompt de sistema para el análisis de marketing social
    system_prompt = """Eres un asistente experto en marketing en redes sociales (Instagram y TikTok).
Tu tarea es analizar una imagen proporcionada por el usuario y generar contenido optimizado para publicaciones virales.

Debes observar cuidadosamente la imagen y entender:
- qué aparece en la imagen
- el contexto visual o emocional
- el posible propósito de la publicación

🎯 TAREA

A partir de la imagen, genera:

Descripción atractiva (caption)
Natural, llamativa y pensada para redes sociales
Puede ser emocional, creativa o narrativa
Debe invitar a interacción (likes, comentarios, compartir)

Hashtags relevantes
Entre 5 y 15 hashtags
Mezcla de hashtags generales y específicos
Relacionados con la imagen y el contexto
Sin repetir palabras innecesariamente

Tono sugerido
Clasifica el estilo del contenido en uno de estos:
divertido
profesional
inspirador
relajado
emocional
promocional
Explica brevemente por qué ese tono encaja con la imagen

📦 FORMATO DE SALIDA (OBLIGATORIO)

Responde exactamente en este formato:

Descripción:
<texto aquí>

Hashtags:
#tag1 #tag2 #tag3 ...

Tono:
<tono elegido> - <explicación breve>

🚫 REGLAS IMPORTANTES
No describas la imagen de forma técnica (evita estilo "hay una persona en…")
No seas literal: crea contenido pensado para redes sociales
No repitas hashtags genéricos sin relación
No agregues texto fuera del formato
Sé creativo pero coherente con la imagen
Si la imagen no es clara, haz la mejor interpretación posible"""

    # Construir el payload compatible con la API de LM Studio (OpenAI-compatible)
    payload = {
        "model": "",  # LM Studio usa el modelo cargado actualmente; dejar vacío o especificar
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analiza esta imagen y genera contenido para redes sociales."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{img_b64}",
                        }
                    }
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0.7,
    }

    # Llamar a LM Studio (servidor local por defecto en puerto 1234)
    lm_studio_url = os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234/v1/chat/completions")

    try:
        response = requests.post(
            lm_studio_url,
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        
        # Extraer el contenido de la respuesta
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content if content else "No se recibió respuesta del modelo."
    
    except requests.exceptions.ConnectionError:
        return f"Error: No se pudo conectar con LM Studio en {lm_studio_url}. Asegúrate de que el servidor está ejecutándose y tiene un modelo cargado con soporte de visión (por ejemplo llama-3.2-vision). Configura la variable LM_STUDIO_URL si usas otro puerto."
    except Exception as e:
        return f"Error en la llamada a LM Studio: {str(e)}"

def main():
    if len(sys.argv) < 2:
        print("Uso: python img2rrssdesc.py <ruta_imagen>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"Error: El archivo '{file_path}' no existe.")
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lower()
    
    # Validar que sea un formato de imagen soportado
    supported_formats = ['.jpg', '.jpeg', '.png', '.webp']
    if ext not in supported_formats:
        print(f"Error: Formato no soportado '{ext}'. Soporta: jpg, jpeg, png, webp")
        sys.exit(1)

    result = analyze_image_for_social_media(file_path)
    
    # Imprimir el resultado por consola
    if result:
        print(result)
    else:
        print("No se pudo generar contenido para la imagen.")

if __name__ == "__main__":
    main()