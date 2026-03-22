# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AI Lesson Plan Generator.

Build with:
    pyinstaller lesson_plan.spec

Produces a single-folder distribution in dist/LessonPlanGenerator/.
"""

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / 'assets'), 'assets'),
        (str(root / 'data' / 'courses.json'), 'data'),
    ],
    hiddenimports=[
        'openpyxl',
        'pdfplumber',
        'PyPDF2',
        'pytesseract',
        'docx',
        'reportlab',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tests',
        'pytest',
        'ruff',
        'mypy',
        'pre_commit',
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LessonPlanGenerator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / 'assets' / 'header.png'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LessonPlanGenerator',
)
