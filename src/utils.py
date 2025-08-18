import os, re, io, json, hashlib, pathlib
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def file_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def load_text_from_pdf(path: str) -> Tuple[str, List[Dict[str, Any]]]:
    doc = fitz.open(path)
    texts = []
    images = []
    for pno in range(len(doc)):
        page = doc[pno]
        texts.append(page.get_text("text"))
        for img in page.get_images(full=True):
            xref = img[0]
            base_img = doc.extract_image(xref)
            ext = base_img.get("ext", "png")
            image_bytes = base_img["image"]
            images.append({"page": pno, "xref": xref, "ext": ext, "image_bytes": image_bytes})
    return "\n".join(texts), images

def load_text_from_plain(path: str) -> str:
    return pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")

def load_text_from_html(path: str) -> str:
    html = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text("\n")
    return text

def chunk_text(text: str, min_tokens: int=50, max_tokens: int=150) -> List[str]:
    paras = re.split(r"\n{2,}", text)
    chunks = []
    for para in paras:
        para = para.strip()
        if not para:
            continue
        sentences = re.split(r"(?<=[\.\!\?])\s+", para)
        buf = []
        for s in sentences:
            buf.append(s)
            token_estimate = sum(len(w.split()) for w in buf)
            if token_estimate >= max_tokens:
                chunks.append(" ".join(buf).strip())
                buf = []
        if buf:
            chunk = " ".join(buf).strip()
            if len(chunk.split()) >= min_tokens or not chunks:
                chunks.append(chunk)
    return chunks

def infer_metadata_from_filename(path: str) -> Dict[str, Any]:
    name = os.path.basename(path)
    brand = None
    model = None
    locale = None
    low = name.lower()
    tokens = re.split(r"[_\-\.\s]+", low)
    for tk in tokens:
        if re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", tk):
            locale = tk
    if tokens:
        brand = tokens[0]
    for tk in tokens[1:]:
        if re.search(r"[a-z]", tk) and re.search(r"\d", tk):
            model = tk
            break
    return {"brand": brand, "model": model, "locale": locale}

def save_binary(path: str, data: bytes):
    ensure_dir(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(data)
