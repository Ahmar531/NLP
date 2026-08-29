import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Trash2, Send, Radio } from 'lucide-react';

export default function VoiceRecorder({ onSendAudio, onCancel, isProcessing }) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordDuration, setRecordDuration] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);

  // Start recording on mount
  useEffect(() => {
    startRecording();
    return () => {
      stopRecordingCleanup();
    };
  }, []);

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') 
        ? 'audio/webm' 
        : MediaRecorder.isTypeSupported('audio/ogg') 
        ? 'audio/ogg' 
        : 'audio/mp4';

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: mimeType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        // Stop audio tracks to release microphone
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(200);
      setIsRecording(true);
      setRecordDuration(0);

      timerRef.current = setInterval(() => {
        setRecordDuration((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Error accessing microphone:', err);
      alert('Could not access microphone. Please check browser permissions.');
      if (onCancel) onCancel();
    }
  };

  const stopRecordingCleanup = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  };

  const handleStop = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleSend = () => {
    if (audioBlob && onSendAudio) {
      onSendAudio(audioBlob);
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <div className="voice-recorder-bar">
      <div className="recorder-status">
        <span className={`recording-dot ${isRecording ? 'pulse' : ''}`} />
        <span className="recorder-time">
          {isRecording ? `Recording... ${formatDuration(recordDuration)}` : `Recorded (${formatDuration(recordDuration)})`}
        </span>
      </div>

      <div className="recorder-waveform">
        {[40, 80, 60, 100, 70, 90, 50, 85, 65, 95, 45, 75, 55, 90, 60].map((h, i) => (
          <span
            key={i}
            className={`record-bar ${isRecording ? 'active' : ''}`}
            style={{
              height: isRecording ? `${h}%` : '25%',
              animationDelay: `${(i % 5) * 0.12}s`,
            }}
          />
        ))}
      </div>

      <div className="recorder-actions">
        {isRecording ? (
          <button
            type="button"
            onClick={handleStop}
            className="recorder-btn stop-btn"
            title="Stop Recording"
          >
            <Square size={16} />
          </button>
        ) : (
          audioUrl && (
            <audio src={audioUrl} controls className="mini-audio-preview" />
          )
        )}

        <button
          type="button"
          onClick={onCancel}
          className="recorder-btn cancel-btn"
          title="Discard Recording"
          disabled={isProcessing}
        >
          <Trash2 size={16} />
        </button>

        <button
          type="button"
          onClick={isRecording ? () => { handleStop(); setTimeout(handleSend, 300); } : handleSend}
          className="recorder-btn send-record-btn"
          title="Send Voice Note"
          disabled={isProcessing}
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
