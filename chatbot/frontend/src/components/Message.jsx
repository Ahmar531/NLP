/* ─────────────────────────────────────────────────────────────
   Message.jsx  —  A Single Chat Bubble
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     Every message in the chat needs to look like a bubble.
     This file makes one bubble. ChatWindow calls it once per message.

   What it is responsible for:
     1. Deciding if the bubble should be on the LEFT (AI) or RIGHT (user).
     2. Choosing the correct colours for each side.
     3. Showing a small avatar icon next to each bubble.
     4. Rendering the message text inside the bubble.

   Props it receives from ChatWindow.jsx:
     - message : an object with { id, role, text }
       - role is 'user' or 'assistant'
       - text is the message string
───────────────────────────────────────────────────────────── */

export default function Message({ message }) {

  // ── Role Check ────────────────────────────────────────────
  // "isUser" is true when the message was sent by the human.
  // We use this boolean to flip the alignment and choose colours.
  const isUser = message.role === 'user'

  // ── Render ────────────────────────────────────────────────
  return (
    // The outer div uses flexbox to push user messages to the RIGHT
    // and AI messages to the LEFT using justify-end / justify-start
    <div className={`message-enter flex items-end gap-2.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>

      {/* ── Avatar Icon ─────────────────────────────────── */}
      {/* A small circle showing who sent the message */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm ring-1 ${
          isUser
            ? 'bg-indigo-500/30 ring-indigo-400/30'   // Purple tint for user
            : 'bg-slate-700/60 ring-white/10'          // Dark tint for AI
        }`}
      >
        {/* Show a person emoji for user, robot for AI */}
        {isUser ? '🧑' : '🤖'}
      </div>

      {/* ── Bubble ──────────────────────────────────────── */}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm sm:max-w-[70%] sm:text-base ${
          isUser
            // User bubble: indigo gradient, white text, rounded differently on the right
            ? 'rounded-tr-sm bg-gradient-to-br from-indigo-500 to-indigo-600 text-white'
            // AI bubble: dark glass look, light text, rounded differently on the left
            : 'rounded-tl-sm border border-white/10 bg-white/5 text-slate-200'
        }`}
      >
        {/* The actual message text */}
        {/* whitespace-pre-wrap preserves newlines in the message */}
        <p className="whitespace-pre-wrap">{message.text}</p>
      </div>
    </div>
  )
}
