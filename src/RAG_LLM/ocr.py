# Optional OCR helpers using EasyOCR (install separately)
from typing import List, Dict, Any, Optional
import io
try:
    import easyocr
except Exception:
    easyocr = None

def ocr_image_bytes(image_bytes: bytes, languages: List[str]=["en"]) -> str:
    if easyocr is None:
        return ""
    reader = easyocr.Reader(languages, gpu=False)
    import numpy as np
    import PIL.Image as Image
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img)
    results = reader.readtext(arr, detail=0)
    return "\n".join(results)
