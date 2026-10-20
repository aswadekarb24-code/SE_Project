"""Shared visual design tokens for the desktop app (Qt) and the LAN display
simulator (Tkinter). Plain constants with no GUI imports, so the display
client can use them without pulling in PyQt6.

Values follow the UI restyle spec. The few spec colours that fail WCAG AA
(4.5:1) for text were darkened just enough to pass; each one is noted inline.
"""

from __future__ import annotations

# Surfaces
CANVAS = "#ECECEC"
SHELL = "#F6F6F7"
SURFACE = "#FFFFFF"
SURFACE_SUBTLE = "#F7F7F8"
HOVER = "#F9FAFB"
PRESSED = "#F3F4F6"
BORDER = "#ECECEE"
BORDER_STRONG = "#E5E7EB"
BORDER_HOVER = "#D1D5DB"
DIVIDER = "#F1F1F3"

# Text
TEXT_PRIMARY = "#111827"
# Spec #6B7280 is 4.48:1 on SHELL; this passes on SURFACE, SHELL and SURFACE_SUBTLE.
TEXT_SECONDARY = "#6A717F"
# Spec muted #9CA3AF is only 2.5:1, so placeholders use the AA-safe secondary grey.
TEXT_MUTED = TEXT_SECONDARY
# Disabled controls are exempt from AA, so they keep the spec's light grey.
TEXT_DISABLED = "#9CA3AF"
TEXT_ON_ACCENT = "#FFFFFF"

# Accent. ACCENT is the spec blue, used for focus borders and other non-text
# marks (3.5:1 clears the 3:1 bar for UI parts). PRIMARY is the same hue
# darkened for button fills and blue text: white on #1E88F7 is only 3.6:1.
ACCENT = "#1E88F7"
PRIMARY = "#086CD5"
PRIMARY_HOVER = "#065DB8"
PRIMARY_DISABLED = "#A8CCF5"
PRIMARY_TINT = "#E8F2FE"
DARK_ACCENT = "#0F1B2D"

# Status (text on tint, plus a slightly darker border of the same hue)
SUCCESS = "#117F3A"  # spec #16A34A is 3.0:1 on its tint
SUCCESS_TINT = "#E7F7EE"
SUCCESS_BORDER = "#BCE5CB"
DANGER = "#D31B44"  # spec #E11D48 is 4.1:1 on its tint
DANGER_TINT = "#FDECEF"
DANGER_BORDER = "#F7C6D1"
WARNING = "#8E6A06"
WARNING_TINT = "#FEF6E0"
WARNING_BORDER = "#F3DE9F"

# Highlight-box gradient border (light blue to light pink)
HIGHLIGHT_START = "#CFE3FD"
HIGHLIGHT_END = "#F9D3E0"

# Typography: the first family installed on the machine wins.
FONT_FAMILIES = ("Inter", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Arial")
FONT_SIZE_LABEL = 13
FONT_SIZE_BODY = 14
FONT_SIZE_LEAD = 16
FONT_SIZE_TITLE = 20
FONT_SIZE_FEATURE = 28

# Shape and spacing (px)
RADIUS_SHELL = 28
RADIUS_CARD = 20
RADIUS_TILE = 12
RADIUS_INPUT = 10
RADIUS_BUTTON = 8
RADIUS_BADGE = 6
SPACE_1 = 8
SPACE_2 = 16
SPACE_3 = 24
