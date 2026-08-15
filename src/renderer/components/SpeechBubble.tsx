import React from 'react';

interface SpeechBubbleProps {
  message: string | null;
  isThinking: boolean;
  isVisible: boolean;
  onDismiss: () => void;
}

export const SpeechBubble: React.FC<SpeechBubbleProps> = ({
  message,
  isThinking,
  isVisible,
  onDismiss
}) => {
  const visibilityClass = isVisible ? 'speech-bubble--visible' : 'speech-bubble--hidden';
  
  return (
    <div className={`speech-bubble ${visibilityClass}`} onClick={onDismiss}>
      <div className="speech-bubble__text">
        {isThinking ? (
          <div className="speech-bubble__thinking">
            <span>.</span><span>.</span><span>.</span>
          </div>
        ) : (
          message
        )}
      </div>
      <div className="speech-bubble__tail" />
    </div>
  );
};
