import React from 'react';
import { X, Download, ExternalLink } from 'lucide-react';

export default function ImageModal({ imageUrl, onClose }) {
  if (!imageUrl) return null;

  return (
    <div className="image-modal-backdrop" onClick={onClose}>
      <div className="image-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="image-modal-header">
          <span className="image-modal-title">Image Preview</span>
          <div className="image-modal-actions">
            <a
              href={imageUrl}
              target="_blank"
              rel="noreferrer"
              className="modal-action-btn"
              title="Open full size"
            >
              <ExternalLink size={18} />
            </a>
            <a
              href={imageUrl}
              download="ai_generated_image.png"
              className="modal-action-btn"
              title="Download image"
            >
              <Download size={18} />
            </a>
            <button onClick={onClose} className="modal-action-btn close-btn" title="Close">
              <X size={20} />
            </button>
          </div>
        </div>
        <div className="image-modal-body">
          <img src={imageUrl} alt="AI Visual" className="modal-full-image" />
        </div>
      </div>
    </div>
  );
}
