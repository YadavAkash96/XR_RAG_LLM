# AR Fitness Coach

An interactive, AI-powered web application that provides real-time video instructions for gym equipment using a Retrieval-Augmented Generation (RAG) pipeline and a live camera feed. This project serves as a proof-of-concept for a future XR/AR gym assistant.

![System Diagram](Documentation/GymLens.drawio.svg)

---

## Table of Contents

- [Core Idea](#core-idea)
- [How It Works](#how-it-works)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [Future Work](#future-work)

## Core Idea

The modern gym can be an intimidating environment. Beginners often struggle with proper form and are unsure how to use complex equipment, creating a barrier to entry and a risk of injury.

This project tackles that problem by creating an on-demand virtual coach. By simply pointing a mobile phone at a piece of equipment and asking a question, the user receives immediate, expert-guided video instruction, overlaid in an augmented reality-style view.

## How It Works

The application operates as a real-time pipeline, turning a user's visual and vocal query into a precise answer.

1.  **Contextual Awareness:** The front-end uses **TensorFlow.js** to run a real-time object detection model (`coco-ssd`) in the browser, identifying what the user is pointing their camera at.
2.  **Voice Query:** A "press-and-hold" interface captures the user's spoken question using the `MediaRecorder` API.
3.  **Orchestration:** A central **FastAPI Gateway** receives the target object and the audio via a **WebSocket**. It orchestrates the backend workflow:
    *   First, it calls a dedicated **Speech-to-Text (STT) microservice** running **OpenAI Whisper** to transcribe the audio.
    *   Next, it combines the transcribed text with the target object name to form a rich, contextual query (e.g., *"how do I use this for my back lat pulldown machine"*).
4.  **RAG-Powered Retrieval:** The gateway sends this rich query to the **RAG microservice**.
    *   This service uses a local LLM (**Ollama/Phi-3**) to extract key entities (`machine_name`, `body_parts`).
    *   It then performs a hybrid search on a **Qdrant** vector database, first filtering by metadata and then performing a semantic search on video transcripts.
5.  **Interactive Response:** The best video result is sent back through the WebSocket to the front-end, where it's displayed as an overlay. The front-end intelligently handles YouTube embeds vs. clickable thumbnails for other platforms and manages the "Show Me Another" feature.

## Technology Stack

This project is built on a robust, scalable microservice architecture.

#### **Backend**
- **Frameworks:** FastAPI, Uvicorn
- **Real-Time Communication:** WebSockets
- **RAG & Search:**
  - **Vector Database:** Qdrant
  - **Embedding Model:** `BAAI/bge-base-en-v1.5`
  - **Entity Extraction LLM:** Microsoft Phi-3 (via Ollama)
- **Speech-to-Text:** OpenAI Whisper
- **Configuration:** YAML, `.env`

#### **Frontend**
- **Core:** HTML5, CSS3, Vanilla JavaScript (ES6+)
- **In-Browser AI:** TensorFlow.js (`coco-ssd` model)
- **Web APIs:** `getUserMedia` (Camera), `MediaRecorder` (Audio)

#### **Data Sourcing Pipeline**
- **Automation:** Python, Apify Client, `yt-dlp`
- **Video Transcription:** OpenAI Whisper

## Project Structure

```
.
├── main_app/               # Main Gateway & Frontend Server
│   ├── app.py
│   └── static/
│       ├── index.html
│       └── main.js
├── services/               # Independent Backend Microservices
│   ├── RAG_Service/
│   │   └── query_api.py
│   └── STT_Service/
│       └── stt_server.py
├── data_pipelines/         # Offline scripts for data collection & ingestion
│   ├── _video_extraction_pipeline.py
│   └── ingest_to_qdrant.py
├── assets/                 # Diagrams and other assets
│   └── GymLens.drawio.svg
├── .env                    # Environment variables (API keys)
└── config.yaml             # Service URLs and configurations
```

## Setup & Installation

Follow these steps to set up the local development environment.

#### **1. Prerequisites**
- Python 3.10+
- [Ollama](https://ollama.com/) installed
- [FFmpeg](https://ffmpeg.org/download.html) installed and available in your system's PATH.

#### **2. Clone & Set Up Ollama**
```bash
git clone https://github.com/YadavAkash96/XR_RAG_LLM.git
cd XR_RAG_LLM
# Pull the required LLM for entity extraction
ollama pull phi3
```

#### **3. Install Python Dependencies**
It is highly recommended to create a separate virtual environment for each service.

```bash
# Example for the main_app
cd main_app
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
# Repeat for services/RAG_Service and services/STT_Service
```
<!-- TODO: Create requirements.txt for each service -->

#### **4. Configure Environment**
Create a `.env` file for your API keys. Then, edit `config.yaml` to match the ports your services will run on.

```yaml
# config.yaml (example)
services:
  STT_ENDPOINT: "http://localhost:5002/transcribe"
  LLM_ENDPOINT: "http://localhost:8001/query"
```

## Running the Application

Each service must be run in a separate terminal.

**Terminal 1: Start the RAG Service**
```bash
cd services/RAG_Service
# source venv/bin/activate
uvicorn query_api:app --reload --port 8001
```

**Terminal 2: Start the STT Service**
```bash
cd services/STT_Service
# source venv/bin/activate
uvicorn stt_server:app --reload --port 5002
```

**Terminal 3: Start the Main Gateway**
```bash
cd main_app
# source venv/bin/activate
uvicorn app:app --reload --port 5000
```

You can now access the application at **`http://localhost:5000`**.

> **Note on Mobile Testing:** Mobile browsers require a secure **HTTPS** connection for camera/mic access. Use a tool like **[ngrok](https://ngrok.com/)** to create a secure tunnel to your main app: `ngrok http 5000`.

## Future Work

- [ ] **Custom Object Detection:** Train a custom, high-performance model (e.g., with YOLOv8 or TFLite Model Maker) to recognize specific gym equipment with greater accuracy.
- [ ] **Object Tracking:** Implement tracking to keep the video overlay "anchored" to the object as the camera moves.
- [ ] **XR Integration:** Port the front-end to an XR device (e.g., Meta Quest) using WebXR for a true augmented reality experience.
- [ ] **Feedback Loop:** Add a user feedback mechanism ("Was this video helpful?") to re-rank results and improve the RAG system over time.
