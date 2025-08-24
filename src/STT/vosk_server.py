import sys
import sounddevice as sd
import queue
import json
from vosk import Model, KaldiRecognizer

# Load ASR model (download once from: https://alphacephei.com/vosk/models)
model = Model("E:\XRAI\vosk-model-en-us-0.22-lgraph")  # folder with the Vosk model
samplerate = 16000
rec = KaldiRecognizer(model, samplerate)
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

# Start microphone stream
with sd.RawInputStream(samplerate=samplerate, blocksize=8000, dtype='int16',
                       channels=1, callback=callback):
    print("Listening...")
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text:
                # Use transcript in backend logic
                print("Transcript:", text)  # replace with your own function
