/// <reference types="vite/client" />

interface SalieriAPI {
  getBackendPort: () => Promise<number>;
  toggleAlwaysOnTop: (onTop: boolean) => Promise<boolean>;
  minimizeWindow: () => Promise<void>;
  hideWindow: () => Promise<void>;
  onStartVoiceCall: (callback: () => void) => void;
  removeAllListeners: (channel: string) => void;
}

declare global {
  interface Window {
    salieriAPI: SalieriAPI;
  }
}

export {};