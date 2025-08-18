from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import os
import cohere
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
collection_name = os.getenv("QDRANT_COLLECTION", "xr_rag_server")
st_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

query = "How to run dry run?"
query_vec = st_model.encode([query], normalize_embeddings=True).tolist()

# Retrieve top 5 relevant chunks
results = client.search(collection_name=collection_name, query_vector=query_vec[0], limit=5)
chunks = [r.payload["chunk"] for r in results]


# --- New code for LLM response generation ---

# 1. Initialize the Inference Client
# hf_client = InferenceClient(token=os.getenv("HF_API_KEY"))
co = cohere.Client(os.getenv("COHERE_API_KEY"))
COHERE_MODEL = "command-r"

context = "\n".join(chunks)


SYSTEM_PROMPT = """You are a careful appliance assistant.
- Produce concise, numbered step-by-step instructions grounded ONLY in the provided context.
- If brand/model present, tailor steps accordingly; otherwise give generic steps.
- Start with a one-line goal: "Goal: ..."
- Each step ≤ 20 words.
- Include safety warnings if present.
- If information is missing, state what is missing and stop.
- Add citations as [source: <short_id>] at the end.
Format your reply ONLY as a JSON object with the following keys:
- goal (string)
- steps (array of strings)
- warnings (array of strings)
- sources (array of strings)

Do not include extra text. Output only valid JSON."""

# 3. Create a prompt for the model
#    Chat models often work best with a structured list of messages.
messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    },
    {
        "role": "user",
        "content": f"""
        Context:
        {context}

        ---
        Question: {query}
        """
    }
]


# 4. Make the API call to generate the response
# We are using a popular and powerful open-source model here.
# You can find more models on the Hugging Face Hub.
# response = hf_client.chat_completion(
#     messages=messages,
#     model="HuggingFaceH4/zephyr-7b-beta",
#     max_tokens=500,
#     temperature=0.2,
# )

# # 5. Print the generated answer
# print("LLM Response:")
# print(response.choices[0].message.content)



user_message = f"Context:\n{context if context else 'No context available.'}\n\nQuestion: {query}"

response = co.chat(
    model=COHERE_MODEL,
    message=user_message,
    preamble=SYSTEM_PROMPT,  # Cohere uses 'preamble' for the system prompt
    temperature=0.2,
)
llm_output = response.text
print("LLM Response:{}".format(llm_output))