import React, { useState } from 'react';
import { Copy, Check, Sparkles, User, Image as ImageIcon, Volume2, Eye } from 'lucide-react';
import AudioPlayer from './AudioPlayer';
import { API_BASE_URL } from '../api';

export default function MessageBubble({ message, onOpenImage }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const copyToClipboard = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Resolve full image URL if it's a relative path from the backend
  const resolveImageUrl = (url) => {
    if (!url) return null;
    if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
      return url;
    }
    return `${API_BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`;
  };

  const fullImageUrl = resolveImageUrl(message.imageSrc || message.image_url);
  const audioDataSrc = (message.workflow === 'audio' || (isUser && message.audioSrc))
    ? (message.audioSrc || (message.audio_base64 ? `data:audio/mp3;base64,${message.audio_base64}` : null))
    : null;

  return (
    <div className={`message-row ${isUser ? 'user-message-row' : 'ava-message-row'}`}>
      {/* Avatar */}
      <div className={`message-avatar ${isUser ? 'user-avatar' : 'ava-avatar'}`}>
        {isUser ? (
          <User size={18} />
        ) : (
          <div className="ava-avatar-inner">
            <Sparkles size={16} />
          </div>
        )}
      </div>

      {/* Bubble Container */}
      <div className="message-content-wrapper">
        <div className="message-header-info">
          <span className="message-sender-name">{isUser ? 'You' : 'Ava'}</span>
          
          {/* Workflow badge */}
          {message.workflow && message.workflow !== 'conversation' && (
            <span className={`workflow-tag tag-${message.workflow}`}>
              {message.workflow === 'image' && <><ImageIcon size={12} /> Generated Art</>}
              {message.workflow === 'audio' && <><Volume2 size={12} /> Voice Note</>}
            </span>
          )}

          {message.timestamp && (
            <span className="message-timestamp">{message.timestamp}</span>
          )}
        </div>

        <div className={`message-bubble ${isUser ? 'user-bubble' : 'ava-bubble'}`}>
          {/* Attached / Uploaded User Image preview */}
          {message.userImagePreview && (
            <div className="message-image-container" onClick={() => onOpenImage(message.userImagePreview)}>
              <img src={message.userImagePreview} alt="User Upload" className="message-image" />
            </div>
          )}

          {/* Audio Input Transcription Pill */}
          {message.transcription && (
            <div className="transcription-pill">
              <Volume2 size={13} />
              <span>Transcribed: &ldquo;{message.transcription}&rdquo;</span>
            </div>
          )}

          {/* Vision Analysis Pill */}
          {message.imageAnalysis && (
            <div className="analysis-pill">
              <Eye size={13} />
              <span>Visual Context: {message.imageAnalysis}</span>
            </div>
          )}

          {/* Text Content */}
          {(message.content || message.isStreaming) && (
            <div className="message-text">
              {message.content ? (
                message.content.split('\n').map((line, idx) => (
                  <p key={idx}>{line || '\u00A0'}</p>
                ))
              ) : message.isStreaming ? (
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              ) : null}
              {message.isStreaming && message.content && (
                <span className="streaming-cursor" aria-hidden="true" />
              )}
            </div>
          )}

          {/* AI Generated Image */}
          {fullImageUrl && (
            <div 
              className="message-image-container generated-image-container"
              onClick={() => onOpenImage(fullImageUrl)}
            >
              <img src={fullImageUrl} alt="AI Generated Scene" className="message-image" />
              <div className="image-overlay-hint">
                <ImageIcon size={14} /> Click to zoom
              </div>
            </div>
          )}

          {/* Audio Playback Player */}
          {audioDataSrc && (
            <div className="message-audio-wrapper">
              <AudioPlayer 
                audioSrc={audioDataSrc} 
                autoPlay={!isUser && message.autoPlayAudio} 
                label={isUser ? 'Your Voice Note' : 'Ava’s Voice Note'} 
              />
            </div>
          )}
        </div>

        {/* Message Actions */}
        {!isUser && message.content && !message.isStreaming && (
          <div className="message-bubble-footer">
            <button 
              type="button" 
              onClick={copyToClipboard} 
              className="message-action-btn"
              title="Copy message"
            >
              {copied ? <Check size={13} className="text-emerald" /> : <Copy size={13} />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
