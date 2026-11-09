# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec. Build this on Windows, where PySide6 and the game live.

From the repository root:

    uv run --with pyinstaller pyinstaller --noconfirm --distpath apps/windows-agent/dist --workpath apps/windows-agent/build apps/windows-agent/packaging/coach-agent.spec
"""

import os

from PyInstaller.utils.hooks import collect_all

agent_root = os.path.abspath(os.path.join(SPECPATH, ".."))

datas, binaries, hiddenimports = collect_all("PySide6")

a = Analysis(
    [os.path.join(agent_root, "coach_agent", "__main__.py")],
    pathex=[agent_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["websockets", "telemetry_schema"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AssettoCorsaCoachAgent",
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="AssettoCorsaCoachAgent",
)
