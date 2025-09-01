import os
import json
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List, Optional

from qdrant_client import QdrantClient, models as qdrant_models
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURATION ---
QDRANT_COLLECTION_NAME = "fitness_videos_rag"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# --- API MODELS (Request and Response Contracts) ---
class QueryRequest(BaseModel):
    """Defines the structure of an incoming query from the front-end."""
    query: str = Field(..., description="The combined text query from the user's voice and the detected object.")
    seen_video_urls: Optional[List[str]] = Field(default_factory=list, description="A list of video URLs already shown to the user in this session.")

class VideoResponse(BaseModel):
    """Defines the structure of the video response sent back to the front-end."""
    video_url: str
    embed_url: str
    video_title: str
    expert_name: str
    text_chunk: str

# --- INITIALIZE SERVICES (Loaded once on startup for performance) ---
print("Loading environment variables from .env file...")
load_dotenv()
QUERY_MODE = "ollama"
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")

print(f"--- Initializing in <{QUERY_MODE.upper()}> mode ---")

# --- Initialize Clients Based on the Switch ---
entity_extraction_client = None
if QUERY_MODE == "gemini":
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set in .env file for Gemini mode.")
    genai.configure(api_key=google_api_key)
    generation_config = genai.GenerationConfig(response_mime_type="application/json")
    entity_extraction_client = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        generation_config=generation_config
    )
    print("Initialized Gemini client.")
elif QUERY_MODE == "ollama":
    entity_extraction_client = OpenAI(
        base_url='http://localhost:11434/v1',
        api_key='ollama',
    )
    print("Initialized Ollama client. Make sure the Ollama server is running.")
else:
    raise ValueError(f"Invalid QUERY_MODE: {QUERY_MODE}. Choose 'gemini' or 'ollama'.")

if not all([qdrant_url, qdrant_api_key, google_api_key]):
    raise RuntimeError("CRITICAL: Required environment variables (QDRANT_URL, QDRANT_API_KEY, GOOGLE_API_KEY) are not set!")

print("Initializing clients (Qdrant, SentenceTransformer, Gemini)...")
# Initialize Qdrant client
qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
# Initialize the embedding model (runs locally)
embedding_model = SentenceTransformer(EMBED_MODEL_NAME, device="cuda" if "cuda" in "cuda" else "cpu")

genai.configure(api_key=google_api_key)
generation_config = genai.GenerationConfig(response_mime_type="application/json")
gemini_model = genai.GenerativeModel(model_name='gemini-1.5-flash', generation_config=generation_config)
print("All clients initialized successfully. API is ready.")

# Initialize FastAPI application
app = FastAPI(
    title="Fitness RAG API",
    description="API for retrieving instructional fitness videos based on real-world context."
)

# --- HELPER FUNCTIONS ---
def analyze_query_with_ollama(query: str, client: OpenAI, model_name="phi3"):
    """
    Uses a local Ollama model to extract entities, ensuring all outputs are lists.
    """
    prompt = f"""You are an expert data analyst. Your task is to extract fitness entities from the following user question. Provide the output ONLY as a valid JSON object with keys "machine_name", "body_parts", and "exercise_name".\n\nUser Question:\n---\n{query}\n---"""
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        extracted_data = json.loads(response.choices[0].message.content)

        
        def to_list(value):
            if isinstance(value, str):
                return [value] 
            if isinstance(value, list):
                return value 
            return [] 

        validated_data = {
            "machine_name": to_list(extracted_data.get("machine_name")),
            "body_parts": to_list(extracted_data.get("body_parts")),
            "exercise_name": to_list(extracted_data.get("exercise_name"))
        }
        return validated_data
        # --- END OF FIX ---

    except Exception as e:
        print(f"Error during Ollama query analysis: {e}")
        return {"machine_name": [], "body_parts": [], "exercise_name": []}
    

def analyze_query_with_gemini(query: str) -> dict:
    """Uses Gemini to extract structured entities from the combined user query."""
    prompt = f"""
    You are an expert data analyst. Your task is to extract fitness entities from the following user query.
    Provide the output ONLY as a valid JSON object with keys "machine_name", "body_parts", and "exercise_name".
    Each key should have a list of strings as its value.

    User Query:
    ---
    {query}
    ---
    """
    try:
        response = gemini_model.generate_content(prompt)
        entities = json.loads(response.text)
        return {
            "machine_name": entities.get("machine_name", []),
            "body_parts": entities.get("body_parts", []),
            "exercise_name": entities.get("exercise_name", [])
        }
    except Exception as e:
        print(f"Error during query analysis with Gemini: {e}")
        return {"machine_name": [], "body_parts": [], "exercise_name": []}

def create_embeddable_url(youtube_url: str) -> str:
    """Converts a standard YouTube Shorts URL to a format that can be embedded in an iframe."""
    if "youtube.com/shorts/" in youtube_url:
        video_id = youtube_url.split("/shorts/")[1].split("?")[0] # Handle potential params
        return f"https://www.youtube.com/embed/{video_id}"
    # Will add other platforms here 
    return youtube_url

# --- THE MAIN API ENDPOINT ---
@app.post("/query", response_model=VideoResponse)
def query_videos(request: QueryRequest):
    """
    This endpoint is the core of the RAG system. It receives a query, finds the best
    instructional video, and handles filtering for videos already seen.
    """
    print(f"\n[REQUEST] Received query: '{request.query}'")
    print(f"[REQUEST] Excluding seen URLs: {request.seen_video_urls}")

    # Step 1: Analyze the query to extract structured entities for filtering.
    if QUERY_MODE == "gemini":
        # This will fail until your daily quota resets
        entities = analyze_query_with_gemini(request.query, entity_extraction_client)
    else: # ollama mode
        entities = analyze_query_with_ollama(request.query, entity_extraction_client)

    print(f"[ANALYSIS] Extracted Entities: {entities}")

    # Step 2: Build a robust metadata filter for Qdrant.
    # This filter ensures we only search within a factually correct subset of our data.
    filter_conditions = []
    if entities.get("machine_name"):
        filter_conditions.append(qdrant_models.FieldCondition(
            key="machine_name", match=qdrant_models.MatchAny(any=entities["machine_name"])
        ))
    if entities.get("body_parts"):
        filter_conditions.append(qdrant_models.FieldCondition(
            key="body_parts", match=qdrant_models.MatchAny(any=entities["body_parts"])
        ))
    
    query_filter = qdrant_models.Filter(should=filter_conditions) if filter_conditions else None
    print(f"[FILTER] Constructed Qdrant Filter: {query_filter}")

    # Step 3: Convert the user's natural language query into a vector embedding.
    query_vector = embedding_model.encode(request.query).tolist()

    # Step 4: Perform the hybrid search in Qdrant.
    # We retrieve more (limit=15) than we need to have fallbacks if the top results have been seen.
    search_results = qdrant_client.search(
        collection_name=QDRANT_COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=15,
        with_payload=True
    )

    # Step 5: Iterate through the ranked results and find the first one the user hasn't seen.
    for result in search_results:
        video_url = result.payload.get("video_url")
        if video_url and video_url not in request.seen_video_urls:
            print(f"[RESULT] Found top unseen result: '{result.payload.get('video_title')}' with score {result.score:.4f}")
            # Prepare and return the successful response
            return VideoResponse(
                video_url=video_url,
                embed_url=create_embeddable_url(video_url),
                video_title=result.payload.get("video_title", "No Title"),
                expert_name=result.payload.get("expert_name", "Unknown Expert"),
                text_chunk=result.payload.get("text", "")
            )

    # Step 6: If the loop completes, no new videos were found.
    print("[RESPONSE] No new relevant videos found for this query.")
    raise HTTPException(status_code=404, detail="No new relevant videos were found. You may have seen them all.")

# --- To run the server ---
# In your terminal, navigate to this directory and run:
# uvicorn query_api:app --reload