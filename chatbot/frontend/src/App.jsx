/* ─────────────────────────────────────────────────────────────
   App.jsx  —  The Main Screen
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     This is the top-level component of the React app.
     It is the first component that React renders when the page loads.

   What it is responsible for:
     1. Keeping the list of chat messages in memory (React state).
     2. Keeping track of whether we are waiting for the AI reply.
     3. Calling the backend API when the user sends a message.
     4. Passing data down to child components (ChatWindow, ChatInput).

   How it connects to the rest of the project:
     - It imports sendChatMessage from api.js to talk to FastAPI.
     - It passes messages to ChatWindow so they can be displayed.
     - It passes handleSend and isLoading to ChatInput so the form
       can call the function and disable itself while waiting.
───────────────────────────────────────────────────────────── */

// useState  — lets us store and update data inside a component
// useEffect — lets us run code after the component renders (not used here
//             directly but imported for completeness awareness)
import { useState } from 'react'

// These are the three visual building blocks of the chat UI
import ChatWindow from './components/ChatWindow'
import ChatInput  from './components/ChatInput'

// This function sends the user's text to the backend and returns the AI reply
import { sendChatMessage } from './api'

// ─── App Component ──────────────────────────────────────────
// This is a React "functional component".
// It returns JSX (HTML-like syntax) that React turns into real HTML.
export default function App() {

  // ── State Variables ──────────────────────────────────────
  // React re-renders the component every time a state variable changes.

  // "messages" stores every chat bubble shown on screen.
  // Each message is an object like: { id, role, text }
  // "role" is either 'user' or 'assistant'
  const [messages, setMessages] = useState([])

  // "isLoading" is true while we are waiting for the AI to respond.
  // We use it to show the typing animation and disable the input.
  const [isLoading, setIsLoading] = useState(false)

  // "errorText" stores a message to show the user if something goes wrong.
  const [errorText, setErrorText] = useState('')

  // ── handleSend Function ──────────────────────────────────
  // This function is called when the user clicks Send or presses Enter.
  // It is defined here (not in ChatInput) because it needs to update
  // the messages list, which lives in this component.
  async function handleSend(text) {

    // Clean the text — remove leading/trailing spaces
    const cleanText = text.trim()

    // Do nothing if the message is empty or we are already waiting for a reply
    if (!cleanText || isLoading) {
      return
    }

    // Build a message object for the user's message
    // Date.now() gives us a unique number to use as an ID
    const userMessage = {
      id:   Date.now(),
      role: 'user',
      text: cleanText,
    }

    // Add the user's message to the chat immediately
    // We use the "previous state" pattern (prev => [...prev, newItem])
    // to safely update state based on the current value
    setMessages(prev => [...prev, userMessage])

    // Show the loading indicator
    setIsLoading(true)

    // Clear any previous error message
    setErrorText('')

    try {
      // ── API Call ──────────────────────────────────────────
      // Send the user's text to our FastAPI backend.
      // This is an "await" call — we pause here until the backend replies.
      const data = await sendChatMessage(cleanText)

      // Build a message object for the AI's reply
      const aiMessage = {
        id:   Date.now() + 1,
        role: 'assistant',
        text: data.response,
      }

      // Add the AI reply to the chat history
      setMessages(prev => [...prev, aiMessage])

    } catch (error) {
      // If something went wrong, show a friendly error message
      // We check error.response.data.detail first (FastAPI error format)
      // If that does not exist, we fall back to a generic message
      const apiError =
        error.response?.data?.detail ||
        error.message ||
        'Something went wrong. Is Ollama running?'

      setErrorText(apiError)

    } finally {
      // "finally" runs whether the try succeeded or failed
      // Always turn off the loading indicator when done
      setIsLoading(false)
    }
  }

  // ── JSX (what the component renders) ────────────────────
  return (
    // Full-screen wrapper with the dark gradient background
    <div className="flex min-h-screen items-center justify-center p-3 sm:p-6">

      {/* ── Main Chat Card ─────────────────────────────── */}
      {/* This is the glass card that contains everything */}
      <div className="glass-card flex h-[95vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl shadow-glass">

        {/* ── Header ────────────────────────────────────── */}
        <header className="flex items-center gap-3 border-b border-white/10 px-5 py-4 sm:px-7">

          {/* Bot icon — a simple SVG circle with a spark emoji */}
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-indigo-500/20 text-xl ring-1 ring-indigo-400/30">
            🤖
          </div>

          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-white sm:text-lg">
              AI Chatbot
            </h1>
            <p className="text-xs text-slate-400">
              Powered by Ollama · Running locally on your machine
            </p>
          </div>

          {/* Live status dot — green pulse = Ollama is expected to be running */}
          <div className="ml-auto flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1.5 ring-1 ring-emerald-500/20">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-xs font-medium text-emerald-400">Live</span>
          </div>
        </header>

        {/* ── Chat Body ─────────────────────────────────── */}
        {/* flex-1 makes this section fill all remaining vertical space */}
        <main className="flex min-h-0 flex-1 flex-col">

          {/* The scrollable list of messages */}
          <ChatWindow messages={messages} isLoading={isLoading} />

          {/* ── Error Banner ───────────────────────────── */}
          {/* Only shown when errorText is not empty */}
          {errorText && (
            <div className="flex items-start gap-2 border-t border-red-500/20 bg-red-500/10 px-5 py-3 text-sm text-red-300">
              {/* Warning icon */}
              <svg className="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <span>{errorText}</span>
            </div>
          )}

          {/* The text input and send button at the bottom */}
          <ChatInput onSend={handleSend} isLoading={isLoading} />
        </main>
      </div>
    </div>
  )
}
