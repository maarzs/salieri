import React from 'react';

interface TitleBarProps {
  onOpenSettings?: () => void;
  onClearHistory?: () => void;
}

export const TitleBar: React.FC<TitleBarProps> = ({ onOpenSettings, onClearHistory }) => {
  const handleMinimize = () => window.salieriAPI?.minimizeWindow();
  const handleHide = () => window.salieriAPI?.hideWindow();

  const handleClearHistory = () => {
    if (onClearHistory && window.confirm('Clear all conversation history?')) {
      onClearHistory();
    }
  };

  return (
    <div className="title-bar">
      <span className="title-bar__label">SALIERI AI</span>
      <div className="title-bar__controls">
        <button
          className="title-bar__btn title-bar__btn--clear"
          onClick={handleClearHistory}
          title="Clear conversation history"
          aria-label="Clear conversation history"
        >
          🗑
        </button>
        <button
          className="title-bar__btn title-bar__btn--settings"
          onClick={onOpenSettings}
          title="Settings"
          aria-label="Open settings"
        >
          ⚙
        </button>
        <button
          className="title-bar__btn title-bar__btn--minimize"
          onClick={handleMinimize}
          title="Minimize"
          aria-label="Minimize window"
        />
        <button
          className="title-bar__btn title-bar__btn--hide"
          onClick={handleHide}
          title="Hide"
          aria-label="Hide window"
        >
          ✕
        </button>
      </div>
    </div>
  );
};
