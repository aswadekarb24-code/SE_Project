# Setup Guide

Detailed, per-OS setup, testing, and (for Windows) packaging instructions
for the Hybrid Offline-First HMS. See `README.md` for a quick overview and
`PLAN.md`/`docs/` for the project's planning documents.

## Prerequisites (all platforms)

- **Python 3.11+** — `uv` can also download and manage its own Python, so a
  system Python isn't strictly required.
- **[`uv`](https://docs.astral.sh/uv/)** — dependency management for the
  desktop app, display simulator, and all tests.
- **Docker + Docker Compose** — runs the local Postgres + FastAPI gateway
  that stands in for Supabase during development. Only needed for sync/
  gateway work; the desktop app itself runs fully offline without it.
- **Git**

---

## 1. Windows

### 1.1 Install prerequisites

- **uv**: in PowerShell, run
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Docker Desktop**: <https://www.docker.com/products/docker-desktop/>
  (WSL2 backend recommended — requires Windows 10 version 2004+ or
  Windows 11).
- **Git for Windows**: <https://git-scm.com/download/win>
- Python itself does not need a separate install — `uv sync` below fetches
  a managed Python automatically if none is found.

### 1.2 Clone and install dependencies

```powershell
git clone <repo-url>
cd SE_Project
uv sync --extra dev --extra gateway
```

### 1.3 Run the app

```powershell
uv run python -m desktop.main
```

The sign-in screen appears first. On a fresh install it opens on
**Create account**: make a Receptionist or Doctor account (doctors also pick
their department), and you're signed straight in. The local database is
created (and encrypted — see `desktop/data/db.py`) at
`%USERPROFILE%\.hms\hms.db` on first launch. An existing database from an
earlier version is upgraded in place: new tables are added and every
existing patient is given a patient number.

### 1.4 Run the tests

```powershell
# Fast, no Docker required
uv run pytest tests/unit tests/system

# Needs the gateway/Postgres stack
docker compose up -d
uv run pytest tests/integration
docker compose down -v
```

### 1.5 Build the Windows `.exe`

Both specs exclude `tests/`, `gateway/`, and dev-only packages — the
desktop build never bundles FastAPI/SQLAlchemy/pytest/etc. (see
`build/pyinstaller.spec` and `build/pyinstaller.release.spec` for why).

```powershell
# One-folder build -- fast rebuilds, for day-to-day dev iteration.
# Produces dist\HMS\HMS.exe
uv run pyinstaller build\pyinstaller.spec

# One-file build -- for an actual release artifact (slower to build and to
# start, so only used for release candidates). Produces dist\HMS.exe
uv run pyinstaller build\pyinstaller.release.spec
```

Run from the repo root with no `--distpath`/`--workpath` override, so
output lands at `dist\` (repo root) and intermediate files at
`build\pyinstaller\` / `build\pyinstaller.release\` — both already excluded
by `.gitignore`, alongside (not overwriting) the committed `.spec`/`.iss`
files already in `build\`.

**Smoke test the build**: run `dist\HMS\HMS.exe` (or `dist\HMS.exe` for the
release build) directly. Confirm the sign-in screen appears, create a
receptionist account, issue a token on the Check-in screen and print its
slip, log out, create a doctor account, call the patient, save a report and
export it as PDF, and confirm `%USERPROFILE%\.hms\hms.db` was created. (This exact flow was verified on Linux during Cycle 5 — see
`docs/progress/cycle-5.md` — producing a working native binary and a
correctly SQLCipher-encrypted DB; only the Windows-specific `.exe` artifact
itself still needs this same check run on Windows.)

### 1.6 Build the installer

1. Build the **release** spec first (§1.5) so `dist\HMS.exe` exists.
2. Install [Inno Setup](https://jrsoftware.org/isdl.php).
3. Compile `build\installer.iss` — either open it in the Inno Setup
   Compiler GUI and click Compile, or from the command line:
   ```powershell
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
   ```
4. Output: `build\installer-output\HMS-Setup-0.1.0.exe` (also
   `.gitignore`d).

### 1.7 Clean-VM release verification (SQA plan gate)

Before treating a build as release-ready, per the SQA plan's release
sign-off criteria:

- [ ] `uv run pytest --cov --cov-report=term-missing` shows ≥80% coverage
- [ ] 100% pass rate on `tests/system` (offline/network-disconnect
      simulation)
- [ ] Zero open P1/P2 defects (see severity table in
      `docs/SE_Group_3_Lab_5_241080077.pdf`)
- [ ] `HMS-Setup-0.1.0.exe` installs cleanly on a **clean Windows VM** with
      no Python/uv/Docker preinstalled
- [ ] The installed app launches, an account can be created and signed in to, and
      `%USERPROFILE%\.hms\hms.db` is created and encrypted on first use
- [ ] Uninstalling via Windows "Apps & Features" removes the app files
      (the `.hms` data directory is intentionally left behind — it's user
      data, not application files)

This checklist is the Windows-only work explicitly flagged as unverified in
`docs/progress/cycle-5.md` (written from a Linux sandbox with no Windows VM
available).

### 1.8 Windows-specific notes

- The built `.exe`/installer is **unsigned** (no code-signing certificate
  for this MVP) — Windows SmartScreen or antivirus may warn on first run;
  choose "More info → Run anyway", or sign the binary if you have a
  certificate.
- Docker Desktop requires WSL2 or Hyper-V virtualization enabled in BIOS/
  Windows Features.

---

## 2. Linux

### 2.1 Install prerequisites

```bash
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Docker + Compose: use your distro's package manager, e.g.
#   Arch:   sudo pacman -S docker docker-compose
#   Ubuntu: sudo apt install docker.io docker-compose-plugin
# then: sudo systemctl enable --now docker
```

PyQt6's wheels bundle Qt itself but not the underlying system graphics/IPC
libraries Qt links against — on a minimal install (including bare CI
runners) you may need to install them yourself. On Debian/Ubuntu:

```bash
sudo apt install libgl1 libegl1 libxkbcommon0 libglib2.0-0 libdbus-1-3
```

This exact list was verified with `ldd` against the real Qt6 shared
libraries on a clean `ubuntu:24.04` container (see `.github/workflows/ci.yml`,
which installs the same packages for CI) — not guessed. Arch/Fedora/etc.
typically have these as transitive dependencies of a `qt6-base`-equivalent
package already.

### 2.2 Clone and install dependencies

```bash
git clone <repo-url>
cd SE_Project
uv sync --extra dev --extra gateway
```

### 2.3 Run the app / tests

```bash
uv run python -m desktop.main

uv run pytest tests/unit tests/system

docker compose up -d
uv run pytest tests/integration
docker compose down -v
```

### 2.4 Headless testing (no display / CI)

- PyQt6 tests run with `QT_QPA_PLATFORM=offscreen` (set automatically in
  `tests/conftest.py`) — no X server required.
- `display_sim`'s Tkinter widgets are **not** exercised by the automated
  suite (no Xvfb configured in CI); only the Tkinter-free business logic in
  `display_sim/display_state.py` is unit-tested. To try the real display
  window manually, run `uv run python -m display_sim.main` on a machine
  with a display, or under `xvfb-run`.

### 2.5 Building a Linux binary (spec validation only)

```bash
uv run pyinstaller build/pyinstaller.spec
./dist/HMS/HMS
```

This produces a native Linux binary, **not** a Windows `.exe` — useful only
to confirm the PyInstaller spec itself (dependency bundling, exclusions,
hidden imports) builds and runs cleanly before building on an actual
Windows machine. This is exactly how `build/pyinstaller.spec` was validated
during Cycle 5.

---

## 3. macOS

### 3.1 Install prerequisites

```bash
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv

# Docker Desktop for Mac
# https://www.docker.com/products/docker-desktop/
```

### 3.2 Clone and install dependencies

```bash
git clone <repo-url>
cd SE_Project
uv sync --extra dev --extra gateway
```

### 3.3 Run the app / tests

```bash
uv run python -m desktop.main

uv run pytest tests/unit tests/system

docker compose up -d
uv run pytest tests/integration
docker compose down -v
```

### 3.4 Notes

- PyQt6 and `sqlcipher3` both ship prebuilt wheels for macOS (Intel and
  Apple Silicon, universal2); a plain `uv sync` should not require Xcode
  Command Line Tools or a system Qt install. (Note: the dependency is
  `sqlcipher3`, not the similarly-named `sqlcipher3-binary` — the latter
  only ever published Linux x86_64 wheels and would fail to install here;
  see `pyproject.toml`'s comment on this.)
- The Windows `.exe` cannot be built or run on macOS — PyInstaller
  cross-compilation isn't supported; that part of packaging needs an actual
  Windows machine or VM (see §1.5–1.7).

---

## Common configuration (all OSes)

Copy `.env.example` to `.env` and adjust as needed. `docker compose up -d`
reads `.env` automatically; the desktop app reads these as plain
environment variables (export them yourself, or use a tool like
[`direnv`](https://direnv.net/)).

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Postgres connection string the gateway uses | local docker-compose Postgres (port 5433 on the host) |
| `HMS_GATEWAY_URL` | Desktop app's sync target; unset = fully offline (`NoOpSyncProvider`) | unset |
| `HMS_SYNC_INTERVAL_SECONDS` | Background sync poll interval | `30` |
| `HMS_DB_ENCRYPTION_KEY` | SQLCipher key for the local DB — **set a real secret for any non-dev deployment** | fixed, publicly-known dev-only fallback |
| `HMS_REQUIRE_TLS` | Gateway refuses plain HTTP when `true` (needs a TLS-terminating reverse proxy in front) | `false` |

## Testing summary (all OSes)

| Command | What it covers | Requirements |
|---|---|---|
| `uv run pytest tests/unit` | Business logic, repositories, services, UI widgets (headless) | none |
| `uv run pytest tests/system` | WAL power-interruption safety, shortened display-node soak test | none |
| `uv run pytest tests/integration` | LAN broadcast latency, gateway `/health` + `/sync/push`, Last-Write-Wins conflict resolution | `docker compose up -d` first |
| `uv run pytest --cov --cov-report=term-missing` | Coverage report (target ≥80% per the SQA plan) | same as above |
| `uv run ruff check .` / `uv run black --check .` | Lint / format | none |
| `uv run pytest -m perf` | Wall-clock latency assertions (NFR-01, e.g. write latency) | none, but run **locally on real hardware** -- excluded from CI (`-m "not perf"`) since shared/virtualized CI runners (especially Windows) have I/O latency variance unrelated to the app's actual performance; see `docs/progress/cycle-5.md`'s addendum |

Per-cycle metrics (coverage %, write/broadcast latency, soak-test results,
defect counts) are tracked cumulatively in `docs/progress/cycle-0.md`
through `cycle-5.md`.
