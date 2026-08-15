import {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  screen,
  ipcMain,
  globalShortcut,
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

function startPythonBackend(): void {
  let command: string;
  let args: string[];

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
    command = foundVenv || 'python';
    args = [
      path.join(__dirname, '../../backend/server.py'),
      '--port',
      String(PYTHON_PORT),
    ];
  } else {
    // Packaged: run the frozen (PyInstaller) backend executable.
    command = path.join(
      process.resourcesPath,
      'backend',
      'salieri-backend.exe'
    );
    args = ['--port', String(PYTHON_PORT)];
  }

  pythonProcess = spawn(command, args, {
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    console.error(`[Backend Error] ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code: number | null) => {
    console.log(`[Backend] Process exited with code ${code}`);
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

// IPC Handlers
ipcMain.handle('get-backend-port', () => PYTHON_PORT);

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