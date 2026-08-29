import React from 'react';
import { Sparkles, Plus, Copy, Check, Menu, Trash2, Cpu } from 'lucide-react';

export default function Header({
  sessionId,
  onNewSession,
  onClearChat,
  onToggleSidebar,
  isBackendConnected,
}) {
  const [copied, setCopied] = React.useState(false);

  const copySessionId = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="header-icon-btn sidebar-toggle-btn"
          title="Toggle Sessions Sidebar"
        >
          <Menu size={20} />
        </button>

        <div className="header-brand">
          <div className="brand-logo-glow">
            <Sparkles size={20} className="brand-icon" />
          </div>
          <div className="brand-text-container">
            <div className="brand-name-row">
              <span className="brand-name">Ava</span>
              <span className="brand-tag">AI COMPANION</span>
            </div>
            <div className="backend-status-indicator">
              <span className={`status-dot ${isBackendConnected ? 'online' : 'offline'}`} />
              <span className="status-text">
                {isBackendConnected ? 'Connected' : 'Connecting to Backend...'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="header-right">
        {/* Session ID Chip */}
        <div className="session-chip" onClick={copySessionId} title="Click to copy Session ID">
          <span className="session-label">SESSION:</span>
          <span className="session-id-val">{sessionId.length > 16 ? `${sessionId.slice(0, 14)}...` : sessionId}</span>
          <button type="button" className="copy-session-btn">
            {copied ? <Check size={13} className="text-emerald" /> : <Copy size={13} />}
          </button>
        </div>

        {/* Clear Messages in current session */}
        <button
          type="button"
          onClick={onClearChat}
          className="header-action-btn secondary-btn"
          title="Clear Current Chat View"
        >
          <Trash2 size={16} />
          <span className="btn-label-desktop">Clear</span>
        </button>

        {/* New Session Button */}
        <button
          type="button"
          onClick={onNewSession}
          className="header-action-btn primary-glow-btn"
          title="Start a Fresh Session"
        >
          <Plus size={17} />
          <span className="btn-label-desktop">New Chat</span>
        </button>
      </div>
    </header>
  );
}
