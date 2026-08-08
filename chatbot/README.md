# 🤖 Beginner AI Chatbot — React + FastAPI + Ollama

A fully working, beginner-friendly AI chatbot that runs **100% locally** on your machine.
No cloud, no API keys, no subscription — just your own AI model powered by Ollama.

---

## 📖 What This Project Teaches You

By reading through the code (which is heavily commented), you will learn:

| Concept | Where to find it |
|---|---|
| How a React app sends data to a backend | `frontend/src/api.js` |
| How FastAPI receives and validates data | `backend/app.py` |
| How to call a local AI model | `backend/app.py` → `get_ollama_reply()` |
| How React state works | `frontend/src/App.jsx` |
| How to show a loading indicator | `frontend/src/components/Loading.jsx` |
| How to auto-scroll a chat window | `frontend/src/components/ChatWindow.jsx` |
| How Pydantic validates JSON | `backend/models.py` |

---

## 🗂 Project Structure

```text
chatbot/
│
├── frontend/                  ← The React app (what the user sees)
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx ← Shows the scrollable chat history
│   │   │   ├── Message.jsx    ← One chat bubble (user or AI)
│   │   │   ├── ChatInput.jsx  ← The text box and send button
│   │   │   └── Loading.jsx    ← The "AI is thinking" animation
│   │   ├── App.jsx            ← Main screen; manages chat state
│   │   ├── main.jsx           ← Entry point; mounts React to the page
│   │   ├── api.js             ← Sends HTTP requests to the backend
│   │   └── index.css          ← Global styles (dark theme, animations)
│   ├── index.html             ← The HTML page React is injected into
│   ├── package.json           ← Frontend dependencies (React, Axios, etc.)
│   ├── vite.config.js         ← Vite build tool configuration
│   └── tailwind.config.js     ← Tailwind CSS configuration
│
├── backend/                   ← The FastAPI server (the "brain")
│   ├── app.py                 ← Main backend; defines API routes
│   ├── models.py              ← Pydantic models (data shapes)
│   ├── requirements.txt       ← Python package list
│   └── .env                   ← Config: model name, ports, etc.
│
└── README.md                  ← This file
```

---

## 🔄 How the App Works (Step by Step)

```
User types a message and presses Enter
         │
         ▼
  React (App.jsx)
  - Adds user message to chat history
  - Shows loading indicator
  - Calls sendChatMessage() in api.js
         │
         ▼ HTTP POST /chat  { "message": "Hello" }
         │
  FastAPI (app.py)
  - Validates the request with Pydantic
  - Calls get_ollama_reply(user_message)
         │
         ▼ HTTP POST /api/chat
         │
  Ollama (local AI model)
  - Generates a reply
         │
         ▼ { "message": { "content": "Hello! How can I help?" } }
         │
  FastAPI (app.py)
  - Returns { "response": "Hello! How can I help?" }
         │
         ▼ JSON response
         │
  React (App.jsx)
  - Hides loading indicator
  - Adds AI message to chat history
  - Chat window auto-scrolls to newest message
```

---

## ⚙️ Setup Instructions

Follow these steps **in order**.

### Step 1 — Install Ollama

Download and install Ollama from the official website:

👉 **https://ollama.com**

Ollama is the local AI engine that runs the language model on your machine.

---

### Step 2 — Download an AI Model

Open a terminal and run **one** of these commands to download a model:

```bash
# Small and fast — good for beginners (recommended to start with)
ollama pull llama3.2:1b

# Slightly larger — better quality answers
ollama pull llama3.2:latest

# Alternative models you can try
ollama pull llama3.2:latest
ollama pull qwen2.5:latest
ollama pull mistral:latest
```

> **Note:** `llama3.2:1b` is only about 1 GB. `llama3.2:latest` is larger.
> Choose based on your disk space and RAM.

---

### Step 3 — Start Ollama

In a terminal, run:

```bash
ollama serve
```

Keep this terminal open. Ollama must stay running while you use the chatbot.

You can verify it is running by visiting: **http://localhost:11434**

---

### Step 4 — Configure the Backend

Open `backend/.env` and set your model name:

```env
# The model name must match exactly what you downloaded
MODEL_NAME=llama3.2:1b

# The Ollama server address (leave this as-is unless you changed it)
OLLAMA_HOST=http://localhost:11434

# The React dev server address (leave as-is for local development)
FRONTEND_ORIGIN=http://localhost:5173
```

---

### Step 5 — Start the Backend

Open a **new terminal** in the `backend/` folder and run:

```powershell
# Install dependencies (only needed once)
pip install -r requirements.txt

# Start the FastAPI server
uvicorn app:app --reload
```

The `--reload` flag restarts the server automatically when you edit `app.py`.

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

**Verify the backend is working:**
- Open http://127.0.0.1:8000 — you should see a JSON status message
- Open http://127.0.0.1:8000/health — shows if Ollama is reachable
- Open http://127.0.0.1:8000/docs — interactive API explorer

---

### Step 6 — Start the Frontend

Open a **new terminal** in the `frontend/` folder and run:

```bash
# Install dependencies (only needed once)
npm install

# Start the React development server
npm run dev
```

You should see:
```
  VITE ready in Xms

  ➜  Local: http://localhost:5173/
```

Open **http://localhost:5173** in your browser. The chatbot is ready! 🎉

---

## ❓ Common Errors and Solutions

### ❌ "Could not connect to Ollama"

**Cause:** Ollama is not running.

**Fix:** Open a terminal and run:
```bash
ollama serve
```

---

### ❌ "Model not found" or `404 Not Found` from Ollama

**Cause:** The model in `.env` has not been downloaded, or the name is wrong.

**Fix:**
```bash
# List models you have downloaded
ollama list

# Download the model that matches MODEL_NAME in .env
ollama pull llama3.2:1b
```

---

### ❌ CORS error in the browser console

**Cause:** The `FRONTEND_ORIGIN` in `.env` does not match the actual React URL.

**Fix:** Make sure `backend/.env` says:
```env
FRONTEND_ORIGIN=http://localhost:5173
```

Then restart the backend.

---

### ❌ "Ollama took too long to respond"

**Cause:** The model is loading for the first time (it warms up on first call).

**Fix:** Wait 30–60 seconds and try again. Subsequent calls will be faster.

---

### ❌ `npm: command not found`

**Fix:** Install Node.js from https://nodejs.org (LTS version)

---

### ❌ `pip: command not found`

**Fix:** Install Python 3.10+ from https://python.org

---

### ❌ Frontend shows a blank page

**Fix:**
1. Check the browser console (F12) for errors.
2. Make sure `npm install` was run in the `frontend/` folder.
3. Make sure `npm run dev` is running.

---

## 🧩 How to Change the AI Model

1. Download a new model:
   ```bash
   ollama pull llama3.2:latest
   ```

2. Edit `backend/.env`:
   ```env
       MODEL_NAME=llama3.2:1b
   ```

3. Restart the backend:
   ```bash
   uvicorn app:app --reload
   ```

That is all — the frontend does not need to change.

### Why `use_mmap` is included

This project sends `"use_mmap": true` in the Ollama request body.
That keeps Ollama from launching `llama-server` with `--load-mode none` on this machine,
which avoids the local runner crash we saw during testing.

If you later move to a different Ollama version or machine, you can keep this setting in place.
It does not change the basic React → FastAPI → Ollama flow.

---

## 📚 Learning Notes for Beginners

### Why we use FastAPI (not pure Python)

FastAPI handles a lot of boilerplate automatically:
- It parses JSON bodies using Pydantic models
- It generates interactive API docs at `/docs`
- It validates incoming data and returns errors automatically
- It is fast because it is built on modern Python async features

### Why we use Axios (not fetch)

Axios is a wrapper around the browser's built-in `fetch` API.
It has a cleaner syntax, automatically parses JSON, and makes error handling easier.
For a beginner project, Axios reduces the amount of code you need to write.

### Why messages are lost on page refresh

The chat history is stored in React state (`useState`).
State lives in memory inside the browser tab.
When you refresh the page, React starts from scratch and the state is cleared.

This is intentional in this project — it keeps the code simple.
A production app would save messages to a database (like SQLite or PostgreSQL).

### Why we use a `.env` file

Hard-coding values like model names directly in the code makes them hard to change.
A `.env` file keeps all "configuration" in one place.
When you want to try a different model, you only edit one file.

---

## 🚀 Quick Start (Summary)

```bash
# Terminal 1 — Run Ollama
ollama serve

# Terminal 2 — Run the backend
cd backend
pip install -r requirements.txt
uvicorn app:app --reload

# Terminal 3 — Run the frontend
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173** and start chatting! 🎉
