import React from 'react';
import { Sparkles, Image as ImageIcon, Volume2, MessageCircle, HeartHandshake } from 'lucide-react';

const SUGGESTIONS = [
  {
    icon: <MessageCircle size={16} className="text-cyan" />,
    text: "Hey Ava! How is your day going?",
    category: "Chat",
  },
  {
    icon: <ImageIcon size={16} className="text-violet" />,
    text: "Show me a picture of a futuristic cyberpunk neon city at night",
    category: "Generate Image",
  },
  {
    icon: <Volume2 size={16} className="text-rose" />,
    text: "Send me a voice message telling me an inspiring thought for today",
    category: "Voice Note",
  },
  {
    icon: <HeartHandshake size={16} className="text-emerald" />,
    text: "What are you working on right now according to your schedule?",
    category: "Activity",
  },
];

export default function QuickPrompts({ onSelectPrompt }) {
  return (
    <div className="quick-prompts-container">
      <div className="welcome-hero">
        <div className="welcome-avatar-glow">
          <Sparkles size={32} />
        </div>
        <h2 className="welcome-title">Meet Ava, Your AI Companion</h2>
        <p className="welcome-subtitle">
          Powered by LangGraph agent architecture with multimodal chat, image generation, voice transcription, and neural speech synthesis.
        </p>
      </div>

      <div className="suggestions-grid">
        {SUGGESTIONS.map((item, idx) => (
          <button
            key={idx}
            type="button"
            className="suggestion-card"
            onClick={() => onSelectPrompt(item.text)}
          >
            <div className="suggestion-icon-wrap">{item.icon}</div>
            <div className="suggestion-text-wrap">
              <span className="suggestion-category">{item.category}</span>
              <span className="suggestion-text">{item.text}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
