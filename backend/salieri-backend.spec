# PyInstaller spec for the Salieri AI backend.
# Build with:  pyinstaller salieri-backend.spec
# Produces:    backend/dist/salieri-backend.exe  (single-file, console)

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect data/binaries/submodules for these. Kept narrow on purpose:
# faster-whisper runs on CTranslate2 (NOT torch), and torch itself is handled
# well by PyInstaller's built-in hook without force-collecting every submodule.
_collect_packages = [
    "faster_whisper",
    "ctranslate2",
    "sentence_transformers",
    "edge_tts",
    "sqlite_vec",
    "tokenizers",
    # NOTE: scipy & scikit-learn are intentionally NOT collect_all'd (it would
    # drag in thousands of *.tests modules). PyInstaller's built-in hooks pull
    # their runtime modules automatically via the sentence_transformers chain.
]

datas = []
binaries = []
hiddenimports = []

for pkg in _collect_packages:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        # Package not installed -> skip (backend degrades gracefully).
        pass

hiddenimports += [
    "websockets",
    "websockets.asyncio",
    "websockets.asyncio.server",
    "ollama",
    "openai",
    "aiohttp",
    "numpy",
    "soundfile",
    "pyaudio",
    "dotenv",
]

a = Analysis(
    ["server.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["rthook_torch_dll.py"],
    excludes=[
        # --- Heavy GUI / plotting / notebook frameworks we never use ---
        "matplotlib", "tkinter",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "IPython", "jupyter", "notebook", "ipykernel",
        # --- Scientific stack not needed at runtime ---
        # NOTE: scipy & scikit-learn are HARD deps of sentence-transformers, so
        # they must NOT be excluded or memory semantic search breaks.
        "pandas", "cv2", "PIL",
        # --- onnxruntime test/benchmark/tooling bloat (faster-whisper uses ctranslate2) ---
        "onnxruntime.tools", "onnxruntime.transformers",
        # --- torch dev/experimental/test submodules (keep core torch via its hook) ---
        "torch.test", "torch.testing", "torch.benchmarks", "torch.fb",
        "torch.fx.experimental", "torch.export",
        # --- cloud SDKs pulled in transitively but unused ---
        "boto3", "botocore",
        # --- test-suite bloat from scipy / scikit-learn ---
        "scipy.tests", "sklearn.tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Drop the outdated VC++ runtime / UCRT DLLs PyInstaller bundles from the build
# machine (14.36). torch 2.13 needs the newer 14.51 runtime; by removing the
# bundled copies, Windows resolves them from System32 instead (avoids the
# c10.dll WinError 1114 "DLL initialization routine failed").
_DROP_SYSTEM_DLLS = {
    "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
    "vcruntime140.dll", "vcruntime140_1.dll",
    "concrt140.dll",
}
a.binaries = [
    b for b in a.binaries
    if not (
        b[0].lower() in _DROP_SYSTEM_DLLS
        or b[0].lower().startswith("api-ms-win-")
    )
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Onedir mode: torch's DLLs (c10.dll etc.) fail to load from PyInstaller's
# onefile temp-extraction dir on Windows, so ship an unpacked folder instead.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="salieri-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep console so Electron can read stdout/stderr logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="salieri-backend",
)
