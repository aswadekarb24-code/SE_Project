# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for release builds: one-file, used for the actual
release artifact (Cycle 5's "final release" step), not day-to-day dev
iteration -- a single file is slower to build and slower to start than the
one-folder dev build (build/pyinstaller.spec), so it's reserved for release
candidates only. Same exclusions as the dev spec.

Build (from the repo root): `uv run pyinstaller build/pyinstaller.release.spec`
On Windows this produces a single dist/HMS.exe. Run on a clean Windows VM to
verify NFR-04 (standalone installer) and the SQA plan's build-verification
protocol before packaging with installer.iss.
"""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH is injected by PyInstaller)

a = Analysis(  # noqa: F821
    [str(PROJECT_ROOT / "desktop" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=["sqlcipher3", "sqlcipher3.dbapi2"],
    hookspath=[],
    excludes=[
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "psycopg",
        "gateway",
        "pytest",
        "pytest_asyncio",
        "pytest_cov",
        "coverage",
        "black",
        "ruff",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HMS",
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
)
