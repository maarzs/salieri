import React, { useEffect, useState } from 'react';
import { Settings, SettingsPatch } from '../types';

interface SettingsPanelProps {
  settings: Settings | null;
  models: string[];
  testResult: { ok: boolean; message: string } | null;
  isSaving: boolean;
  onSave: (patch: SettingsPatch) => void;
  onRefreshModels: () => void;
  onTest: () => void;
  onClose: () => void;
}

/**
 * LLM configuration panel: provider, base URL, model, and API key.
 *
 * The API key input starts empty and is only submitted when the user types a
 * new one — the backend treats an empty value as "keep the existing key", so
 * the secret never has to round-trip to the renderer.
 */
export const SettingsPanel: React.FC<SettingsPanelProps> = ({
  settings,
  models,
  testResult,
  isSaving,
  onSave,
  onRefreshModels,
  onTest,
  onClose,
}) => {
  const [provider, setProvider] = useState('ollama');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [ollamaHost, setOllamaHost] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [ttsEnabled, setTtsEnabled] = useState(true);

  // Hydrate the form whenever fresh settings arrive from the backend.
  useEffect(() => {
    if (!settings) return;
    setProvider(settings.provider);
    setModel(settings.model);
    setBaseUrl(settings.base_url ?? '');
    setOllamaHost(settings.ollama_host ?? '');
    setTtsEnabled(settings.tts_enabled);
    setApiKey('');
  }, [settings]);

  const isOpenAI = provider === 'openai';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const patch: SettingsPatch = {
      provider,
      model: model.trim(),
      base_url: baseUrl.trim(),
      ollama_host: ollamaHost.trim(),
      tts_enabled: ttsEnabled,
    };
    // Only send the key when the user actually entered one.
    if (apiKey.trim()) patch.api_key = apiKey.trim();
    onSave(patch);
  };

  if (!settings) {
    return (
      <div className="settings-panel">
        <div className="settings-panel__header">
          <span>SETTINGS</span>
          <button className="settings-panel__close" onClick={onClose} aria-label="Close settings">
            ✕
          </button>
        </div>
        <p className="settings-panel__loading">Loading settings...</p>
      </div>
    );
  }

  return (
    <div className="settings-panel">
      <div className="settings-panel__header">
        <span>SETTINGS</span>
        <button className="settings-panel__close" onClick={onClose} aria-label="Close settings">
          ✕
        </button>
      </div>

      <form className="settings-form" onSubmit={handleSubmit}>
        <label className="settings-field">
          <span className="settings-field__label">Provider</span>
          <select
            className="settings-field__input"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="ollama">Ollama (local)</option>
            <option value="openai">OpenAI-compatible API</option>
          </select>
        </label>

        {isOpenAI ? (
          <>
            <label className="settings-field">
              <span className="settings-field__label">Base URL</span>
              <input
                className="settings-field__input"
                type="text"
                value={baseUrl}
                placeholder="https://api.openai.com/v1"
                onChange={(e) => setBaseUrl(e.target.value)}
                spellCheck={false}
              />
            </label>

            <label className="settings-field">
              <span className="settings-field__label">
                API Key
                {settings.api_key_set && (
                  <span className="settings-field__hint">
                    {' '}saved {settings.api_key_hint}
                  </span>
                )}
              </span>
              <input
                className="settings-field__input"
                type="password"
                value={apiKey}
                placeholder={
                  settings.api_key_set ? 'Leave blank to keep current key' : 'sk-...'
                }
                onChange={(e) => setApiKey(e.target.value)}
                spellCheck={false}
                autoComplete="off"
              />
            </label>
          </>
        ) : (
          <label className="settings-field">
            <span className="settings-field__label">Ollama Host</span>
            <input
              className="settings-field__input"
              type="text"
              value={ollamaHost}
              placeholder="http://localhost:11434"
              onChange={(e) => setOllamaHost(e.target.value)}
              spellCheck={false}
            />
          </label>
        )}

        <label className="settings-field">
          <span className="settings-field__label">
            Model
            <button
              type="button"
              className="settings-field__refresh"
              onClick={onRefreshModels}
              title="Fetch available models from this endpoint"
            >
              refresh
            </button>
          </span>
          <input
            className="settings-field__input"
            type="text"
            value={model}
            list="salieri-model-list"
            placeholder={settings.model_defaults?.[provider] ?? 'model name'}
            onChange={(e) => setModel(e.target.value)}
            spellCheck={false}
          />
          <datalist id="salieri-model-list">
            {models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          {models.length > 0 && (
            <span className="settings-field__hint">{models.length} models available</span>
          )}
        </label>

        <label className="settings-field settings-field--row">
          <input
            type="checkbox"
            checked={ttsEnabled}
            onChange={(e) => setTtsEnabled(e.target.checked)}
          />
          <span className="settings-field__label">Enable voice (TTS)</span>
        </label>

        {testResult && (
          <p
            className={`settings-result ${
              testResult.ok ? 'settings-result--ok' : 'settings-result--fail'
            }`}
          >
            {testResult.message}
          </p>
        )}

        <div className="settings-actions">
          <button type="button" className="settings-btn" onClick={onTest}>
            Test
          </button>
          <button type="submit" className="settings-btn settings-btn--primary" disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  );
};
