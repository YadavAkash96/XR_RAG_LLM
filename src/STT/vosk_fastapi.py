import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from vosk import Model, KaldiRecognizer

# ---- config ----
MODEL_PATH = os.environ.get("VOSK_MODEL_PATH", "E:/XRAI/vosk-model-en-us-0.22-lgraph")       # E:/XRAI/vosk-model-en-us-0.22-lgraph
SAMPLE_RATE = 16000  # expect 16 kHz PCM16 mono

# ---- load model once ----
model = Model(MODEL_PATH)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    with open("static/vosk_index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/transcribe")
async def transcribe_ws(websocket: WebSocket):
    await websocket.accept()
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"] is not None:
                chunk = message["bytes"]  # raw PCM16 LE mono @16k
                if rec.AcceptWaveform(chunk):
                    result = json.loads(rec.Result())
                    await websocket.send_json({"final": result.get("text", "")})
                else:
                    partial = json.loads(rec.PartialResult())
                    await websocket.send_json({"partial": partial.get("partial", "")})
            elif "text" in message:
                # optional control messages from client
                if message["text"] == "close":
                    final = json.loads(rec.FinalResult())
                    await websocket.send_json({"final": final.get("text", "")})
                    await websocket.close()
                    break
    except WebSocketDisconnect:
        # client disconnected; finalize silently
        _ = rec.FinalResult()
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
