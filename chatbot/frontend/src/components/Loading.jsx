/* ─────────────────────────────────────────────────────────────
   Loading.jsx  —  The "AI Is Thinking" Animation
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     When the user sends a message, there is a delay while Ollama
     generates the reply. This component shows three bouncing dots
     so the user knows the app is working and has not frozen.

   What it is responsible for:
     Rendering a pulsing "Thinking..." bubble that looks like
     the AI is about to type something.

   When it is shown:
     ChatWindow renders this component when isLoading is true.
     It disappears as soon as the AI reply arrives.
───────────────────────────────────────────────────────────── */

export default function Loading() {
  return (
    // Same left-aligned layout as an AI message bubble
    <div className="message-enter flex items-end gap-2.5">

      {/* ── AI Avatar ─────────────────────────────────── */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700/60 text-sm ring-1 ring-white/10">
        🤖
      </div>

      {/* ── Bouncing Dots Bubble ──────────────────────── */}
      <div className="rounded-2xl rounded-tl-sm border border-white/10 bg-white/5 px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1.5">
          {/* Three dots that bounce at different times */}
          {/* The CSS animation is defined in index.css as .typing-dot */}
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />

          {/* Small text label next to the dots */}
          <span className="ml-2 text-xs font-medium text-slate-400">
            Thinking…
          </span>
        </div>
      </div>
    </div>
  )
}
