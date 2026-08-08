/* ─────────────────────────────────────────────────────────────
   ChatWindow.jsx  —  The Scrollable Message List
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     This component is responsible for showing all the messages
     in the conversation. It also automatically scrolls down
     whenever a new message appears.

   What it is responsible for:
     1. Looping through the messages array and rendering each one.
     2. Showing the Loading animation while waiting for the AI.
     3. Showing a welcome screen when no messages exist yet.
     4. Scrolling to the newest message automatically.

   Props it receives from App.jsx:
     - messages  : array of message objects { id, role, text }
     - isLoading : boolean — true when waiting for the AI reply
───────────────────────────────────────────────────────────── */

// useEffect — runs code after the component renders or updates
// useRef    — creates a reference to a real DOM element
import { useEffect, useRef } from 'react'

// Message shows one single chat bubble
import Message from './Message'

// Loading shows the three bouncing dots while the AI is thinking
import Loading from './Loading'

export default function ChatWindow({ messages, isLoading }) {

  // ── Auto-scroll Setup ────────────────────────────────────
  // bottomRef is a pointer to an invisible <div> at the very bottom
  // of the message list. We scroll to it when messages change.
  const bottomRef = useRef(null)

  // useEffect watches the messages array and isLoading flag.
  // Every time either one changes, we scroll smoothly to the bottom.
  useEffect(() => {
    // Optional chaining (?.) prevents a crash if bottomRef is not ready yet
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // ── Render ───────────────────────────────────────────────
  return (
    // overflow-y-auto — adds a scrollbar when messages overflow the container
    // flex-1          — makes this section fill all available vertical space
    // chat-scroll     — the custom scrollbar class from index.css
    <div className="chat-scroll min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">

      {/* Inner wrapper centres the messages and limits their max width */}
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">

        {/* ── Welcome Screen ──────────────────────────── */}
        {/* Shown only when there are no messages yet */}
        {messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center gap-5 py-16 text-center">

            {/* Big bot emoji as a decorative header */}
            <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-indigo-500/20 text-4xl ring-1 ring-indigo-400/20">
              🤖
            </div>

            <div>
              <h2 className="text-xl font-semibold text-white">
                How can I help you today?
              </h2>
              <p className="mt-2 max-w-xs text-sm text-slate-400">
                Type a message below and press{' '}
                <kbd className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-xs text-slate-300">
                  Enter
                </kbd>{' '}
                or click <strong className="text-slate-200">Send</strong> to start chatting.
              </p>
            </div>

            {/* Suggestion chips — clicking one fills the input */}
            <div className="flex flex-wrap justify-center gap-2">
              {[
                '👋 What can you do?',
                '🐍 Explain Python loops',
                '⚛️  How does React work?',
                '🤔 What is an API?',
              ].map((suggestion) => (
                <span
                  key={suggestion}
                  className="cursor-default rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-white/10"
                >
                  {suggestion}
                </span>
              ))}
            </div>
          </div>
        ) : (
          // ── Message List ─────────────────────────────
          // Loop through every message and render a <Message> bubble
          messages.map((message) => (
            <Message key={message.id} message={message} />
          ))
        )}

        {/* ── Loading Indicator ────────────────────────── */}
        {/* Shown at the bottom while we wait for the AI to reply */}
        {isLoading && <Loading />}

        {/* ── Scroll Anchor ────────────────────────────── */}
        {/* This invisible div is what we scroll into view */}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
