import React, { useState, useEffect } from 'react';

interface AvatarProps {
  emotion: string;
  isSpeaking: boolean;
}

const EMOTION_LABELS: Record<string, string> = {
  neutral: 'Online',
  happy: 'Happy',
  thinking: 'Thinking...',
  sad: 'Pensive',
  surprised: '!',
  concerned: 'Concerned',
  sleepy: 'Idle',
};

export const Avatar: React.FC<AvatarProps> = ({ emotion, isSpeaking }) => {
  const [hasSprite, setHasSprite] = useState(false);

  useEffect(() => {
    // Check if custom sprite exists
    const img = new Image();
    img.src = './assets/sprites/neutral.png';
    img.onload = () => setHasSprite(true);
  }, []);

  return (
    <div className="avatar-area">
      <div className="avatar-container">
        {hasSprite ? (
          <img
            className="avatar-sprite"
            src={`./assets/sprites/${emotion}.png`}
            alt={emotion}
          />
        ) : (
          <div className="avatar-placeholder">
            {isSpeaking ? '🔊' : '💜'}
          </div>
        )}
      </div>
      <div className="avatar-emotion-label">
        {EMOTION_LABELS[emotion] || emotion}
      </div>
    </div>
  );
};