import { contextBridge, ipcRenderer } from 'electron';

export interface FeatureModule {
  id: string;
  label: string;
  description: string;
  packages: string[];
  core?: boolean;
  installed: boolean;
}

contextBridge.exposeInMainWorld('salieriAPI', {
  // Backend
  getBackendPort: (): Promise<number> => ipcRenderer.invoke('get-backend-port'),

  // Window controls
  toggleAlwaysOnTop: (onTop: boolean): Promise<boolean> =>
    ipcRenderer.invoke('toggle-always-on-top', onTop),
  minimizeWindow: (): Promise<void> => ipcRenderer.invoke('minimize-window'),
  hideWindow: (): Promise<void> => ipcRenderer.invoke('hide-window'),
  resizeWindow: (width: number, height: number): Promise<void> =>
    ipcRenderer.invoke('resize-window', width, height),
  setClickThrough: (enabled: boolean): Promise<void> =>
    ipcRenderer.invoke('set-click-through', enabled),

  // Feature modules (dynamic backend capabilities)
  listFeatures: (): Promise<FeatureModule[]> => ipcRenderer.invoke('list-features'),
  installFeature: (featureId: string): Promise<{ ok: boolean; message: string }> =>
    ipcRenderer.invoke('install-feature', featureId),
  restartBackend: (): Promise<void> => ipcRenderer.invoke('restart-backend'),
  onInstallProgress: (callback: (featureId: string, message: string) => void): void => {
    ipcRenderer.on('install-progress', (_e, payload: { featureId: string; message: string }) =>
      callback(payload.featureId, payload.message)
    );
  },

  // Voice call events
  onStartVoiceCall: (callback: () => void): void => {
    ipcRenderer.on('start-voice-call', () => callback());
  },

  // Remove listeners
  removeAllListeners: (channel: string): void => {
    ipcRenderer.removeAllListeners(channel);
  },
});
