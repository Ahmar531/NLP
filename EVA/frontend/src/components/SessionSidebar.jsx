import React from 'react';
import { MessageSquare, Plus, Trash2, X, Sparkles, Clock, ChevronRight } from 'lucide-react';

export default function SessionSidebar({
  isOpen,
  onClose,
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}) {
  return (
    <>
      {/* Backdrop for mobile */}
      {isOpen && <div className="sidebar-backdrop" onClick={onClose} />}

      <aside className={`sessions-sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-title-row">
            <Sparkles size={18} className="text-violet" />
            <span className="sidebar-title">Conversations</span>
          </div>
          <button type="button" onClick={onClose} className="sidebar-close-btn" title="Close Sidebar">
            <X size={18} />
          </button>
        </div>

        <div className="sidebar-new-btn-container">
          <button
            type="button"
            onClick={() => {
              onNewSession();
              if (window.innerWidth < 768) onClose();
            }}
            className="sidebar-new-chat-btn"
          >
            <Plus size={16} />
            <span>Start New Chat</span>
          </button>
        </div>

        <div className="sidebar-session-list">
          <div className="sidebar-section-label">RECENT SESSIONS</div>
          {sessions.length === 0 ? (
            <div className="empty-sessions-hint">No saved sessions yet.</div>
          ) : (
            sessions.map((sess) => {
              const isActive = sess.id === currentSessionId;
              return (
                <div
                  key={sess.id}
                  className={`session-item ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    onSelectSession(sess.id);
                    if (window.innerWidth < 768) onClose();
                  }}
                >
                  <MessageSquare size={16} className={`session-item-icon ${isActive ? 'text-violet' : ''}`} />
                  
                  <div className="session-item-info">
                    <span className="session-item-title">
                      {sess.title || `Session ${sess.id.slice(0, 8)}`}
                    </span>
                    <span className="session-item-date">
                      {sess.lastUpdated || 'Active'}
                    </span>
                  </div>

                  {/* Delete session button (except if it's the only one) */}
                  {sessions.length > 1 && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(sess.id);
                      }}
                      className="session-delete-btn"
                      title="Delete Session"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-footer-card">
            <div className="feature-dot" />
            <div className="feature-text">
              <strong>LangGraph + SQLite</strong>
              <p>Thread memory persists per session</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
