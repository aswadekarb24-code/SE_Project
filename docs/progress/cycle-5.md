# Cycle 5 — Packaging & Hardening

## Objectives & risks addressed

NFR-02 (encryption at rest + TLS transport) and NFR-04 (standalone Windows
installer). This cycle ran in a Linux sandbox with no Windows VM available,
so the user explicitly scoped it up front: build and verify everything that
*can* be verified on Linux, and clearly flag the remainder as a manual step
for a Windows machine rather than silently claiming it as done.

## What shipped (demoable, verified here)

- **SQLCipher encryption at rest**: `desktop/data/db.py` now opens
  connections via `sqlcipher3` (a drop-in build of the sqlite3 C extension
  linked against SQLCipher) instead of stdlib `sqlite3`, with `PRAGMA key`
  set from `HMS_DB_ENCRYPTION_KEY` (falling back to a documented, clearly
  labeled *insecure* dev default so local dev/tests need zero setup).
  `sqlite3.Connection` type hints elsewhere in the codebase are left as-is
  since sqlcipher3's objects are DB-API-compatible duck types — no ripple
  effect across the ~15 files that hold a connection.
  - `PRAGMA` statements don't support `?` parameter binding (verified by
    hitting a real syntax error first); the key is embedded via standard
    SQL single-quote-doubling escaping instead, not an ad-hoc format.
  - Verified: an encrypted file is unreadable by plain stdlib `sqlite3`
    (`sqlite3.DatabaseError`), reopening with the correct key reads data
    back correctly, and a wrong key fails (`sqlcipher3.dbapi2.DatabaseError`).
    4 new tests in `tests/unit/test_db_encryption.py`.
  - Re-measured write latency with encryption now in the hot path: p50
    0.246ms, p99 0.412ms over 500 iterations — still comfortably under the
    10ms NFR-01 target (was p99 0.130ms unencrypted in Cycle 1; encryption
    overhead is real but small).
  - Caught and fixed a real issue during manual verification: a leftover
    *unencrypted* `~/.hms/hms.db` from pre-Cycle-5 manual testing correctly
    failed to open once SQLCipher was wired in ("file is not a database").
    This is expected SQLCipher behavior, not a bug — flagging here because
    it's a genuine migration consideration: there's no automatic
    plaintext-to-encrypted migration path. A fresh install is unaffected;
    an in-place upgrade of an existing pre-encryption deployment is not
    handled and would need a one-time migration step if that scenario ever
    arises (it doesn't for this MVP, which has no prior encrypted-or-not
    release).
- **HTTPS/TLS enforcement (gateway)**: `gateway/config.py` reads
  `HMS_REQUIRE_TLS` (off by default, so local docker-compose dev keeps
  working over plain HTTP with no cert); when set, `gateway/main.py` adds
  Starlette's `HTTPSRedirectMiddleware`. A reverse proxy or
  `uvicorn --ssl-certfile/--ssl-keyfile` is expected to actually terminate
  TLS in production; this just makes the app itself refuse plain HTTP once
  that's in place. 4 new tests in `tests/unit/test_gateway_config.py`
  covering the env-var parsing.
- **PyInstaller packaging**: `build/pyinstaller.spec` (one-folder, for fast
  dev iteration) and `build/pyinstaller.release.spec` (one-file, for actual
  release builds) -- both exclude `tests/`, `gateway/`, and dev-only
  packages so the desktop build never bundles FastAPI/SQLAlchemy/pytest/etc.
  **Actually built and ran the one-folder spec on this Linux machine**:
  `uv run pyinstaller build/pyinstaller.spec` succeeded (bundling PyQt6 +
  sqlcipher3 + the app with no missing-module errors), produced a working
  237MB native binary, and launching it created and correctly encrypted a
  fresh local DB. This validates the spec's correctness (dependency
  analysis, exclusions, hidden imports) even though the artifact itself is
  a Linux binary, not a Windows `.exe`.
- `build/installer.iss` — an Inno Setup script wrapping the one-file build
  into a Windows installer. Written but **not compiled or run** -- Inno
  Setup is Windows-only tooling.
- Re-ran the full test suite (94 offline + 6 Docker-Compose integration)
  after every change in this cycle; all still pass, 88% offline coverage.

## What was NOT verified here (needs a Windows machine)

- Actually producing a Windows `.exe` via `pyinstaller.release.spec` --
  only a Linux binary was produced and smoke-tested.
- Compiling `installer.iss` with Inno Setup and running the resulting
  installer.
- The SQA plan's clean-Windows-VM build-verification protocol.
- Confirming PyQt6 renders/behaves identically on real Windows (this
  project targeted Linux-dev-friendliness from Cycle 0 specifically so this
  risk stays contained to actual Windows-specific rendering quirks, not
  missing dependencies).
- The SQA plan's final release sign-off (zero open P1/P2, ≥80% coverage,
  100% offline-simulation pass rate, clean installer run) requires the
  Windows-specific items above before it can be formally declared met --
  everything else in that checklist is already satisfied as of this cycle.

## Metrics measured this cycle

- Offline test coverage: 88% (94 tests); combined with Docker-Compose
  integration tests, 100 tests total, all passing.
- Write latency with encryption: p50 0.246ms / p99 0.412ms (500 runs) --
  still far under the 10ms target.
- PyInstaller build (Linux, one-folder): succeeded with zero missing-module
  errors; bundle size 237MB (PyQt6's Qt libraries dominate this; untrimmed,
  since minimizing bundle size further wasn't this cycle's goal).
- Open defects: P1 0 / P2 0 / P3 0 / P4 0 (the unencrypted-stale-DB issue
  above was dev-environment cleanup, not a shipped defect).

## Carried-over risks / decisions

- The actual Windows `.exe` build, installer compilation, and clean-VM
  verification remain open action items for whoever has access to a
  Windows machine -- this is a environment constraint, not deferred scope.
- No plaintext-to-encrypted DB migration tool exists; not needed for this
  MVP (no prior unencrypted release), but would be required if the schema
  or encryption approach changes again after a real release ships.
- `HMS_REQUIRE_TLS` enforcement is app-level only; actual TLS termination
  (cert management) is explicitly the deploying operator's responsibility
  (reverse proxy or uvicorn flags), not something this codebase manages.

## Addendum: two real cross-OS defects found after the fact

Running `uv sync` for real on Windows and macOS, and CI running on
`ubuntu-latest`, surfaced two genuine problems this cycle's Linux-only
verification missed. Both are fixed now; documented here rather than
silently rewriting the history above.

1. **`sqlcipher3-binary` had no Windows or macOS wheels, ever.** Checking
   PyPI's actual file listing after the fact showed every released version
   only published `manylinux` (Linux x86_64) wheels -- `uv sync` failed
   outright on both Windows and macOS with "doesn't have a source
   distribution or wheel for the current platform." The fix:
   `sqlcipher3` (same `coleifer/sqlcipher3` project, no `-binary` suffix)
   has shipped genuine self-contained wheels for Windows (win32/win_amd64/
   win_arm64), macOS (universal2/x86_64/arm64), and Linux since 0.6.2 --
   confirmed against PyPI's file listing and verified as a drop-in
   (`sqlcipher3.dbapi2`, same API) on this machine before switching
   `pyproject.toml`. This should have been checked against PyPI's actual
   wheel matrix *before* picking the dependency in the first place, not
   after a user hit the failure on a real Windows/macOS machine.
2. **Ubuntu CI failed to even import PyQt6**: `ImportError:
   libEGL.so.1: cannot open shared object file`. This Linux sandbox already
   had the needed system Qt/graphics libraries installed, so Cycle 5's
   verification never exercised a bare system and never caught this. Root
   cause (confirmed with `ldd` against the real `libQt6Core/Gui/Widgets/
   DBus.so` files and the offscreen platform plugin on a clean
   `ubuntu:24.04` container, then verified by actually instantiating
   `QApplication`): five missing shared libraries --
   `libgl1 libegl1 libxkbcommon0 libglib2.0-0 libdbus-1-3`. Added as an
   explicit install step in `.github/workflows/ci.yml` and documented in
   `SETUP.md`'s Linux section.

Takeaway carried into future work: "the Linux sandbox can run it" is not
evidence it works on other platforms or on a minimal Linux install --
dependency/wheel-availability and system-library claims need to be checked
against the actual target (PyPI's file listing, a clean container) rather
than generalized from what happens to already be present in this dev
environment.
