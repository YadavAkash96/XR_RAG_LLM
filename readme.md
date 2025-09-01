# An Interactive Augmented Reality Assistant

A proof-of-concept web application that turns a mobile phone's camera into an interactive, AI-powered assistant. Point your camera at an object, ask a question, and get a relevant short-form video as an answer, overlaid directly onto your view.

<!-- A GIF of the app in action on a mobile phone would be perfect here! -->
<!-- ![Demo GIF](Documentation/demo.gif) -->

---

## Core Idea

Imagine pointing your phone at a complex piece of gym equipment and asking, *"How do I use this for my back?"*

This application solves that by:
1.  **Seeing the World:** Using real-time object detection on the live camera feed to identify what you are looking at.
2.  **Listening to You:** Capturing your voice query and converting it to text.
3.  **Understanding Your Intent:** Combining the identified object ("Chest Press Machine") with your transcribed query ("How do I use this for my back?") to form a rich, contextual search.
4.  **Finding the Answer:** Using a Retrieval-Augmented Generation (RAG) pipeline to search a database of short-form videos (like Instagram Reels, YouTube Shorts, etc.) to find the most relevant clip.
5.  **Showing You How:** Displaying the retrieved video clip as an overlay in the camera view, providing an immediate, visual answer to your question.

## Features

-   **Real-Time Object Detection:** Runs a TensorFlow.js model directly in the browser for low-latency object identification.
-   **Voice-Powered Queries:** Uses a "press and hold" interface to capture voice commands.
-   **Microservices Architecture:** A robust backend built with independent, scalable services for Speech-to-Text and the LLM/RAG pipeline.
-   **WebSocket Communication:** Provides a responsive, real-time connection between the user's browser and the main server.
-   **Augmented Reality Overlay:** Displays bounding boxes for detected objects and the final video response directly on the camera feed.

---

## Architecture

This project uses a microservices architecture orchestrated by a central gateway application. This design ensures that each component is independent, scalable, and easy to maintain.

![System Diagram](Documentation/GymLens.drawio.svg)



## Technology Stack

**Frontend (Client-Side)**
-   **HTML5 / CSS3**
-   **JavaScript (ES6+)**
-   **TensorFlow.js:** For in-browser, real-time object detection (`coco-ssd` model).
-   **Web APIs:** `getUserMedia` (for camera), `MediaRecorder` (for audio), WebSockets (for communication).

**Backend (Server-Side)**
-   **Main App (Gateway):**
    -   **Framework:** FastAPI
    -   **Server:** Uvicorn
-   **STT Service:**
    -   **Framework:** FastAPI
    -   **Speech-to-Text Model:** OpenAI Whisper
    -   **Audio Processing:** `pydub`, `ffmpeg`
-   **RAG-LLM Service:**
    -   **Framework:** FastAPI / Flask
    -   **Core Logic:** Custom RAG pipeline for searching a vector database (e.g., Qdrant, Pinecone).

---

## Project Structure

```
XR_RAG_LLM/
├── main_app/               # The user-facing gateway application
│   ├── app.py              # Main FastAPI server
│   ├── static/             # All frontend files
│   │   ├── index.html
│   │   └── main.js
│   └── requirements.txt
│
├── services/               # Independent backend microservices
│   ├── RAG_LLM/
│   │   ├── app.py
│   │   └── requirements.txt
│   └── STT/
│       ├── whisper_server.py
│       └── requirements.txt
│
├── .env                    # For environment variables
├── config.yaml             # For service URLs and other configs
└── requirements.txt        # Master list (optional)
```

---

## Setup and Installation

**1. Clone the Repository**
```bash
git clone https://github.com/YadavAkash96/XR_RAG_LLM.git
cd XR_RAG_LLM
```

**2. Install FFmpeg**
This project relies on FFmpeg for audio conversion. It must be installed and accessible in your system's PATH.
-   **Windows:** Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` folder to your System PATH.
-   **macOS (Homebrew):** `brew install ffmpeg`
-   **Linux (apt):** `sudo apt update && sudo apt install ffmpeg`

**3. Set Up Python Environments**
It is highly recommended to use a separate virtual environment for each service to avoid dependency conflicts.

```bash
# For the Main App
cd main_app
python -m venv venv
source venv\Scripts\activate
pip install -r requirements.txt
cd ..

# For the STT Service
cd services/STT
python -m venv venv
source venv\Scripts\activate
pip install -r requirements.txt
cd ../..

# For the RAG-LLM Service
cd services/RAG_LLM
python -m venv venv
source venv\Scripts\activate
pip install -r requirements.txt
cd ../..
```

**4. Configure Endpoints**
Copy the `.env_sample` to `.env`. Then, edit the `config.yaml` file to point to the correct URLs for your running services.

```yaml
# config.yaml
services:
  stt_url: "http://localhost:5002/transcribe"
  rag_url: "http://localhost:5001/query"
```

---

## Running the Application

You must run each of the three services in its own terminal.

**Terminal 1: Start the RAG-LLM Service** (Can be cloud hosted)
```bash
cd services/RAG_LLM
source venv\Scripts\activate
# Run your LLM server on port 5001 (or as configured)
uvicorn app:app --host 0.0.0.0 --port 5001
```

**Terminal 2: Start the STT Service**
```bash
cd services/STT
source venv\Scripts\activate
# Run your Whisper server on port 5002 (or as configured)
uvicorn whisper_server:app --host 0.0.0.0 --port 5002
```

**Terminal 3: Start the Main Gateway App**
```bash
cd main_app
source venv\Scripts\activate
# Run the main server on port 5000
uvicorn app:app --host 0.0.0.0 --port 5000
```

You can now access the application on your laptop's browser at `http://localhost:5000`.

---

## Mobile Testing

Mobile browsers require a secure **HTTPS** connection to grant access to the camera. The easiest way to achieve this for local development is with `ngrok`.

1.  **Download and Install** [ngrok](https://ngrok.com/download).
2.  Keep your three servers running.
3.  Open a **new, fourth terminal**.
4.  Run the following command to create a secure tunnel to your main app:
    ```bash
    ngrok http 5000
    ```
5.  `ngrok` will provide a public `https://` URL (e.g., `https://random-string.ngrok-free.app`).
6.  Open this `https://` URL on your phone's browser to test the full application.

## Future Work

-   [ ] **Custom Object Detection Model:** Train a model to recognize specific objects (like different gym machines) with higher accuracy.
-   [ ] **Object Tracking:** Implement object tracking (e.g., with MediaPipe) to keep the video overlay attached to the object as the camera moves.
-   [ ] **Intelligent GIF Generation:** Instead of a video, use a VLM to find the most relevant segment of the video and convert it into a short, looping GIF.
-   [ ] **Native Application:** Port the application to a native iOS/Android app using ARKit/ARCore for a true Augmented Reality experience.
