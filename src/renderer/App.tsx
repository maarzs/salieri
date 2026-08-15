import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mascot } from './components/Mascot';
import { SpeechBubble } from './components/SpeechBubble';
import { CompactInput } from './components/CompactInput';
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

const COMPACT_SIZE = { width: 380, height: 520 };
const EXPANDED_SIZE = { width: 380, height: 600 };
const BUBBLE_AUTO_HIDE_MS = 8000;

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

  // Clippy-style state
  const [isExpanded, setIsExpanded] = useState(false);
  const [bubbleMessage, setBubbleMessage] = useState<string | null>(null);
  const [bubbleVisible, setBubbleVisible] = useState(false);
  const [selectedCharacter, setSelectedCharacter] = useState<'male' | 'female'>('female');
  const bubbleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { sendMessage, isConnected } = useWebSocket(WS_URL, {
    onMessage: (data) => {
      switch (data.type) {
        case 'chat_response':
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            const full = data.content ?? '';
            if (last && last.role === 'salieri' && full) {
              return [...prev.slice(0, -1), { ...last, content: full }];
            }
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
          // Show speech bubble with latest response (compact mode)
          if (data.content) {
            showBubble(data.content);
          }
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
          // Update speech bubble with streaming content
          setBubbleMessage((prev) => (prev ?? '') + (data.content ?? ''));
          if (!bubbleVisible) setBubbleVisible(true);
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
          if (data.settings) {
            const s = data.settings as Settings;
            setSettings(s);
            if (s.mascot_character) {
              setSelectedCharacter(s.mascot_character);
            }
          }
          setIsSaving(false);
          break;

        case 'history':
          setMessages((prev) => {
            if (prev.length > 0 || !data.history?.length) return prev;
            const restored: Message[] = [];
            for (const entry of data.history) {
              restored.push({
                id: `hist-${entry.timestamp}-u`,
                role: 'user',
                content: entry.user_message,
                timestamp: entry.timestamp,
              });
              restored.push({
                id: `hist-${entry.timestamp}-s`,
                role: 'salieri',
                content: entry.response,
                timestamp: entry.timestamp,
              });
            }
            return restored;
          });
          if (data.history?.length) {
            const last = data.history[data.history.length - 1];
            if (last?.emotion) setEmotion(last.emotion);
          }
          break;

        case 'history_cleared':
          setMessages([]);
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

  // Speech bubble management
  const showBubble = useCallback((message: string) => {
    setBubbleMessage(message);
    setBubbleVisible(true);
    // Clear any existing timer
    if (bubbleTimerRef.current) clearTimeout(bubbleTimerRef.current);
    // Auto-hide after 8s
    bubbleTimerRef.current = setTimeout(() => {
      setBubbleVisible(false);
    }, BUBBLE_AUTO_HIDE_MS);
  }, []);

  const dismissBubble = useCallback(() => {
    setBubbleVisible(false);
    if (bubbleTimerRef.current) clearTimeout(bubbleTimerRef.current);
  }, []);

  // Toggle between compact and expanded
  const toggleExpand = useCallback(() => {
    setIsExpanded((prev) => {
      const next = !prev;
      const size = next ? EXPANDED_SIZE : COMPACT_SIZE;
      window.salieriAPI?.resizeWindow(size.width, size.height);
      if (next) {
        // Dismiss bubble when expanding
        dismissBubble();
      }
      return next;
    });
  }, [dismissBubble]);

  // Pull config on connect
  useEffect(() => {
    if (isConnected) {
      sendMessage({ type: 'get_settings' });
      sendMessage({ type: 'load_history', limit: 100 });
    }
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

  // Cleanup bubble timer
  useEffect(() => {
    return () => {
      if (bubbleTimerRef.current) clearTimeout(bubbleTimerRef.current);
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
      // Reset bubble for streaming
      setBubbleMessage(null);
      setBubbleVisible(true);
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

  const handleMicToggle = useCallback(
    (active: boolean) => {
      setIsRecording(active);
      sendMessage({ type: active ? 'stt_start' : 'stt_stop' });
    },
    [sendMessage]
  );

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
      // Update local character immediately for responsive feel
      if (patch.mascot_character) {
        setSelectedCharacter(patch.mascot_character);
      }
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
    sendMessage({ type: 'list_models' });
  }, [sendMessage]);

  const handleClearHistory = useCallback(() => {
    sendMessage({ type: 'clear_history' });
  }, [sendMessage]);

  const playAudio = (base64Audio: string) => {
    const audio = new Audio(`data:audio/wav;base64,${base64Audio}`);
    audio.onended = () => setIsSpeaking(false);
    audio.play().catch(console.error);
  };

  // ── Settings / Voice Call overlays ──
  if (showSettings) {
    return (
      <div className="app-container app-container--expanded">
        <TitleBar onOpenSettings={handleOpenSettings} onClearHistory={handleClearHistory} />
        <SettingsPanel
          settings={settings}
          models={models}
          testResult={testResult}
          isSaving={isSaving}
          selectedCharacter={selectedCharacter}
          onSave={handleSaveSettings}
          onRefreshModels={handleRefreshModels}
          onTest={handleTestConnection}
          onClose={() => setShowSettings(false)}
        />
      </div>
    );
  }

  if (isVoiceCall) {
    return (
      <div className="app-container app-container--expanded">
        <VoiceCall
          emotion={emotion}
          isSpeaking={isSpeaking}
          onEnd={handleEndVoiceCall}
        />
      </div>
    );
  }

  // ── Expanded mode: full chat panel ──
  if (isExpanded) {
    return (
      <div className="app-container app-container--expanded">
        <TitleBar onOpenSettings={handleOpenSettings} onClearHistory={handleClearHistory} />
        <ChatArea
          messages={messages}
          messagesEndRef={messagesEndRef}
          isThinking={status === 'thinking'}
        />
        <Mascot
          character={selectedCharacter}
          emotion={emotion}
          isSpeaking={isSpeaking}
          onClick={toggleExpand}
          size="small"
        />
        <InputArea
          onSend={handleSendMessage}
          onVoiceRecord={handleVoiceRecord}
          onVoiceCall={handleStartVoiceCall}
          isRecording={isRecording}
          disabled={status === 'thinking' || !isConnected}
        />
      </div>
    );
  }

  // ── Compact mode: Clippy-style mascot ──
  return (
    <div className="app-container app-container--compact">
      <SpeechBubble
        message={bubbleMessage}
        isThinking={status === 'thinking'}
        isVisible={bubbleVisible || status === 'thinking'}
        onDismiss={dismissBubble}
      />
      <Mascot
        character={selectedCharacter}
        emotion={emotion}
        isSpeaking={isSpeaking}
        onClick={toggleExpand}
      />
      <CompactInput
        onSend={handleSendMessage}
        onMicToggle={handleMicToggle}
        disabled={status === 'thinking' || !isConnected}
        isListening={isRecording}
      />
    </div>
  );
}