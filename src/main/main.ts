import {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  screen,
  ipcMain,
  globalShortcut,
  dialog,
} from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcess } from 'child_process';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let pythonProcess: ChildProcess | null = null;
let isQuitting = false;

const isDev = !app.isPackaged;
const PYTHON_PORT = 9876;

// assets/ is included in the electron-builder `files` list, so this relative
// path resolves identically in dev and in the packaged app (nativeImage reads
// through app.asar transparently).
function assetPath(name: string): string {
  return path.join(__dirname, '../../assets', name);
}

function createTrayIcon(): Tray {
  const icon = nativeImage.createFromPath(assetPath('tray.png'));
  const trayIcon = new Tray(
    icon.isEmpty() ? nativeImage.createEmpty() : icon.resize({ width: 16, height: 16 })
  );

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Salieri',
      click: () => mainWindow?.show(),
    },
    {
      label: 'Hide Salieri',
      click: () => mainWindow?.hide(),
    },
    { type: 'separator' },
    {
      label: 'Voice Call',
      click: () => mainWindow?.webContents.send('start-voice-call'),
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  trayIcon.setToolTip('Salieri AI');
  trayIcon.setContextMenu(contextMenu);

  trayIcon.on('double-click', () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow?.show();
    }
  });

  return trayIcon;
}

function createWindow(): BrowserWindow {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  const win = new BrowserWindow({
    width: 380,
    height: 520,
    x: width - 400,
    y: height - 540,
    icon: assetPath('icon.png'),
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: true,
    hasShadow: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Click-through when not interacting with the window
  win.setIgnoreMouseEvents(false);

  if (isDev) {
    win.loadURL('http://localhost:5173');
    win.webContents.openDevTools({ mode: 'detach' });
  } else {
    win.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  win.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      win.hide();
    }
  });

  return win;
}

interface BackendResolution {
  command: string;
  args: string[];
  cwd?: string;
  env?: NodeJS.ProcessEnv;
}

/** Locate the backend sidecar and its Python interpreter.
 *  Returns null when nothing usable exists (caller shows an error). */
function resolveBackend(): BackendResolution | null {
  if (isDev) {
    // Dev: look for project virtualenv first, fall back to system python.
    // NOTE: backend/venv is the FULL env (torch, faster-whisper, pyaudio,
    // sentence-transformers); backend/.venv is a minimal/test env that lacks
    // them, so venv must be preferred or voice + semantic memory go missing.
    const venvCandidates = [
      path.join(__dirname, '../../backend/venv/Scripts/python.exe'),
      path.join(__dirname, '../../backend/.venv/Scripts/python.exe'),
      path.join(__dirname, '../../backend/venv/bin/python'),
      path.join(__dirname, '../../backend/.venv/bin/python'),
    ];
    const foundVenv = venvCandidates.find((p) => fs.existsSync(p));
    const command = foundVenv || 'python';
    return {
      command,
      args: [
        path.join(__dirname, '../../backend/server.py'),
        '--port',
        String(PYTHON_PORT),
      ],
    };
  }

  // Packaged: backend is a sidecar folder of loose files in resources/.
  const backendDir = path.join(process.resourcesPath, 'backend');
  const pythonExe = path.join(backendDir, 'python', 'python.exe');
  const serverPy = path.join(backendDir, 'server.py');
  if (!fs.existsSync(pythonExe) || !fs.existsSync(serverPy)) {
    return null;
  }
  return {
    command: pythonExe,
    args: [serverPy, '--port', String(PYTHON_PORT)],
    cwd: backendDir,
    env: { PYTHONPATH: backendDir },
  };
}

/** The interpreter the running backend uses — pip installs go here. */
function backendPythonExe(): string | null {
  const r = resolveBackend();
  return r ? r.command : null;
}

// ---------------------------------------------------------------------------
// Feature module registry — the modular part of the app.
// Each feature maps to pip packages installed on demand into the sidecar's
// Python. 'core' is baked into the installer; the rest are dynamic modules.
// ---------------------------------------------------------------------------
interface FeatureDef {
  id: string;
  label: string;
  description: string;
  packages: string[];
  core?: boolean;
}

const FEATURES: FeatureDef[] = [
  {
    id: 'core',
    label: 'Core (chat, memory, TTS)',
    description: 'WebSocket server, LLM providers, SQLite memory, Edge TTS.',
    packages: [],
    core: true,
  },
  {
    id: 'stt',
    label: 'Voice input (local STT)',
    description: 'Offline speech-to-text via faster-whisper + microphone capture.',
    packages: ['faster-whisper>=1.0.0,<2.0.0', 'pyaudio>=0.2.14,<1.0.0', 'numpy>=1.26.0,<3.0.0', 'soundfile>=0.12.0,<1.0.0'],
  },
  {
    id: 'semantic-memory',
    label: 'Semantic memory search',
    description: 'Embedding-based memory recall (sentence-transformers, pulls in torch ~2 GB). Without it, memory uses keyword search.',
    packages: ['sentence-transformers>=3.0.0,<6.0.0'],
  },
];

interface FeatureStatus extends FeatureDef {
  installed: boolean;
}

/** Ask the sidecar Python which of our feature packages are importable.
 *  Maps pip package names to import module names for the check. */
function checkFeaturesInstalled(pythonExe: string): Promise<Record<string, boolean>> {
  const moduleNames: Record<string, string> = {
    'stt': 'faster_whisper,pyaudio',
    'semantic-memory': 'sentence_transformers',
  };
  return new Promise((resolve) => {
    const result: Record<string, boolean> = {};
    const entries = Object.entries(moduleNames);
    if (entries.length === 0) return resolve(result);
    let pending = entries.length;
    for (const [featureId, mods] of entries) {
      const code =
        'import importlib.util,sys;' +
        `mods=${JSON.stringify(mods.split(','))};` +
        'sys.exit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)';
      const probe = spawn(pythonExe, ['-c', code], { stdio: 'ignore' });
      probe.on('close', (exitCode) => {
        result[featureId] = exitCode === 0;
        if (--pending === 0) resolve(result);
      });
      probe.on('error', () => {
        result[featureId] = false;
        if (--pending === 0) resolve(result);
      });
    }
  });
}

/**
 * Launch the Python sidecar backend.
 *
 * Packaged layout (sidecar — backend is NEVER baked into an exe/asar):
 *   <installDir>/resources/backend/server.py        — backend source
 *   <installDir>/resources/backend/python/python.exe — embedded CPython
 *
 * The sidecar lives in the `resources/` folder as loose files, so it can be
 * updated, patched, or extended (pip installs) without rebuilding the app.
 * All heavy/optional dependencies (torch, faster-whisper, ...) are installed
 * at runtime into the sidecar's site-packages — not shipped in the installer.
 */
function startPythonBackend(): void {
  const resolved = resolveBackend();
  if (!resolved) {
    const msg = isDev
      ? 'No Python interpreter found. Create backend/venv or install Python.'
      : `Backend sidecar not found at ${path.join(process.resourcesPath, 'backend')}. ` +
        'Reinstall or restore the resources/backend folder.';
    dialog.showErrorBox('Salieri AI — backend unavailable', msg);
    return;
  }

  const spawnOptions: { stdio: ['pipe', 'pipe', 'pipe']; cwd?: string; env?: NodeJS.ProcessEnv } = {
    stdio: ['pipe', 'pipe', 'pipe'],
  };
  if (resolved.cwd) spawnOptions.cwd = resolved.cwd;
  if (resolved.env) spawnOptions.env = { ...process.env, ...resolved.env };

  pythonProcess = spawn(resolved.command, resolved.args, spawnOptions);

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    console.error(`[Backend Error] ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code: number | null) => {
    console.log(`[Backend] Process exited with code ${code}`);
    pythonProcess = null;
    if (!isQuitting) {
      console.log('[Backend] Restarting...');
      setTimeout(startPythonBackend, 2000);
    }
  });
}

function stopPythonBackend(): void {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
}

/** Ask the backend to exit so startPythonBackend() launches it fresh.
 *  Used after installing optional modules so new packages are picked up. */
function restartPythonBackend(): void {
  if (pythonProcess) {
    // The 'close' handler sees isQuitting === false and respawns in 2s.
    pythonProcess.kill();
  } else {
    startPythonBackend();
  }
}

// IPC Handlers
ipcMain.handle('get-backend-port', () => PYTHON_PORT);

// ---- Feature modules (dynamic/modular backend) ----

ipcMain.handle('list-features', async (): Promise<FeatureStatus[]> => {
  const pythonExe = backendPythonExe();
  const installedMap = pythonExe ? await checkFeaturesInstalled(pythonExe) : {};
  return FEATURES.map((f) => ({
    ...f,
    installed: f.core ? true : installedMap[f.id] === true,
  }));
});

ipcMain.handle('install-feature', (event, featureId: string): Promise<{ ok: boolean; message: string }> => {
  const feature = FEATURES.find((f) => f.id === featureId);
  if (!feature || feature.core || feature.packages.length === 0) {
    return Promise.resolve({ ok: false, message: `Unknown or non-installable feature: ${featureId}` });
  }
  const pythonExe = backendPythonExe();
  if (!pythonExe) {
    return Promise.resolve({ ok: false, message: 'Backend Python not found.' });
  }

  return new Promise((resolve) => {
    const sendProgress = (message: string) => {
      event.sender.send('install-progress', { featureId, message });
    };
    sendProgress(`Installing ${feature.label}: pip install ${feature.packages.join(' ')}`);

    const installer = spawn(
      pythonExe,
      ['-m', 'pip', 'install', '--no-input', ...feature.packages],
      { stdio: ['ignore', 'pipe', 'pipe'] }
    );

    installer.stdout?.on('data', (d: Buffer) => {
      const line = d.toString().trim();
      if (line) sendProgress(line.slice(-300));
    });
    installer.stderr?.on('data', (d: Buffer) => {
      const line = d.toString().trim();
      if (line) sendProgress(line.slice(-300));
    });

    installer.on('error', (err) => {
      resolve({ ok: false, message: `Failed to run pip: ${err.message}` });
    });

    installer.on('close', (code) => {
      if (code === 0) {
        sendProgress('Installed. Restarting backend...');
        // Restart so the backend picks up the newly installed packages.
        restartPythonBackend();
        resolve({ ok: true, message: `${feature.label} installed. Backend restarting.` });
      } else {
        resolve({ ok: false, message: `pip exited with code ${code}. Check the log for details.` });
      }
    });
  });
});

ipcMain.handle('restart-backend', () => {
  restartPythonBackend();
});

ipcMain.handle('toggle-always-on-top', (_event, onTop: boolean) => {
  mainWindow?.setAlwaysOnTop(onTop);
  return mainWindow?.isAlwaysOnTop();
});

ipcMain.handle('minimize-window', () => {
  mainWindow?.minimize();
});

ipcMain.handle('hide-window', () => {
  mainWindow?.hide();
});

ipcMain.handle('resize-window', (_event, width: number, height: number) => {
  if (mainWindow) {
    const [currentX, currentY] = mainWindow.getPosition();
    const [, currentH] = mainWindow.getSize();
    const dy = height - currentH;
    mainWindow.setSize(width, height);
    // Anchor the bottom edge: grow/shrink upward so the mascot at the
    // bottom stays put whether expanding or collapsing.
    mainWindow.setPosition(currentX, currentY - dy);
  }
});

// App lifecycle
app.whenReady().then(() => {
  mainWindow = createWindow();
  tray = createTrayIcon();
  startPythonBackend();

  // Toggle visibility with global shortcut
  globalShortcut.register('Alt+Shift+S', () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow?.show();
      mainWindow?.focus();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  stopPythonBackend();
  globalShortcut.unregisterAll();
});

app.on('activate', () => {
  if (mainWindow === null) {
    mainWindow = createWindow();
  } else {
    mainWindow.show();
  }
});