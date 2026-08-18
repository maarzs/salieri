import React, { useState, KeyboardEvent } from 'react';

interface CompactInputProps {
  onSend: (text: string) => void;
  onMicToggle: (active: boolean) => void;
  onOpenSettings: () => void;
  disabled: boolean;
  isListening: boolean;
}

export const CompactInput: React.FC<CompactInputProps> = ({
  onSend,
  onMicToggle,
  onOpenSettings,
  disabled,
  isListening
}) => {
  const [input, setInput] = useState('');

  const handleSend = () => {
    const trimmed = input.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="compact-input-wrapper">
      <div className="compact-input">
        <input
          type="text"
          className="compact-input__field"
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />
        <button
          className={`compact-input__btn compact-input__btn--mic ${isListening ? 'compact-input__btn--mic--active' : ''}`}
          onClick={() => onMicToggle(!isListening)}
          disabled={disabled}
          title={isListening ? 'Stop listening' : 'Start listening'}
        >
          🎤
        </button>
        <button
          className="compact-input__btn compact-input__btn--send"
          onClick={handleSend}
          disabled={disabled || !input.trim()}
        >
          ▶
        </button>
        <button
          className="compact-input__btn compact-input__btn--settings"
          onClick={onOpenSettings}
          title="Settings"
          aria-label="Open settings"
        >
          ⚙
        </button>
      </div>
    </div>
  );
};
