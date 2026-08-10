import React from 'react';
import { AppStatus } from '../types';

interface StatusIndicatorProps {
  status: AppStatus;
  isConnected: boolean;
}

const STATUS_LABELS: Record<AppStatus, string> = {
  connecting: 'Connecting...',
  connected: 'Online',
  disconnected: 'Offline',
  idle: 'Ready',
  thinking: 'Thinking...',
  speaking: 'Speaking...',
  listening: 'Listening...',
  error: 'Error',
};

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  isConnected,
}) => {
  const dotClass =
    status === 'thinking' || status === 'speaking'
      ? 'status-dot--speaking'
      : !isConnected
        ? 'status-dot--idle'
        : '';

  return (
    <div className="status-indicator">
      <div className={`status-dot ${dotClass}`} />
      <span>{STATUS_LABELS[status] || status}</span>
    </div>
  );
};