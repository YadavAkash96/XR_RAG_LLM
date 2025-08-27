# In: main_app/app.py
import yaml
import requests
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# --- App and Configuration Setup ---
app = FastAPI()

try:
    with open('../config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    STT_SERVICE_URL = config['services']['STT_ENDPOINT'] # e.g. "http://localhost:5002/transcribe"
    RAG_LLM_SERVICE_URL = config['services']['LLM_ENDPOINT'] # e.g. "http://localhost:5001/query"
except FileNotFoundError:
    print("ERROR: config.yaml not found.")
    exit()

app.mount("/static", StaticFiles(directory="static"), name="static")


# --- WebSocket Endpoint ---
# This is the single endpoint your JavaScript will connect to.
@app.websocket("/ws/query")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # 1. Wait to receive the audio data from the browser
            # The browser will send the target_object first as text, then the audio as bytes
            target_object = await websocket.receive_text()
            audio_bytes = await websocket.receive_bytes()
            print(f"Received query via WebSocket for object: {target_object}")

            # --- This is where the orchestration happens ---
            try:
                # Send a status update back to the UI
                await websocket.send_json({"status": "Transcribing audio..."})

                # Step 2: Call the STT service (using simple HTTP)
                stt_files = {'audio_file': ('query.wav', audio_bytes, 'audio/wav')}
                stt_response = requests.post(STT_SERVICE_URL, files=stt_files)
                stt_response.raise_for_status()
                user_query_text = stt_response.json()['transcription']
                print(f"STT Service returned: '{user_query_text}'")
                
                 # --- TEMPORARY CHANGE FOR TESTING ---
                # We will send the transcribed text back directly as the final result.
                # The LLM call is temporarily disabled.

                # Create a simple "result" dictionary that looks like the final one
                mock_video_result = {"url": user_query_text} 

                # Send the transcription back to the UI
                await websocket.send_json({"status": "Done", "result": mock_video_result})
                
                # Send another status update
                # await websocket.send_json({"status": f"Searching for: '{user_query_text}'"})

                # # Step 3: Call the RAG_LLM service (using simple HTTP)
                # llm_payload = {'query': user_query_text, 'context_object': target_object}
                # llm_response = requests.post(RAG_LLM_SERVICE_URL, json=llm_payload)
                # llm_response.raise_for_status()
                # video_result = llm_response.json() # The final { "url": "..." }

                # # Step 4: Send the FINAL result back to the UI over the WebSocket
                # await websocket.send_json({"status": "Done", "result": video_result})

            except requests.exceptions.RequestException as e:
                await websocket.send_json({"error": "A backend service is unavailable."})
            except Exception as e:
                await websocket.send_json({"error": "An error occurred during processing."})

    except WebSocketDisconnect:
        print("Client disconnected")

# --- Frontend Serving ---
@app.get("/")
async def serve_index():
    return FileResponse('static/index.html')