import React, { useState, useEffect } from 'react';

interface VoiceCallProps {
  emotion: string;
  isSpeaking: boolean;
  onEnd: () => void;
}

export const VoiceCall: React.FC<VoiceCallProps> = ({
  emotion,
  isSpeaking,
  onEnd,
}) => {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (totalSeconds: number): string => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="voice-call-overlay">
      <div className="voice-call-avatar">
        <div
          className="avatar-placeholder"
          style={isSpeaking ? { animation: 'speakGlow 0.5s ease-in-out infinite' } : {}}
        >
          {isSpeaking ? '🔊' : '💜'}
        </div>
      </div>
      <div className="voice-call-status">
        {isSpeaking ? 'Speaking...' : 'Connected'}
      </div>
      <div className="voice-call-timer">{formatTime(seconds)}</div>
      <button className="voice-call-end-btn" onClick={onEnd}>
        📞
      </button>
    </div>
  );
};