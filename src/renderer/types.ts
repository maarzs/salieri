export interface Message {
  id: string;
  role: 'user' | 'salieri' | 'system';
  content: string;
  timestamp: number;
}

export type AppStatus =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'idle'
  | 'thinking'
  | 'speaking'
  | 'listening'
  | 'error';

export interface WSMessage {
  type: string;
  content?: string;
  emotion?: string;
  streamId?: string;
  audio?: string;
  message?: string;
  status?: string;
  // Inbound `settings` frames carry the full resolved config; outbound
  // `update_settings` frames carry only the fields being changed.
  settings?: Settings | SettingsPatch;
  models?: string[];
  saved?: boolean;
  ok?: boolean;
  history?: HistoryEntry[];
  removed?: number;
  limit?: number;
}

/** One persisted exchange, as returned by the `load_history` endpoint. */
export interface HistoryEntry {
  user_message: string;
  response: string;
  emotion: string;
  timestamp: number;
}

/** LLM configuration as returned by the backend. The API key is never sent
 *  back to the renderer — only whether one is set, plus a last-4 hint. */
export interface Settings {
  provider: 'ollama' | 'openai';
  model: string;
  base_url: string;
  ollama_host: string;
  tts_enabled: boolean;
  tts_voice: string;
  tts_rate: string;
  personality_name: string;
  personality_style: string;
  response_length: 'concise' | 'normal' | 'detailed' | string;
  api_key_set: boolean;
  api_key_hint: string;
  model_defaults: Record<string, string>;
  settings_path: string;
}

/** Partial update sent to the backend. Omit api_key to keep the stored one. */
export type SettingsPatch = Partial<{
  provider: string;
  model: string;
  base_url: string;
  ollama_host: string;
  tts_enabled: boolean;
  tts_voice: string;
  tts_rate: string;
  personality_name: string;
  personality_style: string;
  response_length: string;
  api_key: string;
}>;