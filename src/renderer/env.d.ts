/// <reference types="vite/client" />

declare module '*.png' {
  const src: string;
  export default src;
}

interface SalieriAPI {
  getBackendPort: () => Promise<number>;
  toggleAlwaysOnTop: (onTop: boolean) => Promise<boolean>;
  minimizeWindow: () => Promise<void>;
  hideWindow: () => Promise<void>;
  resizeWindow: (width: number, height: number) => Promise<void>;
  onStartVoiceCall: (callback: () => void) => void;
  removeAllListeners: (channel: string) => void;
}

declare global {
  interface Window {
    salieriAPI: SalieriAPI;
  }
}

export {};