import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Avatar } from './components/Avatar';
import { ChatArea } from './components/ChatArea';
import { InputArea } from './components/InputArea';
import { VoiceCall } from './components/VoiceCall';
import { TitleBar } from './components/TitleBar';
import { StatusIndicator } from './components/StatusIndicator';
import { SettingsPanel } from './components/SettingsPanel';
import { useWebSocket } from './hooks/useWebSocket';
import { Message, AppStatus, Settings, SettingsPatch } from './types';

const WS_URL = 'ws://localhost:9876';

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<AppStatus>('connecting');
  const [emotion, setEmotion] = useState<string>('neutral');
  const [isVoiceCall, setIsVoiceCall] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(
    null
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { sendMessage, isConnected } = useWebSocket(WS_URL, {
    onMessage: (data) => {
      switch (data.type) {
        // The backend streams the reply as `chat_stream` chunks and THEN sends
        // `chat_response` carrying the same full text plus the detected emotion.
        // Appending it here would render the reply twice, so treat it as
        // metadata only: apply the emotion, and reconcile the streamed bubble
        // with the authoritative full text instead of adding a new one.
        case 'chat_response':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            const full = data.content ?? '';
            if (last && last.role === 'salieri' && full) {
              return [...prev.slice(0, -1), { ...last, content: full }];
            }
            // No streamed bubble to reconcile (e.g. streaming was skipped) —
            // this is the only copy of the reply, so render it.
            if (!full) return prev;
            return [
              ...prev,
              {
                id: Date.now().toString(),
                role: 'salieri',
                content: full,
                timestamp: Date.now(),
              },
            ];
          });
          setEmotion(data.emotion || 'neutral');
          setStatus('idle');
          break;

        case 'chat_stream':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'salieri' && last.id === data.streamId) {
              return [
                ...prev.slice(0, -1),
                { ...last, content: last.content + data.content },
              ];
            }
            return [
              ...prev,
              {
                id: data.streamId ?? Date.now().toString(),
                role: 'salieri',
                content: data.content ?? '',
                timestamp: Date.now(),
              },
            ];
          });
          break;

        case 'stream_end':
          setStatus('idle');
          break;

        case 'tts_audio':
          if (data.audio) playAudio(data.audio);
          setIsSpeaking(true);
          setStatus('speaking');
          break;

        case 'tts_done':
          setIsSpeaking(false);
          setStatus('idle');
          break;

        case 'stt_result':
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              role: 'user',
              content: data.content ?? '',
              timestamp: Date.now(),
            },
          ]);
          break;

        case 'error':
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              role: 'system',
              content: `Error: ${data.message}`,
              timestamp: Date.now(),
            },
          ]);
          setStatus('idle');
          break;

        case 'status':
          if (data.status) setStatus(data.status as AppStatus);
          break;

        case 'settings':
          // Inbound frames always carry the full resolved config.
          if (data.settings) setSettings(data.settings as Settings);
          setIsSaving(false);
          break;

        case 'models':
          setModels(data.models ?? []);
          break;

        case 'test_result':
          setTestResult({ ok: !!data.ok, message: data.message ?? '' });
          break;
      }
    },
    onConnect: () => setStatus('idle'),
    onDisconnect: () => setStatus('disconnected'),
  });

  // Pull current config once the backend is reachable (and again after any
  // reconnect, so the panel never shows stale values).
  useEffect(() => {
    if (isConnected) sendMessage({ type: 'get_settings' });
  }, [isConnected, sendMessage]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (window.salieriAPI) {
      window.salieriAPI.onStartVoiceCall(() => {
        setIsVoiceCall(true);
      });
    }
    return () => {
      window.salieriAPI?.removeAllListeners('start-voice-call');
    };
  }, []);

  const handleSendMessage = useCallback(
    (content: string) => {
      const userMsg: Message = {
        id: Date.now().toString(),
        role: 'user',
        content,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStatus('thinking');
      sendMessage({ type: 'chat', content });
    },
    [sendMessage]
  );

  const handleVoiceRecord = useCallback(() => {
    if (isRecording) {
      setIsRecording(false);
      sendMessage({ type: 'stt_stop' });
    } else {
      setIsRecording(true);
      sendMessage({ type: 'stt_start' });
    }
  }, [isRecording, sendMessage]);

  const handleStartVoiceCall = useCallback(() => {
    setIsVoiceCall(true);
    sendMessage({ type: 'voice_call_start' });
  }, [sendMessage]);

  const handleEndVoiceCall = useCallback(() => {
    setIsVoiceCall(false);
    sendMessage({ type: 'voice_call_end' });
  }, [sendMessage]);

  const handleSaveSettings = useCallback(
    (patch: SettingsPatch) => {
      setIsSaving(true);
      setTestResult(null);
      sendMessage({ type: 'update_settings', settings: patch });
    },
    [sendMessage]
  );

  const handleRefreshModels = useCallback(() => {
    sendMessage({ type: 'list_models' });
  }, [sendMessage]);

  const handleTestConnection = useCallback(() => {
    setTestResult({ ok: true, message: 'Testing...' });
    sendMessage({ type: 'test_connection' });
  }, [sendMessage]);

  const handleOpenSettings = useCallback(() => {
    setShowSettings(true);
    setTestResult(null);
    // Populate the model dropdown from the currently configured endpoint.
    sendMessage({ type: 'list_models' });
  }, [sendMessage]);

  const playAudio = (base64Audio: string) => {
    const audio = new Audio(`data:audio/wav;base64,${base64Audio}`);
    audio.onended = () => setIsSpeaking(false);
    audio.play().catch(console.error);
  };

  return (
    <div className="app-container">
      <TitleBar onOpenSettings={handleOpenSettings} />

      {showSettings ? (
        <SettingsPanel
          settings={settings}
          models={models}
          testResult={testResult}
          isSaving={isSaving}
          onSave={handleSaveSettings}
          onRefreshModels={handleRefreshModels}
          onTest={handleTestConnection}
          onClose={() => setShowSettings(false)}
        />
      ) : isVoiceCall ? (
        <VoiceCall
          emotion={emotion}
          isSpeaking={isSpeaking}
          onEnd={handleEndVoiceCall}
        />
      ) : (
        <>
          <Avatar emotion={emotion} isSpeaking={isSpeaking} />
          <StatusIndicator status={status} isConnected={isConnected} />
          <ChatArea
            messages={messages}
            messagesEndRef={messagesEndRef}
            isThinking={status === 'thinking'}
          />
          <InputArea
            onSend={handleSendMessage}
            onVoiceRecord={handleVoiceRecord}
            onVoiceCall={handleStartVoiceCall}
            isRecording={isRecording}
            disabled={status === 'thinking' || !isConnected}
          />
        </>
      )}
    </div>
  );
}