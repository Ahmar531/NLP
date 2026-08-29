import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX, RotateCcw } from 'lucide-react';

export default function AudioPlayer({ audioSrc, autoPlay = false, label = 'Voice Message' }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const audioRef = useRef(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleLoadedMetadata = () => {
      setDuration(audio.duration || 0);
    };

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setCurrentTime(0);
    };

    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('ended', handleEnded);

    if (autoPlay) {
      audio.play().then(() => setIsPlaying(true)).catch(() => {
        // Autoplay may be blocked by browser policy until interaction
        setIsPlaying(false);
      });
    }

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('ended', handleEnded);
    };
  }, [audioSrc, autoPlay]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleSeek = (e) => {
    const newTime = parseFloat(e.target.value);
    setCurrentTime(newTime);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const formatTime = (seconds) => {
    if (isNaN(seconds) || seconds === 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <div className="audio-player-card">
      <audio ref={audioRef} src={audioSrc} preload="metadata" />
      
      <button 
        type="button" 
        onClick={togglePlay} 
        className={`audio-play-btn ${isPlaying ? 'playing' : ''}`}
        title={isPlaying ? 'Pause' : 'Play Audio'}
      >
        {isPlaying ? <Pause size={18} /> : <Play size={18} className="play-icon-offset" />}
      </button>

      <div className="audio-body">
        <div className="audio-meta">
          <span className="audio-label">{label}</span>
          <span className="audio-timer">
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
        </div>

        <div className="audio-waveform-container">
          <input
            type="range"
            min="0"
            max={duration || 100}
            step="0.1"
            value={currentTime}
            onChange={handleSeek}
            className="audio-seek-slider"
          />
          {/* Animated sound bars when playing */}
          <div className="audio-wave-bars">
            {[40, 70, 90, 60, 100, 50, 80, 45, 95, 65, 85, 55, 75, 40, 90].map((h, i) => (
              <span
                key={i}
                className={`wave-bar ${isPlaying ? 'animated' : ''}`}
                style={{
                  height: `${isPlaying ? h : 30}%`,
                  animationDelay: `${(i % 5) * 0.15}s`,
                }}
              />
            ))}
          </div>
        </div>
      </div>

      <button type="button" onClick={toggleMute} className="audio-mute-btn" title={isMuted ? 'Unmute' : 'Mute'}>
        {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
      </button>
    </div>
  );
}
