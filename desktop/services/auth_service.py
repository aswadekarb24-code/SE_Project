"""Lightweight role gating for the MVP's dual-role interface -- no passwords,
just a role chosen at startup that determines which screens are shown.
Matches the scope doc's "Dual-role Interface: Receptionist (Data entry/
queue) & Doctor (Lookup/status)". There is no server-side enforcement here;
this is UI-level screen gating only, appropriate to the MVP's scope.
"""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
