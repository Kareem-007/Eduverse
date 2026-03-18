# Eduverse — AI Tutor with Real-Time Voice & Avatar

> A real-time AI tutoring agent powered by Gemini Live API, featuring a lip-synced 3D avatar, bidirectional voice interruption, and a live content panel that renders code, math, and diagrams on the fly.

Built for the **Gemini Live Agent Challenge** — Live Agents category.

---

## Architecture

```
Browser (index.html)
    │
    ├── HTTPS ──────────────────► Firebase Hosting
    │
    └── WSS (WebSocket) ────────► Cloud Run (live_service.py)
                                        │
                                        ├── Gemini Live API (bidi streaming)
                                        └── Secret Manager (GEMINI_API_KEY)
```

**Tech Stack:**
- **Frontend:** Vanilla JS, Web Audio API (AudioWorklet), TalkingHead.js, Three.js
- **Backend:** Python 3.11, google-genai SDK, WebSockets
- **AI:** Gemini 2.5 Flash Native Audio (Live API)
- **Cloud:** Google Cloud Run, Secret Manager, Firebase Hosting
- **Avatar:** Ready Player Me + TalkingHead.js lipsync

---

## Features

- **Real-time voice conversation** — talk naturally, no typing required
- **Bidirectional interruption** — interrupt the tutor mid-sentence naturally
- **Lip-synced 3D avatar** — viseme-based lipsync driven by streamed audio
- **Live content panel** — code blocks, math (KaTeX), diagrams (Mermaid.js) rendered in real-time via Gemini tool calls
- **Gapless audio playback** — scheduled AudioBufferSourceNodes for smooth streaming
- **Camera/screen mode** — optionally stream webcam or screen to Gemini

---

## Project Structure

```
eduverse/
├── index.html              # Frontend — avatar, audio, WebSocket client
├── edu.glb                 # 3D avatar model (Ready Player Me)
├── .gitignore
├── README.md
└── backend/
    ├── live_service.py     # Main backend — Gemini Live API + WebSocket server
    ├── image_input.py      # Image input helper
    ├── gemini_service.py   # Gemini service utilities
    ├── main.py             # Entry point
    ├── requirements.txt    # Python dependencies
    ├── Dockerfile          # Cloud Run container
    └── .env.example        # Environment variable template
```

---

## Local Setup & Running

### Prerequisites

- Python 3.11+
- Node.js 20+ (for Firebase CLI, optional for local dev)
- A [Gemini API key](https://aistudio.google.com/apikey)
- A webcam (optional — use `--mode none` to skip)

### 1. Clone the repo

```bash
git clone https://github.com/Kareem-007/Eduverse.git
cd Eduverse
```

### 2. Set up Python virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Run the backend

```bash
# No camera (recommended for testing)
python live_service.py --mode none

under development and fixations
# With webcam
python live_service.py --mode camera

# With screen capture
python live_service.py --mode screen
```

You should see:
```
[WS] Server started on ws://localhost:8765
```

### 6. Open the frontend

Open `index.html` directly in your browser:

```bash
# Linux
xdg-open ../index.html

# Mac
open ../index.html

# Or just drag index.html into Chrome/Firefox
```

> **Note:** Use a browser that supports Web Audio API and `getUserMedia` (Chrome recommended).

### 7. Start a session

1. Wait for the 3D avatar to load
2. Click **Start Session**
3. Wait for status to show **CONNECTED**
4. Click **Mic On** to start talking
5. Ask Eduverse anything — math, code, science, history

---

## Reproducing the Full Experience

To fully test all features:

| Feature | How to test |
|---|---|
| Voice conversation | Click Mic On and ask a question |
| Interruption | Start talking while the avatar is speaking |
| Code rendering | Ask "show me a Python function for fibonacci" |
| Math rendering | Ask "explain the euler identity" |
| Lipsync | Watch the avatar's mouth sync to the audio |

---

## Cloud Deployment (Google Cloud Run)  (Under development)

The backend is configured for Google Cloud Run deployment.

### Prerequisites
- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed

### Deploy

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# Store API key
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=- --replication-policy=automatic

# Build and push image
gcloud artifacts repositories create eduverse-repo --repository-format=docker --location=us-central1
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/eduverse-repo/backend:latest ./backend
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/eduverse-repo/backend:latest

# Deploy to Cloud Run
gcloud run deploy eduverse-backend \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/eduverse-repo/backend:latest \
  --platform=managed \
  --region=us-central1 \
  --port=8765 \
  --timeout=3600 \
  --concurrency=1 \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --allow-unauthenticated \
  --session-affinity
```

---

## Google Cloud Services Used

- **Gemini Live API** — `gemini-2.5-flash-native-audio-preview` via `google-genai` SDK
- **Cloud Run** — Backend WebSocket server hosting
- **Secret Manager** — Secure API key storage
- **Firebase Hosting** — Frontend static file serving
- **Artifact Registry** — Docker image storage

---

## Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) |

---

## Built With

- [Google Gemini Live API](https://ai.google.dev/gemini-api/docs/live)
- [TalkingHead.js](https://github.com/met4citizen/TalkingHead)
- [Three.js](https://threejs.org/)
- [Ready Player Me](https://readyplayer.me/)
- [Marked.js](https://marked.js.org/)
- [KaTeX](https://katex.org/)
- [Mermaid.js](https://mermaid.js.org/)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

*Built for the Gemini Live Agent Challenge 2026 — #GeminiLiveAgentChallenge*
