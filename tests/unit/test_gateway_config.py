"""Tests gateway/config.py's HMS_REQUIRE_TLS parsing (NFR-02). Doesn't test
gateway/main.py's middleware wiring directly, since REQUIRE_TLS is read at
import time there and reloading gateway.config afterwards wouldn't affect
an already-built FastAPI app -- the parsing logic itself is the testable
unit here.
"""

from __future__ import annotations

import importlib
import os

import pytest

import gateway.config as config_module


@pytest.fixture(autouse=True)
def _reset_config_module():
    yield
    os.environ.pop("HMS_REQUIRE_TLS", None)
    importlib.reload(config_module)


def test_require_tls_defaults_to_false(monkeypatch):
    monkeypatch.delenv("HMS_REQUIRE_TLS", raising=False)
    importlib.reload(config_module)
    assert config_module.REQUIRE_TLS is False


def test_require_tls_true_when_set(monkeypatch):
    monkeypatch.setenv("HMS_REQUIRE_TLS", "true")
    importlib.reload(config_module)
    assert config_module.REQUIRE_TLS is True


def test_require_tls_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("HMS_REQUIRE_TLS", "TRUE")
    importlib.reload(config_module)
    assert config_module.REQUIRE_TLS is True


def test_require_tls_false_for_unrecognized_values(monkeypatch):
    monkeypatch.setenv("HMS_REQUIRE_TLS", "1")
    importlib.reload(config_module)
    assert config_module.REQUIRE_TLS is False
