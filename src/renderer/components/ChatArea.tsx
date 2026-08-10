import React from 'react';
import { Message } from '../types';

interface ChatAreaProps {
  messages: Message[];
  messagesEndRef: React.RefObject<HTMLDivElement>;
  isThinking: boolean;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  messagesEndRef,
  isThinking,
}) => {
  return (
    <div className="chat-area">
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="message message--system">
            Salieri is online. Say hello!
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`message message--${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {isThinking && (
          <div className="message message--salieri">
            <div className="loading-dots">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};