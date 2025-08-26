import io
import os
import tempfile
from fastapi import FastAPI, UploadFile, WebSocket
from fastapi.params import File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydub import AudioSegment
import requests
import whisper


AudioSegment.converter = "E:/XRAI/XR_RAG_LLM/ffmpeg/bin/ffmpeg.exe"
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

model = whisper.load_model("small")  # choose model size

LLM_ENDPOINT = "http://192.168.0.232:8001/ask_xr"

async def process_audio_and_transcribe(audio_bytes: bytes) -> str:
    """
    Takes raw audio bytes, converts them, and returns the transcribed text.
    This version explicitly creates, closes, and cleans up the temporary WAV file
    to prevent any file-locking permission errors on Windows.
    """
    print("--- Starting Audio Processing (Explicit File Path) ---")
    
    # Create a temporary file path for the WAV file
    wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(wav_fd) # Close the file handle immediately

    try:
        # 1. Load initial audio data from memory
        print("1. Loading audio from memory...")
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        
        # 2. Export the audio to the temporary WAV file path.
        #    pydub will handle opening, writing, and closing the file.
        print(f"2. Converting and exporting to WAV file: {wav_path}")
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(wav_path, format="wav")
        
        # 3. Transcribe with Whisper. The file is now closed and safe to read.
        print("3. Transcribing with Whisper...")
        result = model.transcribe(wav_path, fp16=False)
        transcribed_text = result["text"].strip()
        
        print(f"4. Transcription successful: '{transcribed_text}'")
        return transcribed_text

    except Exception as e:
        print(f"!!! A critical error occurred: {e}")
        return f"[Error processing audio: {e}]"
    
    finally:
        # 4. CRUCIAL: Clean up the temporary file, no matter what happens.
        if os.path.exists(wav_path):
            print(f"5. Cleaning up temporary file: {wav_path}")
            os.remove(wav_path)

            
@app.get("/")
async def index():
    return FileResponse("static/whisper_index.html")

# 1. NEW: HTTP Endpoint for Service-to-Service Communication
# This is the endpoint your main_app.py will call.
@app.post("/transcribe")
async def http_transcribe(audio_file: UploadFile = File(...)):
    """
    Receives an audio file via HTTP POST, transcribes it, and returns
    the transcription in a JSON response.
    """
    audio_bytes = await audio_file.read()
    transcribed_text = await process_audio_and_transcribe(audio_bytes)
    
    # Return a standard JSON response
    return JSONResponse(content={"transcription": transcribed_text})

@app.websocket("/ws/transcribe")
async def ws_transcribe(ws: WebSocket):
    """
    Handles real-time audio transcription over a WebSocket connection.
    Ideal for direct testing from a browser UI.
    """
    await ws.accept()

    try:
        # receive a single blob
        data = await ws.receive_bytes()
        transcribed_text = await process_audio_and_transcribe(data)
        print(f"Transcription: {transcribed_text}")

        # Send to LLM
        # llm_payload = {"query": transcribed_text}
        # llm_response = requests.post(LLM_ENDPOINT, json=llm_payload, timeout=30)
        # llm_json = llm_response.json()

        # # Format response for client
        # formatted_response = f"{transcribed_text['text'].strip()}\n\n"
        # # Format response for client nicely
        # formatted_response += f"📌 Goal:\n{llm_json.get('goal','')}\n\n"
        # steps = llm_json.get("steps", [])
        # if steps:
        #     formatted_response += "📝 Steps:\n"
        #     for i, step in enumerate(steps, 1):
        #         formatted_response += f"  {i}. {step}\n"

        # warnings = llm_json.get("warnings", [])
        # if warnings:
        #     formatted_response += "\n⚠️ Warnings:\n"
        #     for w in warnings:
        #         formatted_response += f"  - {w}\n"

        # sources = llm_json.get("sources", [])
        # if sources:
        #     formatted_response += "\n📚 Sources:\n"
        #     for s in sources:
        #         formatted_response += f"  - {s}\n"

        # # send final response to client
        # await ws.send_text(formatted_response)
        # await ws.close()
        
        
        await ws.send_text(transcribed_text)
        await ws.close()

    except Exception as e:
        await ws.close()
        print("Error:", e)

