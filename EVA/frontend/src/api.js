import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Headers needed to bypass the ngrok browser warning interstitial
// (free ngrok shows a warning page unless this header is present)
const NGROK_HEADERS = {
  'ngrok-skip-browser-warning': 'true',
};

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2 minutes for LLM/Image/TTS generation
  headers: NGROK_HEADERS,
});

/**
 * Send a text message to the AI Companion and receive chunked SSE response.
 *
 * Can be used in two ways:
 * 1. Streaming with callbacks:
 *    sendChatMessage(msg, sid, onChunk, onDone, onError)
 * 2. Promise mode (accumulates all chunks and resolves):
 *    const data = await sendChatMessage(msg, sid)
 *
 * @param {string}   message    - Text message content
 * @param {string}   sessionId  - Unique session ID
 * @param {Function} [onChunk]  - Callback for each chunk: (chunkData) => void
 * @param {Function} [onDone]   - Callback when streaming completes: (doneData) => void
 * @param {Function} [onError]  - Callback for errors: (err) => void
 */
export async function sendChatMessage(
  message,
  sessionId = 'default',
  onChunk = null,
  onDone = null,
  onError = null,
) {
  const url = `${API_BASE_URL}/chat`;

  // If used in streaming callback mode:
  if (typeof onChunk === 'function') {
    let response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...NGROK_HEADERS },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
    } catch (err) {
      if (onError) onError(err);
      return;
    }

    if (!response.ok) {
      const detail = await response.text().catch(() => response.statusText);
      const err = new Error(`/chat error ${response.status}: ${detail}`);
      if (onError) onError(err);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop();

      for (const event of events) {
        const dataLine = event
          .split('\n')
          .find((l) => l.startsWith('data:'));
        if (!dataLine) continue;

        let parsed;
        try {
          parsed = JSON.parse(dataLine.slice(5).trim());
        } catch {
          continue;
        }

        if (parsed.done) {
          if (onDone) onDone(parsed);
          return;
        }

        onChunk(parsed);
      }
    }

    if (onDone) onDone({});
    return;
  }

  // Promise mode (no onChunk passed): read all chunks and return aggregated result
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...NGROK_HEADERS },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`/chat error ${response.status}: ${detail}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let fullText = '';
  let lastData = {};

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop();

    for (const event of events) {
      const dataLine = event.split('\n').find((l) => l.startsWith('data:'));
      if (!dataLine) continue;
      try {
        const parsed = JSON.parse(dataLine.slice(5).trim());
        if (parsed.chunk) {
          fullText += (fullText ? '\n\n' : '') + parsed.chunk;
          lastData = parsed;
        }
      } catch {
        // ignore malformed JSON
      }
    }
  }

  return {
    response: fullText,
    session_id: sessionId,
    workflow: lastData.workflow || 'conversation',
    image_url: lastData.image_url || null,
    audio_base64: lastData.audio_base64 || null,
  };
}

/**
 * Explicit streaming alias for sendChatMessage.
 */
export const sendChatMessageStream = sendChatMessage;

/**
 * Send an audio file or voice recording to the AI Companion.
 * @param {File|Blob} audioFileOrBlob - Audio file or recorded blob
 * @param {string} sessionId - Unique session ID
 */
export async function sendAudioMessage(audioFileOrBlob, sessionId = 'default') {
  const formData = new FormData();
  
  // Format filename with extension if it's a blob
  let fileToSend = audioFileOrBlob;
  if (!(audioFileOrBlob instanceof File)) {
    const ext = audioFileOrBlob.type?.includes('webm') ? 'webm' : 
                audioFileOrBlob.type?.includes('ogg') ? 'ogg' : 
                audioFileOrBlob.type?.includes('wav') ? 'wav' : 'mp3';
    fileToSend = new File([audioFileOrBlob], `recording_${Date.now()}.${ext}`, {
      type: audioFileOrBlob.type || 'audio/webm',
    });
  }

  formData.append('file', fileToSend);
  formData.append('session_id', sessionId);

  const response = await apiClient.post('/audio', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

/**
 * Send an image file with an optional prompt/caption.
 * @param {File} imageFile - Image file
 * @param {string} caption - Optional user caption/question
 * @param {string} sessionId - Unique session ID
 */
export async function sendImageMessage(imageFile, caption = '', sessionId = 'default') {
  const formData = new FormData();
  formData.append('file', imageFile);
  if (caption && caption.trim()) {
    formData.append('caption', caption.trim());
  }
  formData.append('session_id', sessionId);

  const response = await apiClient.post('/image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

/**
 * Fetch conversation history for a given session ID.
 * @param {string} sessionId
 */
export async function getSessionHistory(sessionId) {
  try {
    const response = await apiClient.get(`/history/${sessionId}`);
    return response.data?.messages || [];
  } catch (error) {
    console.warn(`Could not load history for session ${sessionId}:`, error);
    return [];
  }
}

/**
 * Check backend connection status.
 */
export async function checkBackendHealth() {
  try {
    const response = await apiClient.get('/health');
    return response.status === 200;
  } catch {
    return false;
  }
}

export { API_BASE_URL };
