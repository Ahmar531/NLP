/* ─────────────────────────────────────────────────────────────
   ChatInput.jsx  —  The Message Input Form
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     This component handles everything the user types.
     It exists as a separate file so that App.jsx stays focused
     on managing state and does not get cluttered with form logic.

   What it is responsible for:
     1. Letting the user type a message in the text box.
     2. Sending the message when the user presses Enter.
     3. Sending the message when the user clicks the Send button.
     4. Clearing the input box after each send.
     5. Disabling the input and button while waiting for the AI.

   Props it receives from App.jsx:
     - onSend    : a function to call with the typed text
     - isLoading : boolean — disables input while waiting for AI
───────────────────────────────────────────────────────────── */

// useState lets us store and update the text the user is typing
import { useState, useRef, useEffect } from 'react'

export default function ChatInput({ onSend, isLoading }) {

  // ── State ─────────────────────────────────────────────────
  // "text" stores whatever the user has typed so far
  const [text, setText] = useState('')

  // inputRef lets us auto-focus the input when the page loads
  const inputRef = useRef(null)

  // Auto-focus the input field when the component first appears
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Re-focus input after the AI replies so the user can type again
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus()
    }
  }, [isLoading])

  // ── handleSubmit Function ─────────────────────────────────
  // This is called when the form is submitted.
  // The form is submitted when:
  //   a) The user presses Enter in the input field
  //   b) The user clicks the Send button
  function handleSubmit(event) {
    // Prevent the browser from refreshing the page on form submit
    event.preventDefault()

    // Reject if text is blank or we are already waiting for a reply
    if (!text.trim() || isLoading) {
      return
    }

    // Call the parent function (handleSend in App.jsx) with the text
    onSend(text)

    // Clear the input field so the user can type the next message
    setText('')
  }

  // ── handleKeyDown Function ───────────────────────────────
  // Allows Shift+Enter to add a new line, plain Enter to send
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit(event)
    }
  }

  // ── Render ────────────────────────────────────────────────
  return (
    // The form sits at the very bottom of the chat card
    <form
      onSubmit={handleSubmit}
      className="border-t border-white/10 bg-white/5 px-4 py-4 sm:px-6"
    >
      <div className="mx-auto flex w-full max-w-3xl items-end gap-3">

        {/* ── Text Input ──────────────────────────────── */}
        {/* We use a textarea so the input grows with long messages */}
        <label className="sr-only" htmlFor="chat-input">
          Type your message
        </label>

        <textarea
          id="chat-input"
          ref={inputRef}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything… (Enter to send, Shift+Enter for new line)"
          disabled={isLoading}
          className="input-glow min-h-[48px] w-full resize-none rounded-2xl border border-white/10 bg-white/8 px-4 py-3 text-sm text-white placeholder-slate-500 transition disabled:cursor-not-allowed disabled:opacity-50 sm:text-base"
          style={{ background: 'rgba(255,255,255,0.07)' }}
        />

        {/* ── Send Button ─────────────────────────────── */}
        <button
          type="submit"
          id="send-button"
          disabled={isLoading || !text.trim()}
          className="btn-glow flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-500 text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:opacity-50"
          title="Send message"
        >
          {/* Show a spinner icon while loading, send arrow otherwise */}
          {isLoading ? (
            // Simple CSS spinner
            <svg
              className="h-5 w-5 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          ) : (
            // Send arrow icon
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          )}
        </button>
      </div>

      {/* ── Hint text ───────────────────────────────────── */}
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-slate-600">
        Responses are generated by a local Ollama model · No data is sent to the cloud
      </p>
    </form>
  )
}
