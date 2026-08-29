import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Mic,
  Image as ImageIcon,
  Paperclip,
  X,
  Sparkles,
  Loader2,
  AlertCircle,
  FileAudio,
  Radio,
} from 'lucide-react';

import Header from './components/Header';
import MessageBubble from './components/MessageBubble';
import VoiceRecorder from './components/VoiceRecorder';
import ImageModal from './components/ImageModal';
import SessionSidebar from './components/SessionSidebar';
import QuickPrompts from './components/QuickPrompts';

import {
  sendChatMessage,
  sendChatMessageStream,
  sendAudioMessage,
  sendImageMessage,
  getSessionHistory,
  checkBackendHealth,
} from './api';

import './App.css';

// Helper to generate unique session IDs
function generateSessionId() {
  return `session_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
}

export default function App() {
  // ─── Session Management ──────────────────────────────────────────────────
  const [sessions, setSessions] = useState(() => {
    try {
      const saved = localStorage.getItem('eva_chat_sessions');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [currentSessionId, setCurrentSessionId] = useState(() => {
    const savedId = localStorage.getItem('eva_active_session_id');
    if (savedId) return savedId;
    const initialId = generateSessionId();
    localStorage.setItem('eva_active_session_id', initialId);
    return initialId;
  });

  // ─── Chat States ─────────────────────────────────────────────────────────
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(`eva_messages_${currentSessionId}`);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [inputText, setInputText] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);
  const [isRecordingMode, setIsRecordingMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // ─── UI & Auxiliary States ───────────────────────────────────────────────
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [modalImageUrl, setModalImageUrl] = useState(null);
  const [isBackendConnected, setIsBackendConnected] = useState(true);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const audioFileInputRef = useRef(null);
  const imageFileInputRef = useRef(null);

  // ─── Health Polling & Initialization ─────────────────────────────────────
  useEffect(() => {
    const checkHealth = async () => {
      const healthy = await checkBackendHealth();
      setIsBackendConnected(healthy);
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Save current messages whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(`eva_messages_${currentSessionId}`, JSON.stringify(messages));
    } catch (e) {
      console.warn('Failed to save messages to local storage:', e);
    }
  }, [messages, currentSessionId]);

  // Update sessions list metadata
  useEffect(() => {
    setSessions((prev) => {
      const existing = prev.find((s) => s.id === currentSessionId);
      const title = messages.length > 0
        ? messages[0].content?.slice(0, 30) || 'Active Chat'
        : 'New Conversation';

      const updated = existing
        ? prev.map((s) => (s.id === currentSessionId ? { ...s, title, lastUpdated: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } : s))
        : [{ id: currentSessionId, title, lastUpdated: 'Just now' }, ...prev];

      localStorage.setItem('eva_chat_sessions', JSON.stringify(updated));
      return updated;
    });
  }, [messages, currentSessionId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Format current time
  const getCurrentTime = () => {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // ─── Session Actions ─────────────────────────────────────────────────────
  const handleNewSession = () => {
    const newId = generateSessionId();
    setCurrentSessionId(newId);
    localStorage.setItem('eva_active_session_id', newId);
    setMessages([]);
    setSelectedImage(null);
    setImagePreviewUrl(null);
    setIsRecordingMode(false);
    setErrorMessage(null);
  };

  const handleSelectSession = async (sessionId) => {
    if (sessionId === currentSessionId) return;
    setCurrentSessionId(sessionId);
    localStorage.setItem('eva_active_session_id', sessionId);
    setErrorMessage(null);

    // Try loading local cache first
    try {
      const saved = localStorage.getItem(`eva_messages_${sessionId}`);
      if (saved) {
        setMessages(JSON.parse(saved));
        return;
      }
    } catch (e) {
      console.warn(e);
    }

    // Fallback: fetch from backend SQLite memory
    setIsLoading(true);
    const history = await getSessionHistory(sessionId);
    setIsLoading(false);

    if (history && history.length > 0) {
      const formatted = history.map((item, idx) => ({
        id: `hist_${idx}_${Date.now()}`,
        role: item.role,
        content: item.content,
        timestamp: 'Previous',
      }));
      setMessages(formatted);
    } else {
      setMessages([]);
    }
  };

  const handleDeleteSession = (sessionId) => {
    const updated = sessions.filter((s) => s.id !== sessionId);
    setSessions(updated);
    localStorage.setItem('eva_chat_sessions', JSON.stringify(updated));
    localStorage.removeItem(`eva_messages_${sessionId}`);

    if (sessionId === currentSessionId) {
      if (updated.length > 0) {
        handleSelectSession(updated[0].id);
      } else {
        handleNewSession();
      }
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    localStorage.removeItem(`eva_messages_${currentSessionId}`);
  };

  // ─── Image Attachment Handlers ───────────────────────────────────────────
  const handleImageFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      setErrorMessage('Please select a valid image file (JPG, PNG, WebP).');
      return;
    }

    setSelectedImage(file);
    const preview = URL.createObjectURL(file);
    setImagePreviewUrl(preview);
    setErrorMessage(null);
    e.target.value = '';
  };

  const handleRemoveAttachedImage = () => {
    setSelectedImage(null);
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl);
      setImagePreviewUrl(null);
    }
  };

  // ─── Audio File Upload Handler ───────────────────────────────────────────
  const handleAudioFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('audio/') && !file.name.match(/\.(mp3|wav|ogg|m4a|webm|flac)$/i)) {
      setErrorMessage('Please select a valid audio file (MP3, WAV, OGG, M4A).');
      return;
    }

    e.target.value = '';
    await handleSendAudio(file);
  };

  // ─── Sending Handlers ────────────────────────────────────────────────────
  const handleSend = async () => {
    if (isLoading) return;

    // Case 1: Image + Caption or Image only
    if (selectedImage) {
      const imgFile = selectedImage;
      const preview = imagePreviewUrl;
      const caption = inputText.trim();

      // Add user message to state immediately
      const userMsgId = `user_${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: userMsgId,
          role: 'user',
          content: caption || 'Sent an image for analysis',
          userImagePreview: preview,
          timestamp: getCurrentTime(),
        },
      ]);

      setInputText('');
      setSelectedImage(null);
      setImagePreviewUrl(null);
      setIsLoading(true);
      setErrorMessage(null);

      try {
        const data = await sendImageMessage(imgFile, caption, currentSessionId);
        
        setMessages((prev) => [
          ...prev,
          {
            id: `ava_${Date.now()}`,
            role: 'assistant',
            content: data.response,
            workflow: data.workflow,
            image_url: data.image_url,
            audio_base64: data.audio_base64,
            imageAnalysis: data.image_analysis,
            autoPlayAudio: !!data.audio_base64,
            timestamp: getCurrentTime(),
          },
        ]);
      } catch (err) {
        console.error('Image message error:', err);
        setErrorMessage(err.response?.data?.detail || 'Failed to analyze image. Please ensure backend is running.');
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // Case 2: Standard Text Message
    const textToSend = inputText.trim();
    if (!textToSend) return;

    const userMsgId = `user_${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content: textToSend,
        timestamp: getCurrentTime(),
      },
    ]);

    setInputText('');
    setIsLoading(true);
    setErrorMessage(null);

    // Auto-adjust textarea height back
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // ── Streaming text message ──────────────────────────────────────────
    const avaMsgId = `ava_${Date.now()}`;

    // Add a placeholder message immediately so the bubble appears
    setMessages((prev) => [
      ...prev,
      {
        id: avaMsgId,
        role: 'assistant',
        content: '',
        isStreaming: true,
        timestamp: getCurrentTime(),
      },
    ]);

    await sendChatMessageStream(
      textToSend,
      currentSessionId,

      // onChunk — append each arriving chunk
      (chunkData) => {
        if (!chunkData?.chunk) return;
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== avaMsgId) return m;
            const separator = m.content ? '\n\n' : '';
            return {
              ...m,
              content: m.content + separator + chunkData.chunk,
              workflow: chunkData.workflow || m.workflow,
              image_url: chunkData.image_url || m.image_url,
              audio_base64: chunkData.audio_base64 || m.audio_base64,
              autoPlayAudio:
                chunkData.workflow === 'audio' && !!chunkData.audio_base64,
            };
          })
        );
      },

      // onDone — mark streaming complete (or remove if EVA stayed silent)
      (doneData) => {
        setMessages((prev) => {
          const target = prev.find((m) => m.id === avaMsgId);
          if (!target || !target.content.trim()) {
            // EVA stayed silent
            return prev.filter((m) => m.id !== avaMsgId);
          }
          return prev.map((m) =>
            m.id === avaMsgId ? { ...m, isStreaming: false } : m
          );
        });
        setIsLoading(false);
      },

      // onError
      (err) => {
        console.error('Stream error:', err);
        setErrorMessage(
          err?.message || 'Failed to send message. Please ensure backend is running.'
        );
        // Remove the empty placeholder on error
        setMessages((prev) => prev.filter((m) => m.id !== avaMsgId));
        setIsLoading(false);
      },
    );
    // Note: setIsLoading(false) is called inside onDone / onError above
  };

  const handleSendAudio = async (audioBlobOrFile) => {
    setIsRecordingMode(false);
    setIsLoading(true);
    setErrorMessage(null);

    // Create a local preview for user's voice message
    const previewUrl = URL.createObjectURL(audioBlobOrFile);
    const userMsgId = `user_${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content: '',
        audioSrc: previewUrl,
        workflow: 'audio',
        timestamp: getCurrentTime(),
      },
    ]);

    try {
      const data = await sendAudioMessage(audioBlobOrFile, currentSessionId);

      // Update user message with transcription once received
      if (data.transcription) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMsgId ? { ...m, transcription: data.transcription, content: data.transcription } : m
          )
        );
      }

      // Add assistant response
      setMessages((prev) => [
        ...prev,
        {
          id: `ava_${Date.now()}`,
          role: 'assistant',
          content: data.response,
          workflow: data.workflow || 'audio',
          image_url: data.image_url,
          audio_base64: data.audio_base64,
          autoPlayAudio: true,
          timestamp: getCurrentTime(),
        },
      ]);
    } catch (err) {
      console.error('Audio message error:', err);
      setErrorMessage(err.response?.data?.detail || 'Failed to process voice note. Check Groq API key.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaInput = (e) => {
    setInputText(e.target.value);
    // Auto-expand textarea
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 150)}px`;
  };

  return (
    <div className="app-container">
      {/* Sessions Drawer */}
      <SessionSidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
      />

      {/* Main Chat Area */}
      <div className="main-chat-layout">
        {/* Navigation Header */}
        <Header
          sessionId={currentSessionId}
          onNewSession={handleNewSession}
          onClearChat={handleClearChat}
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
          isBackendConnected={isBackendConnected}
        />

        {/* Message Feed */}
        <main className="chat-feed-area">
          <div className="chat-feed-content">
            {messages.length === 0 ? (
              <QuickPrompts onSelectPrompt={(text) => setInputText(text)} />
            ) : (
              messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onOpenImage={(url) => setModalImageUrl(url)}
                />
              ))
            )}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="message-row ava-message-row loading-row">
                <div className="message-avatar ava-avatar">
                  <div className="ava-avatar-inner">
                    <Sparkles size={16} className="spin-slow" />
                  </div>
                </div>
                <div className="message-content-wrapper">
                  <div className="message-header-info">
                    <span className="message-sender-name">Ava</span>
                    <span className="thinking-tag">Thinking & Processing...</span>
                  </div>
                  <div className="message-bubble ava-bubble loading-bubble">
                    <div className="typing-dots">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Error Banner */}
            {errorMessage && (
              <div className="error-banner">
                <AlertCircle size={18} className="error-icon" />
                <span className="error-text">{errorMessage}</span>
                <button type="button" onClick={() => setErrorMessage(null)} className="error-dismiss">
                  <X size={15} />
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </main>

        {/* Floating Input Composer */}
        <footer className="chat-composer-section">
          <div className="composer-wrapper">
            {/* Attached Image Preview Pill */}
            {imagePreviewUrl && (
              <div className="attached-preview-pill">
                <div className="preview-img-wrap">
                  <img src={imagePreviewUrl} alt="Attached" />
                </div>
                <span className="attached-name">{selectedImage?.name || 'Attached Image'}</span>
                <button
                  type="button"
                  onClick={handleRemoveAttachedImage}
                  className="remove-attached-btn"
                  title="Remove Image"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            {/* Live Audio Recorder Bar vs Text Composer */}
            {isRecordingMode ? (
              <VoiceRecorder
                onSendAudio={handleSendAudio}
                onCancel={() => setIsRecordingMode(false)}
                isProcessing={isLoading}
              />
            ) : (
              <div className="composer-bar">
                {/* Hidden File Inputs */}
                <input
                  ref={imageFileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageFileChange}
                  style={{ display: 'none' }}
                />
                <input
                  ref={audioFileInputRef}
                  type="file"
                  accept="audio/*,.mp3,.wav,.ogg,.m4a,.webm"
                  onChange={handleAudioFileUpload}
                  style={{ display: 'none' }}
                />

                {/* Upload Image Button */}
                <button
                  type="button"
                  onClick={() => imageFileInputRef.current?.click()}
                  className={`composer-icon-btn ${selectedImage ? 'active-icon' : ''}`}
                  title="Upload Image for Vision Analysis"
                  disabled={isLoading}
                >
                  <ImageIcon size={20} />
                </button>

                {/* Upload Audio File Button */}
                <button
                  type="button"
                  onClick={() => audioFileInputRef.current?.click()}
                  className="composer-icon-btn"
                  title="Upload Audio File (.mp3, .wav, .m4a)"
                  disabled={isLoading}
                >
                  <FileAudio size={20} />
                </button>

                {/* Real-time Voice Record Trigger Button */}
                <button
                  type="button"
                  onClick={() => setIsRecordingMode(true)}
                  className="composer-icon-btn voice-trigger-btn"
                  title="Record Voice Note"
                  disabled={isLoading}
                >
                  <Mic size={20} />
                </button>

                {/* Main Text Input */}
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={inputText}
                  onChange={handleTextareaInput}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    selectedImage
                      ? 'Add an optional question or caption about this image...'
                      : 'Message Ava... (Ask for advice, pictures, or voice notes)'
                  }
                  className="composer-textarea"
                  disabled={isLoading}
                />

                {/* Send Button */}
                <button
                  type="button"
                  onClick={handleSend}
                  className={`composer-send-btn ${inputText.trim() || selectedImage ? 'ready' : ''}`}
                  disabled={isLoading || (!inputText.trim() && !selectedImage)}
                  title="Send (Enter)"
                >
                  {isLoading ? <Loader2 size={18} className="spinner" /> : <Send size={18} />}
                </button>
              </div>
            )}

            <div className="composer-footer-hint">
              <span>Ava can chat, generate images, transcribe audio, and synthesize voice.</span>
            </div>
          </div>
        </footer>
      </div>

      {/* Full Image Zoom Modal */}
      <ImageModal
        imageUrl={modalImageUrl}
        onClose={() => setModalImageUrl(null)}
      />
    </div>
  );
}
