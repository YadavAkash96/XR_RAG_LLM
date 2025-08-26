
`XR_RAG_LLM/`
`├── data/`
`├── Documentation/`
`├── ffmpeg/`
`|`
`├── services/                 # <-- RENAMED 'src' for clarity`
`│   ├── RAG_LLM/              
`│   │   ├── app.py            # Runs on its own port (8001)`
`│   │   └── requirements.txt  
`│   │   └── ... (other files)`
`│   │`
`│   └── STT/                  # STT service`
`│       ├── whisper_server.py # Runs on its own port (8000)`
`│       └── requirements.txt  
`│       └── ... (other files)`
`|`
`└── main_app/                 # <-- NEW! user facing gateway app`
    `├── app.py                # The main server the user connects to (e.g., on port 5000)`
    `│`
    `└── static/               
    `│   ├── index.html`
    `│   └── main.js`
    `│`
    `└── requirements.txt'      
`|`
`├── .env`
`├── .gitignore`
`├── config.yaml`
`└── requirements.txt'
