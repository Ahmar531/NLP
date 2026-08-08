/* ─────────────────────────────────────────────────────────────
   api.js  —  The Frontend API Client
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     Instead of writing the backend URL in every component, we
     create one shared Axios client here. If we ever change the
     backend address, we only update it in this one file.

   What it is responsible for:
     1. Creating an Axios instance with the backend base URL.
     2. Exporting a simple function that sends a chat message.

   How it connects to the rest of the project:
     - App.jsx imports sendChatMessage and calls it with the user's text.
     - This file sends an HTTP POST to FastAPI and returns the JSON body.

   What Axios is:
     Axios is a small JavaScript library that makes HTTP requests
     (like fetch) but with a nicer API and automatic JSON parsing.
───────────────────────────────────────────────────────────── */

// Import Axios — it is installed via: npm install axios
import axios from 'axios'

// ── Backend URL ────────────────────────────────────────────
// VITE_API_URL is read from a .env file in the frontend folder.
// If the variable is not set, we fall back to localhost:8000.
//
// To override this, create frontend/.env and add:
//   VITE_API_URL=http://127.0.0.1:8000
//
// Vite requires all env variables to start with VITE_ so they
// are safe to expose in the browser.
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

// ── Axios Instance ─────────────────────────────────────────
// We create a reusable Axios instance so every request
// automatically uses the same base URL and headers.
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    // Tell the backend we are sending JSON data
    'Content-Type': 'application/json',
  },
  // If the backend takes longer than 120 seconds, cancel the request.
  // Local models can be slow on first load, so we give it extra time.
  timeout: 120_000,
})

// ── sendChatMessage Function ───────────────────────────────
// What it does:
//   Sends the user's message text to the FastAPI /chat endpoint.
//
// When it is called:
//   App.jsx calls it inside the handleSend function every time
//   the user submits a message.
//
// What it returns:
//   A Promise that resolves to the JSON response body.
//   The body looks like: { response: "Hello! How can I help?" }
//
// Errors:
//   If the request fails (network error, server error, etc.),
//   Axios throws an error that App.jsx catches and shows to the user.
export async function sendChatMessage(message) {
  // POST /chat with the message inside a JSON body
  const response = await api.post('/chat', { message })

  // response.data is the parsed JSON body from FastAPI
  // It contains { response: "..." }
  return response.data
}
