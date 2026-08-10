import React, { useState, KeyboardEvent } from 'react';

interface InputAreaProps {
  onSend: (content: string) => void;
  onVoiceRecord: () => void;
  onVoiceCall: () => void;
  isRecording: boolean;
  disabled: boolean;
}

export const InputArea: React.FC<InputAreaProps> = ({
  onSend,
  onVoiceRecord,
  onVoiceCall,
  isRecording,
  disabled,
}) => {
  const [input, setInput] = useState('');

  const handleSend = () => {
    const trimmed = input.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="input-area">
      <button
        className={`input-area__btn input-area__btn--voice ${isRecording ? 'active' : ''}`}
        onClick={onVoiceRecord}
        title={isRecording ? 'Stop recording' : 'Voice input'}
        disabled={disabled}
      >
        🎤
      </button>
      <input
        className="input-area__field"
        type="text"
        placeholder="Type a message..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <button
        className="input-area__btn input-area__btn--voice"
        onClick={onVoiceCall}
        title="Voice call"
        disabled={disabled}
      >
        📞
      </button>
      <button
        className="input-area__btn input-area__btn--send"
        onClick={handleSend}
        disabled={disabled || !input.trim()}
      >
        ▶
      </button>
    </div>
  );
};