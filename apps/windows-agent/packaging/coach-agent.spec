# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec. Build this on Windows, where PySide6 and the game live.

    pyinstaller packaging/coach-agent.spec
"""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all("PySide6")

a = Analysis(
    ["../coach_agent/__main__.py"],
    pathex=[".."],
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
