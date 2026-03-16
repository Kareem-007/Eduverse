import PIL.Image
import io
from google.genai import types
def load_image_file(filepath: str) -> types.Blob:
    """Loads an image from a file path and prepares it for Gemini."""
    try:
        img = PIL.Image.open(filepath)
        img.thumbnail([1024, 1024]) # Resize for better latency
        
        # Convert to RGB if necessary (handles PNGs)
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        buffer = io.BytesIO()
        img.save(buffer, format="jpeg")
        
        return types.Blob(
            mime_type="image/jpeg",
            data=buffer.getvalue()
        )
    except Exception as e:
        print(f"Error loading image: {e}")
        return None
