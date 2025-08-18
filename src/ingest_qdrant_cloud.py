import os, io, json, argparse, yaml, numpy as np
from typing import Dict, Any, List, Set, Tuple
from tqdm import tqdm

import torch
from PIL import Image

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, VisionEncoderDecoderModel

from qdrant_client import QdrantClient, models
from dotenv import load_dotenv
from utils import *
from ocr import ocr_image_bytes

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")
TEXT_MODEL = os.getenv("TEXT_MODEL")
CAPTION_MODEL = os.getenv("CAPTION_MODEL")
SHARED_ENCODER_MODEL = os.getenv("SHARED_ENCODER_MODEL")
USE_OCR = os.getenv("USE_OCR", "false").lower() == "true"
LANGUAGES = os.getenv("LANGUAGES", "en").split(",")
MIN_CHUNK_TOKENS = int(os.getenv("MIN_CHUNK_TOKENS", 50))
MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS", 150))
STORE_IMAGES = os.getenv("STORE_IMAGES", "false").lower() == "true"

def load_captioner(name: str):
    if "nlpconnect" in name:
        from transformers import ViTImageProcessor
        tok = AutoTokenizer.from_pretrained(name)
        proc = ViTImageProcessor.from_pretrained(name)
        model = VisionEncoderDecoderModel.from_pretrained(name)
        return ("vitgpt2", model, proc, tok)
    else:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        proc = BlipProcessor.from_pretrained(name)
        model = BlipForConditionalGeneration.from_pretrained(name)
        return ("blip", model, proc, None)


def caption_images(image_bytes_list: List[bytes], caption_cfg: Dict[str, Any], batch_size: int = 8) -> List[str]:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cap_type, model, proc, tok = load_captioner(caption_cfg["caption_model"])
    model = model.to(device)
    captions = []
    for i in range(0, len(image_bytes_list), batch_size):
        batch = image_bytes_list[i:i+batch_size]
        images = [Image.open(io.BytesIO(b)).convert("RGB") for b in batch]
        with torch.no_grad():
            if cap_type == "vitgpt2":
                pixel_values = proc(images=images, return_tensors="pt").pixel_values.to(device)
                out_ids = model.generate(pixel_values=pixel_values, max_length=64, num_beams=3)
                caps = tok.batch_decode(out_ids, skip_special_tokens=True)
            else:
                inputs = proc(images=images, return_tensors="pt").to(device)
                out_ids = model.generate(**inputs, max_length=64, num_beams=3)
                caps = proc.tokenizer.batch_decode(out_ids, skip_special_tokens=True)
        captions.extend([c.strip() for c in caps])
    return captions


def embed_texts(texts: List[str], st_model: SentenceTransformer, batch_size: int = 64) -> np.ndarray:
    vecs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        v = st_model.encode(batch, normalize_embeddings=True, convert_to_numpy=True)
        vecs.append(v)
    return np.vstack(vecs).astype(np.float32, copy=False) if vecs else np.zeros((0, st_model.get_sentence_embedding_dimension()), dtype=np.float32)


def embed_shared_encoder_text_and_images(text_chunks: List[str], image_bytes_list: List[bytes], shared_model_name: str) -> tuple[np.ndarray, int]:
    model = SentenceTransformer(shared_model_name)
    text_vecs = model.encode(text_chunks, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32, copy=False) if text_chunks else np.zeros((0, model.get_sentence_embedding_dimension()), dtype=np.float32)
    imgs = [Image.open(io.BytesIO(b)).convert("RGB") for b in image_bytes_list]
    img_vecs = model.encode(imgs, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32, copy=False) if imgs else np.zeros((0, model.get_sentence_embedding_dimension()), dtype=np.float32)
    all_vecs = np.vstack([text_vecs, img_vecs]).astype(np.float32, copy=False) if text_vecs.shape[0] + img_vecs.shape[0] > 0 else np.zeros((0, model.get_sentence_embedding_dimension()), dtype=np.float32)
    return all_vecs, model.get_sentence_embedding_dimension()


def merge_modalities_to_text_chunks(
    text_chunks: List[str],
    text_meta: List[Dict[str, Any]],
    image_bytes_list: List[bytes],
    image_meta: List[Dict[str, Any]],
    caption_cfg: Dict[str, Any],
    use_ocr: bool,
    langs: List[str],
    min_tokens: int,
    max_tokens: int,
    ocr_already_in_text: Set[Tuple[str, int]] | None = None,
):
    merged_chunks = []
    merged_meta = []

    captions = caption_images(image_bytes_list, caption_cfg) if image_bytes_list else []
    ocr_seen = ocr_already_in_text or set()

    for i, m in enumerate(image_meta):
        cap_text = captions[i] if captions else ""
        ocr_text = ""
        key = (m.get("source"), int(m.get("page", -1)))
        if use_ocr and key not in ocr_seen:
            ocr_text = ocr_image_bytes(image_bytes_list[i], languages=langs)
        merged_text_parts = []
        if cap_text.strip():
            merged_text_parts.append(f"[Image Caption]: {cap_text}")
        if ocr_text.strip():
            merged_text_parts.append(f"[Image Text]: {ocr_text}")
        if merged_text_parts:
            merged_text = "\n".join(merged_text_parts)
            for c in chunk_text(merged_text, min_tokens, max_tokens):
                merged_chunks.append(c)
                merged_meta.append({"chunk": c, "type": "image_info", **m})

    for c, m in zip(text_chunks, text_meta):
        merged_chunks.append(c)
        merged_meta.append({"chunk": c, "type": "text", **m})

    return merged_chunks, merged_meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Folder with PDFs, images, txt/md/html")
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))

    # Qdrant cloud setup
    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "xr_rag")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    strategy = cfg["index"].get("strategy", "caption_to_text")
    text_model_name = cfg["index"]["text_model"]
    use_ocr = bool(cfg["index"].get("use_ocr", False))
    langs = cfg["index"].get("languages", ["en"])
    min_tokens = int(cfg["index"].get("min_chunk_tokens", 50))
    max_tokens = int(cfg["index"].get("max_chunk_tokens", 150))

    # Gather corpus
    text_chunks, text_meta = [], []
    image_bytes_list, image_meta = [], []

    supported_img_ext = {".png", ".jpg", ".jpeg", ".webp"}
    supported_text_ext = {".txt", ".md", ".markdown", ".html", ".htm"}
    supported_pdf_ext = {".pdf"}

    for root, _, files in os.walk(args.input):
        for fn in files:
            path = os.path.join(root, fn)
            ext = os.path.splitext(fn)[1].lower()
            meta = infer_metadata_from_filename(path)

            if ext in supported_text_ext:
                text = load_text_from_html(path) if ext in {".html", ".htm"} else load_text_from_plain(path)
                for c in chunk_text(text, min_tokens, max_tokens):
                    text_chunks.append(c)
                    text_meta.append({"source": path, **meta})

            elif ext in supported_pdf_ext:
                text, images = load_text_from_pdf(path)
                for c in chunk_text(text, min_tokens, max_tokens):
                    text_chunks.append(c)
                    text_meta.append({"source": path, **meta})
                for im in images:
                    image_bytes_list.append(im["image_bytes"])
                    image_meta.append({"source": path, "page": im["page"], **meta})
                if use_ocr and not text.strip():
                    for im in images:
                        ocr_text = ocr_image_bytes(im["image_bytes"], languages=langs)
                        if ocr_text.strip():
                            for c in chunk_text(ocr_text, min_tokens, max_tokens):
                                text_chunks.append(c)
                                text_meta.append({"source": path, "page": im["page"], "ocr": True, **meta})

            elif ext in supported_img_ext:
                with open(path, "rb") as f:
                    b = f.read()
                image_bytes_list.append(b)
                image_meta.append({"source": path, **meta})

    print(f"[Ingest] Found text chunks: {len(text_chunks)} | images: {len(image_bytes_list)}")

    # Build embeddings
    if strategy == "caption_to_text":
        caption_cfg = {"caption_model": cfg["index"].get("caption_model", "nlpconnect/vit-gpt2-image-captioning")}
        ocr_already_in_text = {(m.get("source"), int(m.get("page", -1))) for m in text_meta if m.get("ocr") is True}
        merged_chunks, merged_meta = merge_modalities_to_text_chunks(
            text_chunks, text_meta, image_bytes_list, image_meta, caption_cfg,
            use_ocr, langs, min_tokens, max_tokens, ocr_already_in_text=ocr_already_in_text
        )
        print(f"[Ingest] Total merged chunks for embedding: {len(merged_chunks)}")
        st_model = SentenceTransformer(text_model_name)
        vectors = embed_texts(merged_chunks, st_model)
        all_meta = merged_meta

    elif strategy == "shared_encoder":
        shared_model_name = cfg["index"]["shared_encoder_model"]
        if not shared_model_name:
            raise ValueError("Set index.shared_encoder_model in config when using shared_encoder")
        vectors, _ = embed_shared_encoder_text_and_images(text_chunks, image_bytes_list, shared_model_name)
        all_meta = [{"type": "text", **m} for m in text_meta] + [{"type": "image", **m} for m in image_meta]

    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    print(f"[Ingest] Final vectors: {vectors.shape[0]} x {vectors.shape[1]}")

    # Ensure Qdrant collection exists
    try:
        client.get_collection(QDRANT_COLLECTION)
    except Exception:
        client.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=models.VectorParams(size=vectors.shape[1], distance=models.Distance.COSINE)
        )

    # Upsert into Qdrant in batches
    BATCH_SIZE = 500
    
    # points = [PointStruct(vector=v.tolist(), payload=m) for v, m in zip(vectors, merged_meta)]
    
    points = [models.PointStruct(id=i, vector=v.tolist(), payload=m) for i, (v, m) in enumerate(zip(vectors, merged_meta))]

    BATCH_SIZE = 500
    for i in range(0, len(points), BATCH_SIZE):
        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points[i:i+BATCH_SIZE]
        )
        print(f"Uploaded {min(i+BATCH_SIZE,len(points))}/{len(points)} points")


if __name__ == "__main__":
    main()
