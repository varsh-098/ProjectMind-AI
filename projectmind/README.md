# ProjectMind AI

A project-aware AI development workspace.

## Architecture Roadmap

```
Phase 3: llama-server → Nemotron (HTTP API)
Phase 4: Python → llama-server → Nemotron
Phase 5: FastAPI → Python → llama-server → Nemotron
...
```

## Running the stack

### 1. Start Nemotron via llama-server

```powershell
llama-server.exe --hf-repo nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF --hf-file NVIDIA-Nemotron3-Nano-4B-Q4_K_M.gguf --host 127.0.0.1 --port 8081 --n-gpu-layers 33
```

### 2. Test llama-server is alive

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8081/health"
```

### 3. Run FastAPI backend (Phase 5)

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

### 4. Test the chat endpoint

```powershell
$body = '{"question": "What is an API?"}' | ConvertFrom-Json | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method POST -ContentType "application/json" -Body $body
```

## Project Structure

```
projectmind/
├── README.md
├── .env                    ← API keys (never commit)
├── .gitignore
├── backend/
│   ├── main.py             ← FastAPI app
│   ├── routers/
│   │   └── chat.py         ← /chat and /health routes
│   ├── services/
│   │   └── nemotron.py     ← llama-server client
│   └── requirements.txt
└── scripts/
    └── test_http.ps1       ← Raw HTTP test (Phase 3)
```
