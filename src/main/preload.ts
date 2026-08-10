import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('salieriAPI', {
  // Backend
  getBackendPort: (): Promise<number> => ipcRenderer.invoke('get-backend-port'),

  // Window controls
  toggleAlwaysOnTop: (onTop: boolean): Promise<boolean> =>
    ipcRenderer.invoke('toggle-always-on-top', onTop),
  minimizeWindow: (): Promise<void> => ipcRenderer.invoke('minimize-window'),
  hideWindow: (): Promise<void> => ipcRenderer.invoke('hide-window'),

  // Voice call events
  onStartVoiceCall: (callback: () => void): void => {
    ipcRenderer.on('start-voice-call', () => callback());
  },

  // Remove listeners
  removeAllListeners: (channel: string): void => {
    ipcRenderer.removeAllListeners(channel);
  },
});