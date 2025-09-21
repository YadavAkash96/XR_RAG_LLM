import yaml
import requests
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


app = FastAPI()

try:
    with open('../config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    STT_SERVICE_URL = config['services']['STT_ENDPOINT']     # e.g. "http://localhost:5002/transcribe"
    RAG_LLM_SERVICE_URL = config['services']['LLM_ENDPOINT'] # e.g. "http://localhost:8001/query"
except (FileNotFoundError, KeyError):
    print("ERROR: config.yaml not found or missing required service endpoints.")
    exit()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws/query")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # The WebSocket now handles two types of incoming messages.
            # It will always receive a JSON text message first.
            
            message_str = await websocket.receive_text()
            message_data = json.loads(message_str)
            
            target_object = 'leg press machine'        #message_data.get("target_object")
            seen_urls = message_data.get("seen_urls", [])
            
            user_query_text = "" # Initialize to empty

            # --- DYNAMIC LOGIC: Check if we need to do STT ---
            if "transcribed_text" in message_data:
                # This is a "Next Video" request. We already have the text.
                user_query_text = message_data["transcribed_text"]
                print(f"Received 'Next Video' request with cached text: '{user_query_text}'")
            else:
                audio_bytes = await websocket.receive_bytes()       # <-- Wait for the audio bytes
                print(f"Received new audio query for object: '{target_object}'")
                if len(audio_bytes) < 1024:
                    print(f"[WARN] Received empty or invalid audio data (size: {len(audio_bytes)} bytes). Skipping STT.")

                    await websocket.send_json({"error": "No audio was detected in the recording. Please try again."})
                    continue 
                try:
                    await websocket.send_json({"status": "Transcribing audio..."})
                    stt_files = {'audio_file': ('query.wav', audio_bytes, 'audio/wav')}
                    stt_response = requests.post(STT_SERVICE_URL, files=stt_files)
                    stt_response.raise_for_status()
                    
                    stt_result = stt_response.json()
                    user_query_text = stt_result['transcription']
                    print(f"STT Service returned: '{user_query_text}'")

                    # If STT service returns an empty string, treat it as an error
                    if not user_query_text.strip():
                         print("[WARN] STT service returned an empty transcription. Skipping RAG.")
                         await websocket.send_json({"error": "Could not understand the audio. Please speak clearly and try again."})
                         continue
                    
                    # IMPORTANT: Send the transcribed text back to the front-end so it can cache it
                    await websocket.send_json({"status": "Transcribed", "transcribed_text": user_query_text})

                except requests.exceptions.RequestException as e:
                    await websocket.send_json({"error": f"STT service is unavailable: {e}"})
                    continue # Wait for the next message
            
            # --- RAG Call (This part is now common to both paths) ---
            if user_query_text:
                try:
                    await websocket.send_json({"status": f"Searching for: '{user_query_text}'"})

                    combined_query = f"{user_query_text} {target_object}"
                    rag_payload = {
                        'query': combined_query,
                        'seen_video_urls': seen_urls
                    }

                    rag_response = requests.post(RAG_LLM_SERVICE_URL, json=rag_payload)
                    rag_response.raise_for_status()
                    video_result = rag_response.json()
                    print(video_result)
                    await websocket.send_json({"status": "Done", "result": video_result})
                    print(f"Sent video result to client: {video_result.get('video_title')}")
                
                except requests.exceptions.RequestException as e:
                    await websocket.send_json({"error": f"RAG service is unavailable: {e}"})
                except Exception as e:
                    await websocket.send_json({"error": f"An error occurred during RAG processing: {e}"})

    except WebSocketDisconnect:
        print("Client disconnected")

# --- Frontend Call ---
@app.get("/")
async def serve_index():
    return FileResponse('static/index.html')