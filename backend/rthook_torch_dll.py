"""PyInstaller runtime hook: make torch's DLLs loadable when frozen.

Runs before the frozen script. Registers torch/lib (and the bundle's _internal
dir) on the Windows DLL search path so c10.dll / torch_cpu.dll resolve their
dependencies, which otherwise fail with WinError 1114 under the _internal layout.
"""

import os
import sys

if sys.platform.startswith("win"):
    # In a frozen app, bundled files live in sys._MEIPASS (== _internal in onedir).
    base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

    candidates = [
        os.path.join(base, "torch", "lib"),
        base,  # DLLs may also sit at the top of _internal
    ]

    for d in candidates:
        if not os.path.isdir(d):
            continue
        try:
            os.add_dll_directory(d)
        except (OSError, AttributeError):
            pass
        # Also prepend to PATH as a fallback for older resolution behavior.
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
