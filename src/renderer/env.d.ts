/// <reference types="vite/client" />

declare module '*.png' {
  const src: string;
  export default src;
}

interface FeatureModule {
  id: string;
  label: string;
  description: string;
  packages: string[];
  core?: boolean;
  installed: boolean;
}

interface SalieriAPI {
  getBackendPort: () => Promise<number>;
  toggleAlwaysOnTop: (onTop: boolean) => Promise<boolean>;
  minimizeWindow: () => Promise<void>;
  hideWindow: () => Promise<void>;
  resizeWindow: (width: number, height: number) => Promise<void>;
  listFeatures: () => Promise<FeatureModule[]>;
  installFeature: (featureId: string) => Promise<{ ok: boolean; message: string }>;
  restartBackend: () => Promise<void>;
  onInstallProgress: (callback: (featureId: string, message: string) => void) => void;
  onStartVoiceCall: (callback: () => void) => void;
  removeAllListeners: (channel: string) => void;
}

declare global {
  interface Window {
    salieriAPI: SalieriAPI;
  }
}

export {};