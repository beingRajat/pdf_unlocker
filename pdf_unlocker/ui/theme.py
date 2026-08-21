"""Design tokens.

Every colour is a ``(light, dark)`` pair. CustomTkinter resolves the pair
against the current appearance mode, so a theme switch needs no repainting
code anywhere in the UI: the widgets follow the mode on their own.

Only tokens that are actually referenced live here. Anything that stops being
used belongs in git history, not in this file.
"""


class Theme:
    """Colour, type and geometry tokens for the application UI."""

    # -- Surfaces ---------------------------------------------------------
    BG = ("#F2F2F6", "#0A0A0F")             # window behind everything
    SURFACE = ("#FFFFFF", "#141419")        # cards
    SURFACE_ALT = ("#F6F6FA", "#1B1B22")    # inputs, list rows
    SURFACE_HOVER = ("#ECECF2", "#23232C")  # row hover, ghost button hover
    BORDER = ("#E3E3EA", "#26262F")
    BORDER_STRONG = ("#D2D2DC", "#33333F")

    # -- Accent -----------------------------------------------------------
    ACCENT = ("#6D4AFF", "#7C5CFF")
    ACCENT_HOVER = ("#5A34F5", "#6B4CE6")
    ACCENT_SOFT = ("#EDE9FF", "#1F1940")

    # -- Status -----------------------------------------------------------
    OK = ("#0E9F63", "#3DDC97")
    OK_SOFT = ("#E2F7EE", "#0F2C1E")

    BAD = ("#DC3A57", "#FF5C7A")
    BAD_SOFT = ("#FCE7EB", "#33131C")

    WARN = ("#B87400", "#FFB84D")
    WARN_SOFT = ("#FFF2DC", "#2E210A")

    NEUTRAL_SOFT = ("#EDEDF2", "#1E1E27")

    # -- Text -------------------------------------------------------------
    TEXT = ("#111117", "#F2F2F7")
    TEXT_DIM = ("#57576A", "#9A9AAE")
    TEXT_FAINT = ("#8A8A9C", "#66667A")
    TEXT_ON_ACCENT = "#FFFFFF"

    # -- Type -------------------------------------------------------------
    FONT = "Segoe UI"
    MONO = "Consolas"

    SIZE_DISPLAY = 21
    SIZE_TITLE = 15
    SIZE_BODY = 13
    SIZE_LABEL = 12
    SIZE_MICRO = 11

    # -- Geometry ---------------------------------------------------------
    R_CARD = 16
    R_CTRL = 10
    R_PILL = 999  # clamped by CustomTkinter to half the height

    PAD_CARD = 15
    GAP = 11

    # Character the password field displays instead of the real text
    MASK_CHAR = "•"
