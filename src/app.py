import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient
import cohere # <-- Added Cohere import
from dotenv import load_dotenv
from typing import List, Optional

# --- 1. Configuration and Initialization ---

load_dotenv()

GENERIC_QUERY_THRESHOLD = 0.25

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    notes: Optional[List[str]] = Field(None, description="Optional list of text notes from the XR scene.")

class XRResponse(BaseModel):
    goal: str
    steps: List[str]
    warnings: List[str]
    sources: List[str]
    is_generic: bool = Field(False, description="True if the answer is from general knowledge, not a manual.")

# --- 2. Load Models and Clients at Startup ---

app = FastAPI(
    title="XR Context-Aware Assistant API",
    version="3.0-Cohere", # <-- Updated version to reflect the change
    description="API that combines user manuals with real-time scene notes to answer queries."
)

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
collection_name = os.getenv("QDRANT_COLLECTION", "xr_rag_server")
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# --- LLM Client Initialization ---
# Hugging Face Client (Commented Out)
# hf_client = InferenceClient(token=os.getenv("HF_TOKEN"))
# LLM_MODEL = "google/gemma-1.1-7b-it"

# Cohere Client (Now Active)
co = cohere.Client(os.getenv("COHERE_API_KEY"))
COHERE_MODEL = "command-r"

SYSTEM_PROMPT = """You are a careful appliance assistant.
- Produce concise, numbered step-by-step instructions based on the provided context.
- Start with a one-line goal: "Goal: ..."
- Each step should be 20 words or less.
- If the context contains safety warnings, extract them exactly as they are.
- If the context is empty or unhelpful, answer from your general knowledge.
- Format your reply ONLY as a JSON object with the following keys: "goal", "steps", "warnings".

Do not include any text before or after the JSON object. Output only valid JSON."""

# --- 3. API Endpoint Definition ---

@app.post("/ask_xr", response_model=XRResponse)
async def ask_xr_assistant(request: QueryRequest):
    try:
        query_vector = embedding_model.encode([request.query], normalize_embeddings=True).tolist()
        
        # Search Qdrant for relevant context
        search_results = qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_vector[0],
            limit=request.top_k,
            with_payload=True
        )

        # Decide if the query is generic based on the score of the BEST result.
        is_generic_query = (
            not search_results or 
            search_results[0].score < GENERIC_QUERY_THRESHOLD
        )
        
        context = ""
        sources = []
        
        if is_generic_query:
            sources = ["General Knowledge"]
        else:
            context_chunks = [hit.payload.get("chunk", "") for hit in search_results]
            sources = list(set([hit.payload.get("source", "unknown") for hit in search_results]))
            manual_context = "\n---\n".join(context_chunks)
            context = f"Manual Information:\n{manual_context}"

            if request.notes:
                notes_context = "\n".join(request.notes)
                context = f"Important Real-Time Scene Notes:\n{notes_context}\n\n---\n\n{context}"

        # --- LLM Call Section ---

        # === Hugging Face API Call (Commented Out) ===
        # messages = [
        #     {"role": "system", "content": SYSTEM_PROMPT},
        #     {"role": "user", "content": f"Context:\n{context if context else 'No context available.'}\n\nQuestion: {request.query}"}
        # ]
        # 
        # response = hf_client.chat_completion(
        #     messages=messages, model=LLM_MODEL, max_tokens=512, temperature=0.1
        # )
        # llm_output = response.choices[0].message.content
        # ============================================

        # === Cohere API Call (Now Active) ===
        user_message = f"Context:\n{context if context else 'No context available.'}\n\nQuestion: {request.query}"

        response = co.chat(
            model=COHERE_MODEL,
            message=user_message,
            preamble=SYSTEM_PROMPT,  # Cohere uses 'preamble' for the system prompt
            temperature=0.2,
        )
        llm_output = response.text
        # ==================================

        try:
            # The rest of this logic works for both APIs without changes
            cleaned_output = llm_output.strip().replace("```json", "").replace("```", "").strip()
            json_response = json.loads(cleaned_output)
            
            llm_warnings = json_response.get("warnings", [])
            if not isinstance(llm_warnings, list):
                llm_warnings = []

            if is_generic_query:
                final_warnings = ["This is general advice and is not from a specific product manual."]
            else:
                final_warnings = llm_warnings
                if request.notes:
                    final_warnings.append("This response also considers real-time notes provided by the user.")
            
            json_response["warnings"] = final_warnings
            json_response["sources"] = sources
            json_response["is_generic"] = is_generic_query
            
            return XRResponse(**json_response)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to parse LLM response. Error: {e}. Raw output: {llm_output}"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")