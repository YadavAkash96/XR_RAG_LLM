import tempfile
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydub import AudioSegment
import requests
import whisper

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

model = whisper.load_model("small")  # choose model size

LLM_ENDPOINT = "http://192.168.0.232:8001/ask_xr"

@app.get("/")
async def index():
    return FileResponse("static/whisper_index.html")

@app.websocket("/ws/transcribe")
async def ws_transcribe(ws: WebSocket):
    await ws.accept()

    try:
        # receive a single blob
        data = await ws.receive_bytes()

        # save WebM/Opus blob
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(data)
            webm_path = f.name

        # convert to WAV PCM16
        wav_temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio = AudioSegment.from_file(webm_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(wav_temp.name, format="wav")

        # transcribe with Whisper
        result = model.transcribe(wav_temp.name, fp16=False)
        transcribed_text = result["text"].strip()
        print(f"Transcription: {result['text'].strip()}")

        # Send to LLM
        llm_payload = {"query": transcribed_text}
        llm_response = requests.post(LLM_ENDPOINT, json=llm_payload, timeout=30)
        llm_json = llm_response.json()

        # Format response for client
        formatted_response = f"{result['text'].strip()}\n\n"
        # Format response for client nicely
        formatted_response += f"📌 Goal:\n{llm_json.get('goal','')}\n\n"
        steps = llm_json.get("steps", [])
        if steps:
            formatted_response += "📝 Steps:\n"
            for i, step in enumerate(steps, 1):
                formatted_response += f"  {i}. {step}\n"

        warnings = llm_json.get("warnings", [])
        if warnings:
            formatted_response += "\n⚠️ Warnings:\n"
            for w in warnings:
                formatted_response += f"  - {w}\n"

        sources = llm_json.get("sources", [])
        if sources:
            formatted_response += "\n📚 Sources:\n"
            for s in sources:
                formatted_response += f"  - {s}\n"

        # send final response to client
        await ws.send_text(formatted_response)
        await ws.close()
        
        
        # await ws.send_text(result["text"].strip())
        # await ws.close()

    except Exception as e:
        await ws.close()
        print("Error:", e)
