import React, { useEffect, useState } from 'react';
import { Settings, SettingsPatch, FeatureModule } from '../types';

import maleNeutral from '../assets/mascots/male/neutral.png';
import femaleNeutral from '../assets/mascots/female/neutral.png';

/** Popular Edge TTS voices offered as quick picks; the input accepts any
 *  valid Edge TTS voice name, so this list is a convenience, not a limit. */
const VOICE_OPTIONS: { id: string; label: string }[] = [
  { id: 'en-US-AriaNeural', label: 'Aria — US female (default)' },
  { id: 'en-US-AvaNeural', label: 'Ava — US female' },
  { id: 'en-US-JennyNeural', label: 'Jenny — US female' },
  { id: 'en-US-MichelleNeural', label: 'Michelle — US female' },
  { id: 'en-US-GuyNeural', label: 'Guy — US male' },
  { id: 'en-US-ChristopherNeural', label: 'Christopher — US male' },
  { id: 'en-US-EricNeural', label: 'Eric — US male' },
  { id: 'en-GB-SoniaNeural', label: 'Sonia — British female' },
  { id: 'en-GB-RyanNeural', label: 'Ryan — British male' },
  { id: 'en-AU-NatashaNeural', label: 'Natasha — Australian female' },
  { id: 'en-AU-WilliamNeural', label: 'William — Australian male' },
  { id: 'en-CA-ClaraNeural', label: 'Clara — Canadian female' },
  { id: 'en-IN-NeerjaNeural', label: 'Neerja — Indian female' },
];

interface SettingsPanelProps {
  settings: Settings | null;
  models: string[];
  testResult: { ok: boolean; message: string } | null;
  isSaving: boolean;
  onSave: (patch: SettingsPatch) => void;
  onRefreshModels: () => void;
  onTest: () => void;
  onClose: () => void;
  selectedCharacter: 'male' | 'female';
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
  selectedCharacter,
}) => {
  const [provider, setProvider] = useState('ollama');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [ollamaHost, setOllamaHost] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [ttsVoice, setTtsVoice] = useState('');
  const [ttsRate, setTtsRate] = useState('');
  const [personalityName, setPersonalityName] = useState('');
  const [personalityStyle, setPersonalityStyle] = useState('');
  const [responseLength, setResponseLength] = useState('normal');
  const [character, setCharacter] = useState<'male' | 'female'>(selectedCharacter);

  // Feature modules (dynamic backend capabilities)
  const [features, setFeatures] = useState<FeatureModule[]>([]);
  const [installing, setInstalling] = useState<string | null>(null);
  const [installLog, setInstallLog] = useState<string>('');

  const refreshFeatures = () => {
    window.salieriAPI?.listFeatures().then(setFeatures).catch(() => {});
  };

  useEffect(() => {
    refreshFeatures();
    window.salieriAPI?.onInstallProgress((_id, message) => {
      setInstallLog(message);
    });
    return () => {
      window.salieriAPI?.removeAllListeners('install-progress');
    };
  }, []);

  const handleInstall = async (featureId: string) => {
    setInstalling(featureId);
    setInstallLog('Starting install...');
    try {
      const result = await window.salieriAPI.installFeature(featureId);
      setInstallLog(result.message);
    } catch (err) {
      setInstallLog(`Install failed: ${err}`);
    } finally {
      setInstalling(null);
      // Give the backend a moment to restart, then re-probe installed state.
      setTimeout(refreshFeatures, 3000);
    }
  };

  // Hydrate the form whenever fresh settings arrive from the backend.
  useEffect(() => {
    if (!settings) return;
    setProvider(settings.provider);
    setModel(settings.model);
    setBaseUrl(settings.base_url ?? '');
    setOllamaHost(settings.ollama_host ?? '');
    setTtsEnabled(settings.tts_enabled);
    setTtsVoice(settings.tts_voice ?? '');
    setTtsRate(settings.tts_rate ?? '');
    setPersonalityName(settings.personality_name ?? '');
    setPersonalityStyle(settings.personality_style ?? '');
    setResponseLength(settings.response_length || 'normal');
    setApiKey('');
    if (settings.mascot_character) setCharacter(settings.mascot_character);
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
      tts_voice: ttsVoice.trim(),
      tts_rate: ttsRate.trim(),
      personality_name: personalityName.trim(),
      personality_style: personalityStyle.trim(),
      response_length: responseLength,
      mascot_character: character,
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
            placeholder={settings.model_defaults?.[provider] ?? 'model name'}
            onChange={(e) => setModel(e.target.value)}
            spellCheck={false}
          />
          {models.length > 0 && (
            <select
              className="settings-field__input"
              value={model && models.includes(model) ? model : ''}
              onChange={(e) => setModel(e.target.value)}
              size={Math.min(models.length, 6)}
              aria-label="Available models"
            >
              {!model || !models.includes(model) ? (
                <option value="">— typed model kept: {model || 'none'} —</option>
              ) : null}
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          )}
          {models.length > 0 ? (
            <span className="settings-field__hint">
              {models.length} models — click one to select it, or type above
            </span>
          ) : (
            <span className="settings-field__hint">
              Save settings first, then hit refresh to browse models
            </span>
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

        {ttsEnabled && (
          <div className="settings-section">
            <span className="settings-section__title">VOICE</span>
            <label className="settings-field">
              <span className="settings-field__label">TTS Voice</span>
              <input
                className="settings-field__input"
                type="text"
                value={ttsVoice}
                list="salieri-voice-list"
                placeholder="en-US-AriaNeural"
                onChange={(e) => setTtsVoice(e.target.value)}
                spellCheck={false}
              />
              <datalist id="salieri-voice-list">
                {VOICE_OPTIONS.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </datalist>
              <span className="settings-field__hint">
                Any Edge TTS voice works — e.g. en-US-AriaNeural, en-US-GuyNeural,
                en-GB-SoniaNeural, en-AU-NatashaNeural
              </span>
            </label>

            <label className="settings-field">
              <span className="settings-field__label">Speaking rate</span>
              <select
                className="settings-field__input"
                value={ttsRate}
                onChange={(e) => setTtsRate(e.target.value)}
              >
                <option value="-25%">Slower (-25%)</option>
                <option value="+0%">Normal (+0%)</option>
                <option value="+10%">Slightly fast (+10%)</option>
                <option value="+25%">Fast (+25%)</option>
              </select>
            </label>
          </div>
        )}

        <div className="settings-section">
          <span className="settings-section__title">PERSONALITY</span>
          <label className="settings-field">
            <span className="settings-field__label">Name</span>
            <input
              className="settings-field__input"
              type="text"
              value={personalityName}
              placeholder="Salieri"
              onChange={(e) => setPersonalityName(e.target.value)}
              spellCheck={false}
            />
            <span className="settings-field__hint">
              The selected character always stays Salieri — a custom name is ignored
            </span>
          </label>

          <label className="settings-field">
            <span className="settings-field__label">Response length</span>
            <select
              className="settings-field__input"
              value={responseLength}
              onChange={(e) => setResponseLength(e.target.value)}
            >
              <option value="concise">Concise</option>
              <option value="normal">Normal</option>
              <option value="detailed">Detailed</option>
            </select>
          </label>

          <label className="settings-field">
            <span className="settings-field__label">Style notes</span>
            <textarea
              className="settings-field__input settings-field__textarea"
              value={personalityStyle}
              placeholder="Optional tone tweaks, topics to favor, quirks..."
              onChange={(e) => setPersonalityStyle(e.target.value)}
              rows={3}
            />
          </label>
        </div>

        <div className="settings-section">
          <span className="settings-section__title">CHARACTER</span>
          <div className="character-selector">
            <div
              className={`character-option ${character === 'male' ? 'character-option--selected' : ''}`}
              onClick={() => setCharacter('male')}
            >
              <img src={maleNeutral} alt="Male mascot" className="character-option__image" />
              <span className="character-option__label">Male</span>
            </div>
            <div
              className={`character-option ${character === 'female' ? 'character-option--selected' : ''}`}
              onClick={() => setCharacter('female')}
            >
              <img src={femaleNeutral} alt="Female mascot" className="character-option__image" />
              <span className="character-option__label">Female</span>
            </div>
          </div>
          <span className="settings-field__hint">
            {character === 'female'
              ? 'Gloomy, sharp-tongued assistant — hides concern behind criticism. Softer neural voice.'
              : 'Machine-like anti-hero — cold, clipped, mechanical. Addresses you as Master. Low, flat neural voice.'}
            {' '}Switching character also changes personality, voice, and emotion style.
          </span>
        </div>

        <div className="settings-section">
          <span className="settings-section__title">MODULES</span>
          <span className="settings-field__hint">
            Optional backend capabilities, installed on demand into the sidecar
            Python (kept out of the installer to keep it small). Installing
            restarts the backend.
          </span>
          <ul className="modules-list">
            {features.map((f) => (
              <li key={f.id} className="modules-list__item">
                <div className="modules-list__info">
                  <span className="modules-list__label">
                    {f.label}
                    {f.core && <span className="modules-list__badge">built-in</span>}
                    {!f.core && f.installed && (
                      <span className="modules-list__badge modules-list__badge--ok">installed</span>
                    )}
                  </span>
                  <span className="settings-field__hint">{f.description}</span>
                </div>
                {!f.core && !f.installed && (
                  <button
                    type="button"
                    className="settings-btn"
                    disabled={installing !== null}
                    onClick={() => handleInstall(f.id)}
                  >
                    {installing === f.id ? 'Installing...' : 'Install'}
                  </button>
                )}
              </li>
            ))}
          </ul>
          {installLog && <p className="modules-log">{installLog}</p>}
        </div>

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
