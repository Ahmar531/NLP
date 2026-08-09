# Small Chatbot

A minimal demonstration chatbot project with a Python backend and a static frontend. It is intended as a lightweight example for experimenting with simple conversational flows, integrating a model or rule-based responder, and connecting a browser UI to a backend API.

## Project Overview

- **Goal:** Provide a tiny end-to-end chat example showing how a static frontend communicates with a Python backend to send user messages and receive bot replies.
- **Components:**
	- `backend/` — Python HTTP service that accepts chat requests and returns responses (see `main.py`).
	- `frontend/` — Static web UI (`index.html`, `script.js`, `style.css`) that sends user input and displays bot replies.

## How it works

- The frontend captures user messages and sends them to the backend over HTTP (usually a `POST /chat` JSON endpoint). The backend processes the message (rule-based logic, ML model call, or third-party API) and returns a JSON response which the frontend renders.
- Data flow:
	1. User types a message in the browser UI.
 2. `script.js` sends the message to the backend (fetch/XHR).
 3. Backend processes message and responds with `{ "reply": "..." }`.
 4. Frontend displays the reply in the chat view.

## Quick Example

- Example `curl` call to the backend (replace host/port as needed):

```powershell
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"message\": \"Hello\"}"
# Expected response: { "reply": "Hi — how can I help?" }
```

- Example frontend fetch (from `frontend/script.js`):

```javascript
fetch('/chat', {
	method: 'POST',
	headers: { 'Content-Type': 'application/json' },
	body: JSON.stringify({ message: userMessage }),
})
.then(r => r.json())
.then(data => showReply(data.reply))
```

## Development & Notes

- Prerequisites: Python 3.10+ for the backend. A modern browser for the frontend.
- Run the backend from the `backend` folder (virtualenv recommended):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
python main.py
```

- If the frontend is opened directly from the file system, adjust fetch URLs or serve it via a static server to avoid CORS/file:// restrictions:

```powershell
cd frontend
python -m http.server 8000
# then open http://localhost:8000
```

- Typical backend concerns: enable CORS during development, add logging, and validate incoming JSON.

## Extending the project

- Swap in a more advanced NLP model, add session/context handling, persist chats to disk or a DB, or add authentication.

## Next steps

- I can update this README with concrete endpoint names and request/response shapes after you confirm how `backend/main.py` implements the API.

## License

MIT (change as needed)
