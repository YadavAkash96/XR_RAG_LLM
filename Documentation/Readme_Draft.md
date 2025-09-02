Of course. A great README is crucial for showcasing your work. It should act as the front page, technical manual, and vision statement for your project all at once.

Here is a comprehensive, well-structured `README.md` template tailored specifically to your project. You can copy and paste this directly into a `README.md` file at the root of your GitHub repository.

---

# AR Fitness Coach: A Real-Time RAG-Powered Gym Assistant

<!-- A brief, one-sentence summary of the project. -->
This project is a proof-of-concept for an augmented reality fitness assistant that provides real-time, expert-guided video instructions for gym equipment using a Retrieval-Augmented Generation (RAG) pipeline.

<!-- Optional: Add some professional badges. You can generate these at shields.io -->
![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)![License](https://img.shields.io/badge/license-MIT-green.svg)

---

<!-- A GIF is the best way to showcase your projOf course. A great README is crucial for showcasing your work. It should act as the front page, technical manual, and vision statement for your project all at once.

Here is a comprehensive, well-structured `README.md` template tailored specifically to your project. You can copy and paste this directly into a `README.md` file at the root of your GitHub repository.

---

# AR Fitness Coach: A Real-Time RAG-Powered Gym Assistant

<!-- A brief, one-sentence summary of the project. -->
This project is a proof-of-concept for an augmented reality fitness assistant that provides real-time, expert-guided video instructions for gym equipment using a Retrieval-Augmented Generation (RAG) pipeline.

<!-- Optional: Add some professional badges. You can generate these at shields.io -->
![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)![License](https://img.shields.io/badge/license-MIT-green.svg)

---

<!-- A GIF is the best way to showcase your project. Record your mobile screen and convert it to a GIF. -->
### Demo
*A brief demonstration of the application in action.*

![Demo GIF of the AR Fitness Coach](./assets/demo.gif)
<!-- TODO: Replace this with a real GIF of your application. -->

## 📋 Table of Contents
- [Problem Statement](#-problem-statement)
- [Core Features](#-core-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [How It Works](#-how-it-works)
  - [1. Data Ingestion Pipeline](#1-data-ingestion-pipeline)
  - [2. Real-Time Query Pipeline](#2-real-time-query-pipeline)
- [Setup and Installation](#-setup-and-installation)
- [Usage](#-usage)
- [Future Work](#-future-work)
- [License](#-license)

## 🎯 Problem Statement

Gyms can be intimidating for beginners. Improper form can lead to injury, and it's often difficult to know how to use a specific machine for different workouts. This project aims to solve that by creating an intuitive, on-demand coach that lives in your pocket. By simply pointing your phone at a piece of equipment and asking a question, you can get immediate, trustworthy video guidance from certified experts.

## ✨ Core Features

- **Real-Time Object Recognition:** The mobile front-end identifies gym equipment from the camera feed.
- **Natural Language Queries:** Users can ask questions in plain English (e.g., "how do I use this for my back?").
- **Hybrid RAG Video Retrieval:** A sophisticated back-end combines metadata filtering with semantic search to find the most relevant instructional video.
- **Vetted Expert Content:** The system retrieves short-form videos (Reels, Shorts) exclusively from a database of certified trainers and coaches.
- **Contextual AR Overlay:** The retrieved video is displayed on the user's screen, attached to the real-world object it relates to.
- **Interactive Session Management:** Users can request a new video if they dislike the current one, and the system will provide the next best alternative without showing duplicates.

## 🏗️ System Architecture

The system is designed with a clean separation between the data processing (ingestion) and the real-time query handling (inference).

<!-- You can replace this with your own draw.io SVG file! -->
![System Architecture Diagram](./assets/system_architecture.svg)
<!-- TODO: Add your draw.io SVG to an 'assets' folder and make sure the path is correct. -->

## 💻 Tech Stack

- **Back-End:** Python, FastAPI
- **AI / RAG Pipeline:**
  - **Vector Database:** Qdrant (Cloud Hosted)
  - **Embedding Model:** `BAAI/bge-small-en-v1.5` (via `sentence-transformers`)
  - **Entity Extraction LLM:** Microsoft Phi-3 (via **Ollama**)
- **Data Sourcing:** Custom Python scripts for YouTube data collection.
- **Front-End (Conceptual):** Mobile Application (e.g., React Native, Flutter, Swift) with a real-time object detection model.

## ⚙️ How It Works

### 1. Data Ingestion Pipeline (`ingest_to_qdrant.py`)

This offline process prepares the knowledge base for our RAG system.
1.  **Data Collection:** Short-form videos from certified trainers are identified, and their metadata (URL, title, transcript) is saved to a `.jsonl` file.
2.  **LLM Entity Extraction:** For each video, a local **Phi-3** model running via Ollama analyzes the title and description to extract structured metadata (e.g., `machine_name`, `body_parts`, `exercise_name`).
3.  **Chunking:** The video transcript is broken down into smaller, semantically meaningful text chunks.
4.  **Embedding:** Each text chunk is converted into a vector embedding using the `bge-small-en-v1.5` model.
5.  **Indexing:** The vector, along with its rich metadata payload, is uploaded to a **Qdrant** collection. Payload indexes are created on the metadata fields to enable fast, filtered searches.

### 2. Real-Time Query Pipeline (`query_api.py`)

This is the live API that the mobile application interacts with.
1.  **Contextual Query:** The mobile app detects an object (e.g., "leg press machine") and combines it with the user's voice query (e.g., "how to do this for calves") into a single string.
2.  **Query Analysis:** The API receives the query and uses the local **Phi-3** model to extract entities (e.g., `machine_name: ["leg press"]`, `body_parts: ["calves"]`).
3.  **Hybrid Search Funnel:**
    -   **Metadata Filtering:** It first asks Qdrant to retrieve only the video chunks where the payload metadata matches the extracted entities.
    -   **Semantic Search:** On that pre-filtered set, it then performs a vector similarity search to find the chunks that are most contextually relevant to the user's query.
4.  **Session Filtering:** The API filters out any video URLs that the front-end marked as "already seen" in this session.
5.  **Response:** The API returns a JSON object containing the URL (and embeddable URL) of the top-ranked, unseen video.

## 🚀 Setup and Installation

Follow these steps to get the back-end running locally.

**1. Prerequisites:**
   - Python 3.10+
   - [Ollama](https://ollama.com/) installed on your machine.

**2. Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/your-repo-name.git
   cd your-repo-name
   ```

**3. Set Up Ollama:**
   - Pull the Phi-3 model:
     ```bash
     ollama pull phi3
     ```
   - Ensure the Ollama server is running.

**4. Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   <!-- TODO: Create a requirements.txt file with `pip freeze > requirements.txt` -->

**5. Configure Environment Variables:**
   - Create a file named `.env` in the root directory and add your credentials. Use the `.env.example` as a template.
     ```
     # .env file
     QDRANT_URL="YOUR_QDRANT_CLUSTER_URL"
     QDRANT_API_KEY="YOUR_QDRANT_API_KEY"
     # GOOGLE_API_KEY is optional if using Ollama
     ```

## 🏃 Usage

**1. Run the Data Ingestion Pipeline:**
   - This only needs to be done once to populate your Qdrant database.
   - Make sure your `.jsonl` data file is ready.
   - Run the script:
     ```bash
     python ingest_to_qdrant.py
     ```

**2. Start the API Server:**
   ```bash
   uvicorn query_api:app --reload
   ```

**3. Test the API:**
   - The server will be running on `http://127.0.0.1:8000`.
   - Open your browser and navigate to `http://127.0.0.1:8000/docs` to access the interactive Swagger UI and test the `/query` endpoint.

## 🔮 Future Work

- [ ] Fine-tune the embedding model on a fitness-specific dataset for more accurate semantic search.
- [ ] Implement a user feedback loop (e.g., "Was this video helpful?") to re-rank videos.
- [ ] Expand the video database to cover a wider range of exercises and machines.
- [ ] Improve the front-end AR tracking to more robustly "anchor" the video overlay to the moving object.

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
<!-- TODO: Add a LICENSE file with the MIT license text. -->ect. Record your mobile screen and convert it to a GIF. -->
### Demo
*A brief demonstration of the application in action.*

![Demo GIF of the AR Fitness Coach](./assets/demo.gif)
<!-- TODO: Replace this with a real GIF of your application. -->

## 📋 Table of Contents
- [Problem Statement](#-problem-statement)
- [Core Features](#-core-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [How It Works](#-how-it-works)
  - [1. Data Ingestion Pipeline](#1-data-ingestion-pipeline)
  - [2. Real-Time Query Pipeline](#2-real-time-query-pipeline)
- [Setup and Installation](#-setup-and-installation)
- [Usage](#-usage)
- [Future Work](#-future-work)
- [License](#-license)

## 🎯 Problem Statement

Gyms can be intimidating for beginners. Improper form can lead to injury, and it's often difficult to know how to use a specific machine for different workouts. This project aims to solve that by creating an intuitive, on-demand coach that lives in your pocket. By simply pointing your phone at a piece of equipment and asking a question, you can get immediate, trustworthy video guidance from certified experts.

## ✨ Core Features

- **Real-Time Object Recognition:** The mobile front-end identifies gym equipment from the camera feed.
- **Natural Language Queries:** Users can ask questions in plain English (e.g., "how do I use this for my back?").
- **Hybrid RAG Video Retrieval:** A sophisticated back-end combines metadata filtering with semantic search to find the most relevant instructional video.
- **Vetted Expert Content:** The system retrieves short-form videos (Reels, Shorts) exclusively from a database of certified trainers and coaches.
- **Contextual AR Overlay:** The retrieved video is displayed on the user's screen, attached to the real-world object it relates to.
- **Interactive Session Management:** Users can request a new video if they dislike the current one, and the system will provide the next best alternative without showing duplicates.

## 🏗️ System Architecture

The system is designed with a clean separation between the data processing (ingestion) and the real-time query handling (inference).

<!-- You can replace this with your own draw.io SVG file! -->
![System Architecture Diagram](./assets/system_architecture.svg)
<!-- TODO: Add your draw.io SVG to an 'assets' folder and make sure the path is correct. -->

## 💻 Tech Stack

- **Back-End:** Python, FastAPI
- **AI / RAG Pipeline:**
  - **Vector Database:** Qdrant (Cloud Hosted)
  - **Embedding Model:** `BAAI/bge-small-en-v1.5` (via `sentence-transformers`)
  - **Entity Extraction LLM:** Microsoft Phi-3 (via **Ollama**)
- **Data Sourcing:** Custom Python scripts for YouTube data collection.
- **Front-End (Conceptual):** Mobile Application (e.g., React Native, Flutter, Swift) with a real-time object detection model.

## ⚙️ How It Works

### 1. Data Ingestion Pipeline (`ingest_to_qdrant.py`)

This offline process prepares the knowledge base for our RAG system.
1.  **Data Collection:** Short-form videos from certified trainers are identified, and their metadata (URL, title, transcript) is saved to a `.jsonl` file.
2.  **LLM Entity Extraction:** For each video, a local **Phi-3** model running via Ollama analyzes the title and description to extract structured metadata (e.g., `machine_name`, `body_parts`, `exercise_name`).
3.  **Chunking:** The video transcript is broken down into smaller, semantically meaningful text chunks.
4.  **Embedding:** Each text chunk is converted into a vector embedding using the `bge-small-en-v1.5` model.
5.  **Indexing:** The vector, along with its rich metadata payload, is uploaded to a **Qdrant** collection. Payload indexes are created on the metadata fields to enable fast, filtered searches.

### 2. Real-Time Query Pipeline (`query_api.py`)

This is the live API that the mobile application interacts with.
1.  **Contextual Query:** The mobile app detects an object (e.g., "leg press machine") and combines it with the user's voice query (e.g., "how to do this for calves") into a single string.
2.  **Query Analysis:** The API receives the query and uses the local **Phi-3** model to extract entities (e.g., `machine_name: ["leg press"]`, `body_parts: ["calves"]`).
3.  **Hybrid Search Funnel:**
    -   **Metadata Filtering:** It first asks Qdrant to retrieve only the video chunks where the payload metadata matches the extracted entities.
    -   **Semantic Search:** On that pre-filtered set, it then performs a vector similarity search to find the chunks that are most contextually relevant to the user's query.
4.  **Session Filtering:** The API filters out any video URLs that the front-end marked as "already seen" in this session.
5.  **Response:** The API returns a JSON object containing the URL (and embeddable URL) of the top-ranked, unseen video.

## 🚀 Setup and Installation

Follow these steps to get the back-end running locally.

**1. Prerequisites:**
   - Python 3.10+
   - [Ollama](https://ollama.com/) installed on your machine.

**2. Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/your-repo-name.git
   cd your-repo-name
   ```

**3. Set Up Ollama:**
   - Pull the Phi-3 model:
     ```bash
     ollama pull phi3
     ```
   - Ensure the Ollama server is running.

**4. Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   <!-- TODO: Create a requirements.txt file with `pip freeze > requirements.txt` -->

**5. Configure Environment Variables:**
   - Create a file named `.env` in the root directory and add your credentials. Use the `.env.example` as a template.
     ```
     # .env file
     QDRANT_URL="YOUR_QDRANT_CLUSTER_URL"
     QDRANT_API_KEY="YOUR_QDRANT_API_KEY"
     # GOOGLE_API_KEY is optional if using Ollama
     ```

## 🏃 Usage

**1. Run the Data Ingestion Pipeline:**
   - This only needs to be done once to populate your Qdrant database.
   - Make sure your `.jsonl` data file is ready.
   - Run the script:
     ```bash
     python ingest_to_qdrant.py
     ```

**2. Start the API Server:**
   ```bash
   uvicorn query_api:app --reload
   ```

**3. Test the API:**
   - The server will be running on `http://127.0.0.1:8000`.
   - Open your browser and navigate to `http://127.0.0.1:8000/docs` to access the interactive Swagger UI and test the `/query` endpoint.

## 🔮 Future Work

- [ ] Fine-tune the embedding model on a fitness-specific dataset for more accurate semantic search.
- [ ] Implement a user feedback loop (e.g., "Was this video helpful?") to re-rank videos.
- [ ] Expand the video database to cover a wider range of exercises and machines.
- [ ] Improve the front-end AR tracking to more robustly "anchor" the video overlay to the moving object.

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
<!-- TODO: Add a LICENSE file with the MIT license text. -->