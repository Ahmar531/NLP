# ✨ Ava - AI Companion & WhatsApp Bot

Ava is a multi-modal AI Companion built with **LangGraph**, **FastAPI**, **React**, and **Groq**.

---

## 📋 Prerequisites

- **Python 3.12+**
- **Node.js 18+** & npm
- **[uv](https://docs.astral.sh/uv/)** (Python Package Manager)
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **ngrok** (for public URL / WhatsApp Webhook)

---

## ⚙️ Step 1: Configure Environment (`.env`)

Create or update `.env` in the root folder:

```env
# Required: Get key from https://console.groq.com/keys
GROQ_API_KEY="gsk_your_groq_api_key_here"

# Optional: ElevenLabs Voice
ELEVENLABS_API_KEY=""
ELEVENLABS_VOICE_ID="kdmDKE6EkgrWrrykO9Qt"

# Optional: Get key from https://api.together.ai/settings/api-keys (falls back to free Pollinations FLUX if empty)
TOGETHER_API_KEY=""

# Optional: Qdrant Cloud (falls back to local SQLite/Qdrant in ./data if empty)
QDRANT_URL=""
QDRANT_API_KEY=""

# Evolution API for WhatsApp
EVOLUTION_API_URL="http://localhost:8080"
EVOLUTION_API_KEY="D4C48552A640-4169-AB43-A4BACEF8347F"
EVOLUTION_INSTANCE="AVA"
```

---

## 📦 Step 2: Install Dependencies

1. **Install Python backend packages:**
   ```powershell
   uv sync
   ```

2. **Install and build Frontend:**
   ```powershell
   cd frontend
   npm install
   npm run build
   cd ..
   ```

---

## 🚀 Step 3: Run the Project

### Terminal 1: Start Backend Server
```powershell
uv run python -m uvicorn ai_companion.interfaces.api.app:app --app-dir src --port 8000 --reload
```
- Open browser: **`http://localhost:8000`**
- API Docs: **`http://localhost:8000/docs`**

### Terminal 2: Expose via ngrok (for WhatsApp Webhook)
```powershell
ngrok http 8000
```
- Open the generated `https://xxxx.ngrok-free.dev` in browser.
- Click **"Visit Site"** on the first prompt to access the chat UI.

---

## 💬 WhatsApp Integration (Evolution API)

1. Start your Evolution API container (Port 8080).
2. Set webhook URL in Evolution API:
   ```text
   http://host.docker.internal:8000/webhook/whatsapp
   ```
   *(or your ngrok URL: `https://xxxx.ngrok-free.dev/webhook/whatsapp`)*
3. Events to enable in Evolution API:
   - `MESSAGES_UPSERT`
   - `MESSAGES_UPDATE`
   - `CONNECTION_UPDATE`

---

## 🧠 Memory Systems

- **Short-Term Memory:** Stored in `./data/memory.db` (remembers active conversation turns).
- **Long-Term Memory:** Stored in `./data/qdrant_db` / Qdrant Cloud (extracts & recalls user facts across sessions).
