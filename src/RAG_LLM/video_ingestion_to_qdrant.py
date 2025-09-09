import argparse
import time
import uuid
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
import nltk
from openai import OpenAI
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import yaml


def extract_entities_with_ollama(video_data, client, model_name="phi3"):
    """
    Uses a local Ollama model to extract structured entities.
    """
    text_content = f"Title: {video_data.get('title', '')}\nDescription: {video_data.get('description', '')}"

    # Phi-3 is excellent at following structured prompts
    prompt = f"""
    You are an expert sports scientist. Your task is to extract fitness entities from the following video text.
    Analyze the text and provide the output ONLY as a valid JSON object. Do not include any other text, explanations, or markdown formatting.
    The JSON object must have the following keys: "machine_name", "exercise_name", "body_parts".

    Video Text to Analyze:
    ---
    {text_content}
    ---
    """
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        
        # Validate and clean the data
        validated_data = {
            "machine_name": extracted_data.get("machine_name", []) or ["General"],
            "exercise_name": extracted_data.get("exercise_name", ["Unknown Exercise"]),
            "body_parts": extracted_data.get("body_parts", [])
        }
        return validated_data

    except Exception as e:
        print(f"\n[ERROR] Ollama entity extraction failed: {e}")
        return {
            "machine_name": ["General"],
            "exercise_name": [video_data.get('title', 'Unknown Exercise')],
            "body_parts": []
        }
    
def extract_entities_with_gemini(video_data, model):
    text_content = f"Title: {video_data.get('title', '')}\nDescription: {video_data.get('description', '')}"
    
    json_format_instructions = """
    {
        "machine_name": ["Name of the gym machine, e.g., 'Leg Press' or 'Cable Machine'"],
        "exercise_name": ["Specific name of the exercise, e.g., 'Barbell Squat' or 'Tricep Pushdown'"],
        "body_parts": ["List of primary muscle groups worked, e.g., 'Quads', 'Glutes', 'Triceps'"]
    }
    """
    
    prompt = f"""
    You are an expert sports scientist. Your task is to extract fitness entities from the following video text.
    Analyze the text and provide the output ONLY in the valid JSON format specified below.
    Do not include any text, explanations, or markdown formatting outside of the JSON object.

    JSON Format:
    {json_format_instructions}

    Rules:
    - If no specific machine is mentioned, return an empty list for "machine_name".
    - "body_parts" should be a list of primary muscles targeted.

    Video Text to Analyze:
    ---
    {text_content}
    ---

    JSON Output:
    """
    
    try:
        response = model.generate_content(prompt)
        json_string = response.text.strip().replace("```json", "").replace("```", "").strip()
        extracted_data = json.loads(json_string)
        
        validated_data = {
            "machine_name": extracted_data.get("machine_name", []) or ["General"],
            "exercise_name": extracted_data.get("exercise_name", ["Unknown Exercise"]),
            "body_parts": extracted_data.get("body_parts", [])
        }
        return validated_data
        
    except Exception as e:
        print(f"\n[ERROR] Gemini entity extraction failed: {e}")
        return { "machine_name": ["General"], "exercise_name": [video_data.get('title', 'Unknown Exercise')], "body_parts": [] }

def chunk_text(text, sentences_per_chunk=5):
    sentences = nltk.sent_tokenize(text)
    return [" ".join(sentences[i:i + sentences_per_chunk]) for i in range(0, len(sentences), sentences_per_chunk)]



if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))

    print("Checking/downloading NLTK 'punkt' model...")
    nltk.download('punkt', quiet=True)

    # Set this to "ollama" to use your local model, or "gemini" for the cloud.
    EXTRACTION_MODE = "ollama" 

    # 1. Load Environment Variables
    load_dotenv()
    INPUT_JSONL_FILE = "fitness_videos_data.jsonl"
    QDRANT_COLLECTION_NAME = "fitness_videos_rag"
    EMBED_MODEL_NAME = cfg["index"]["text_model"]
    VECTOR_DIMENSION = 768  

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not all([qdrant_url, qdrant_api_key, google_api_key]):
        raise ValueError("QDRANT_URL, QDRANT_API_KEY, and GOOGLE_API_KEY must be set in the .env file.")

    print("--- Starting Data Ingestion for Qdrant with Gemini Extraction ---")

    if EXTRACTION_MODE == "gemini":
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY is not set in .env file for Gemini mode.")
        genai.configure(api_key=google_api_key)
        generation_config = genai.GenerationConfig(response_mime_type="application/json")
        entity_extraction_client = genai.GenerativeModel(
            model_name='gemini-1.5-flash',      #SLM:Small Language Model
            generation_config=generation_config
        )
        print("Initialized Gemini client.")
    elif EXTRACTION_MODE == "ollama":

        entity_extraction_client = OpenAI(
            base_url='http://localhost:11434/v1',
            api_key='ollama',
        )
        print("Initialized Ollama client. Make sure the Ollama server is running.")
    else:
        raise ValueError(f"Invalid EXTRACTION_MODE: {EXTRACTION_MODE}. Choose 'gemini' or 'ollama'.")
    
    print("Initializing clients (Qdrant, SentenceTransformer, Gemini)...")
    qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    embedding_model = SentenceTransformer(EMBED_MODEL_NAME, device="cuda" if "cuda" in "cuda" else "cpu")

    print(f"Setting up Qdrant collection: '{QDRANT_COLLECTION_NAME}'")

    if qdrant_client.collection_exists(collection_name=QDRANT_COLLECTION_NAME):
        print(f"Collection '{QDRANT_COLLECTION_NAME}' already exists. Deleting it to start fresh.")
        qdrant_client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)

    print(f"Creating new collection: '{QDRANT_COLLECTION_NAME}'")
    qdrant_client.create_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors_config= models.VectorParams(size=VECTOR_DIMENSION, distance=models.Distance.COSINE)
    )
    
    # --- NEW: CREATE PAYLOAD INDEXES ---
    print("Creating payload indexes for filtering...")
    # Index for machine_name
    qdrant_client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name="machine_name",
        field_schema="keyword"
    )
    # Index for body_parts
    qdrant_client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name="body_parts",
        field_schema="keyword"
    )
    # Index for exercise_name (good practice to add it too)
    qdrant_client.create_payload_index(
        collection_name=QDRANT_COLLECTION_NAME,
        field_name="exercise_name",
        field_schema="keyword"
    )
    print("Payload indexes created successfully.")
    print(f"Processing data from '{INPUT_JSONL_FILE}'...")
    points_to_upload = []
    with open(INPUT_JSONL_FILE, 'r', encoding='utf-8') as f:
        for line in tqdm(f, desc="Processing videos"):
            video_data = json.loads(line)
            if not video_data.get('transcript'):
                continue

            if EXTRACTION_MODE == "gemini":
                entities = extract_entities_with_gemini(video_data, entity_extraction_client)
            else: 
                entities = extract_entities_with_ollama(video_data, entity_extraction_client)
            
            print(entities)
            
            transcript_chunks = chunk_text(video_data['transcript'])

            for chunk in transcript_chunks:
                payload = {
                    "text": chunk,
                    "video_url": video_data.get('url'),
                    "video_title": video_data.get('title'),
                    "machine_name": entities["machine_name"],
                    "body_parts": entities["body_parts"],
                    "exercise_name": entities["exercise_name"]
                }
                point = {"id": str(uuid.uuid4()), "payload": payload}
                points_to_upload.append(point)

    if points_to_upload:
        print(f"Prepared {len(points_to_upload)} points. Generating embeddings and uploading...")
        
        chunk_texts = [point["payload"]["text"] for point in points_to_upload]
        vectors = embedding_model.encode(chunk_texts, show_progress_bar=True)
        
        for i, point in enumerate(points_to_upload):
            point["vector"] = vectors[i].tolist()
            
        qdrant_client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=[models.PointStruct(**point) for point in points_to_upload],
            wait=True
        )
        
        print(f"--- Ingestion Complete! ---")
        print(f"Successfully uploaded {len(points_to_upload)} points to Qdrant collection '{QDRANT_COLLECTION_NAME}'.")
    else:
        print("No data was processed or uploaded.")

