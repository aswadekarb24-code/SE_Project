# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the desktop app -- one-folder build, used during
development for fast incremental rebuilds (see pyinstaller.release.spec for
the one-file variant used for actual release artifacts).

Excludes tests/, gateway/, and dev-only packages so the desktop build never
bundles FastAPI/SQLAlchemy/psycopg/pytest/etc -- those are only installed
via the `gateway`/`dev` extras, never part of the desktop app's own runtime
dependencies.

Build (from the repo root): `uv run pyinstaller build/pyinstaller.spec`
On Windows this produces dist/HMS/HMS.exe; on Linux/macOS, a native binary
of the same name, useful for validating the spec itself (missing-module
errors, bundling correctness) without a Windows machine.
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
    [],
    exclude_binaries=True,
    name="HMS",
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="HMS",
)
