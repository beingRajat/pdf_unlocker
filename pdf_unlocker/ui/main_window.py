"""Main application window.

Files and results share one tall panel behind a segmented switcher. Two
separate lists meant two cramped lists on a laptop screen, with rows clipped
mid-height; one panel gives either view room to breathe, and the counters stay
in the header so switching is never needed to watch a run.

All PDF work happens on worker threads. This module only drains the result
queue and never touches pikepdf directly.

Feedback is inline: completion, export and validation speak through the
floating toast rather than modal dialogs, so nothing blocks the window while a
batch runs. The one remaining dialog is the close-during-processing
confirmation, which genuinely needs an answer.
"""

import contextlib
import logging
import os
import queue
import subprocess
import sys
import threading
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    TkinterDnD = None
    DND_FILES = None
    DRAG_DROP_AVAILABLE = False

from pdf_unlocker import __version__
from pdf_unlocker.core.config_manager import ConfigManager
from pdf_unlocker.core.file_scanner import find_pdfs, is_pdf
from pdf_unlocker.core.password_manager import PasswordManager
from pdf_unlocker.core.pdf_processor import (
    MessageType,
    PDFProcessor,
    Status,
    UnlockResult,
)
from pdf_unlocker.core.results_exporter import ResultsExporter
from pdf_unlocker.ui.theme import Theme

ctk.set_default_color_theme("blue")

# Rebuilding a row per file is cheap for tens of files and painful for
# thousands, so the lists render a window onto the data and count the rest.
MAX_FILE_ROWS = 60
MAX_RESULT_ROWS = 200

TOAST_DURATION_MS = 4500

# Unscaled geometry. CustomTkinter applies display scaling on top of these.
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 790
MIN_WIDTH = 640
MIN_HEIGHT = 560

# A scrollable list reports its whole content as its preferred height, which
# would let a long file list push everything below it off screen. The list
# therefore sits in a holder of a fixed height that scrolls internally and
# grows only into spare room.
LIST_HEIGHT = 208

VIEW_FILES = "Files"
VIEW_RESULTS = "Results"


def human_size(path: str) -> str:
    """Format a file size for display, tolerating a file that vanished."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "--"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def ellipsize(text: str, limit: int = 44) -> str:
    """Shorten a filename in the middle, keeping the extension readable."""
    if len(text) <= limit:
        return text
    head = (limit - 3) // 2
    tail = limit - 3 - head
    return f"{text[:head]}...{text[-tail:]}"


def truncate(text: str, limit: int = 34) -> str:
    """Shorten a message at the end.

    Middle-elision suits filenames but mangles a sentence: "None of the
    pro...passwords worked" reads worse than a clean tail cut.
    """
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class MainWindow(ctk.CTk):
    """The application window."""

    def __init__(self, config_manager: ConfigManager, logger: logging.Logger):
        super().__init__()

        self.config_manager = config_manager
        self.logger = logger
        self.config = config_manager.load_config()

        # State
        self.selected_files: list[str] = []
        self.results: list[UnlockResult] = []
        self.is_processing = False
        self.result_queue: Optional[queue.Queue] = None
        self.output_folder: Optional[str] = None
        self.output_folders: list[str] = []
        self._toast_timer: Optional[str] = None
        self._result_rows = 0
        self.results_empty: Optional[ctk.CTkLabel] = None
        # Remove buttons on file rows, so the processing lockout can reach them.
        self._file_row_buttons: list[ctk.CTkButton] = []

        # The password field masks itself and get() returns the real text, so
        # there is no second copy of the secret to keep in sync.
        self.password_visible = False

        self.processor = PDFProcessor(logger)
        self.keyring_available = PasswordManager.is_available()

        ctk.set_appearance_mode(self.config.get("appearance_mode", "dark"))

        self._setup_window()
        # Before the UI is built: the empty-state copy depends on the answer.
        self.dnd_ready = self._load_tkdnd()
        self._build_ui()
        self._load_saved_data()
        self._setup_dnd()
        self._bind_shortcuts()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # =====================================================================
    # WINDOW
    # =====================================================================

    def _setup_window(self):
        self.title("Unlocker")
        self.configure(fg_color=Theme.BG)

        # CustomTkinter multiplies every geometry figure by the display
        # scaling, while winfo_screen* report already-scaled pixels. Work in
        # unscaled units on both sides or the window opens taller than the
        # screen and pack silently clips the bottom of the layout away.
        scaling = self._get_window_scaling() or 1.0
        avail_w = int(self.winfo_screenwidth() / scaling) - 40
        avail_h = int(self.winfo_screenheight() / scaling) - 64

        width = min(WINDOW_WIDTH, max(MIN_WIDTH, avail_w))
        height = min(WINDOW_HEIGHT, max(MIN_HEIGHT, avail_h))

        x = max(0, (avail_w - width) // 2 + 20)
        y = max(0, (avail_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)

    def _bind_shortcuts(self):
        """Keyboard access for every primary action."""
        self.bind("<Control-o>", lambda e: self._browse_files())
        self.bind("<Control-O>", lambda e: self._browse_folder())
        self.bind("<Control-Return>", lambda e: self._try_start())
        self.bind("<Control-l>", lambda e: self._clear_files())
        self.bind("<Escape>", lambda e: self._cancel() if self.is_processing else None)

    # =====================================================================
    # BUILD
    # =====================================================================

    def _build_ui(self):
        self._build_topbar()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(10, 0))
        self.body = body

        self._build_main_card(body)
        self._build_key_card(body)
        self._build_action_row(body)
        self._build_toast()

        self._switch_view(VIEW_FILES)

    def _card(self, parent, **kwargs):
        """The one container shape the whole UI is built from."""
        return ctk.CTkFrame(
            parent,
            fg_color=Theme.SURFACE,
            corner_radius=Theme.R_CARD,
            border_width=1,
            border_color=Theme.BORDER,
            **kwargs,
        )

    def _pill(self, parent, text, fg, text_color, width=56):
        return ctk.CTkLabel(
            parent,
            text=text,
            width=width,
            height=28,
            fg_color=fg,
            text_color=text_color,
            corner_radius=Theme.R_PILL,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_LABEL, weight="bold"),
        )

    def _ghost_button(self, parent, text, command, width=120):
        """Low-emphasis action: outline only until hovered."""
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=36,
            fg_color="transparent",
            hover_color=Theme.SURFACE_HOVER,
            text_color=Theme.TEXT_DIM,
            border_width=1,
            border_color=Theme.BORDER_STRONG,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_LABEL, weight="bold"),
        )

    # -- top bar ----------------------------------------------------------

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        bar.pack(fill="x", padx=20, pady=(14, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar,
            text="🔓",
            width=40,
            height=40,
            fg_color=Theme.ACCENT_SOFT,
            corner_radius=12,
            font=ctk.CTkFont(size=19),
        ).pack(side="left")

        titles = ctk.CTkFrame(bar, fg_color="transparent")
        titles.pack(side="left", padx=(12, 0))

        ctk.CTkLabel(
            titles,
            text="Unlocker",
            text_color=Theme.TEXT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_DISPLAY, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            titles,
            text="Strip passwords off your PDFs, in bulk",
            text_color=Theme.TEXT_FAINT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
        ).pack(anchor="w")

        self.btn_theme = ctk.CTkButton(
            bar,
            text="☾" if ctk.get_appearance_mode() == "Dark" else "☀",
            command=self._toggle_theme,
            width=38,
            height=38,
            fg_color=Theme.SURFACE,
            hover_color=Theme.SURFACE_HOVER,
            text_color=Theme.TEXT_DIM,
            border_width=1,
            border_color=Theme.BORDER,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(size=15),
        )
        self.btn_theme.pack(side="right")

        ctk.CTkLabel(
            bar,
            text=f"v{__version__}",
            text_color=Theme.TEXT_FAINT,
            font=ctk.CTkFont(Theme.MONO, Theme.SIZE_MICRO),
        ).pack(side="right", padx=(0, 12))

    # -- main card: switcher over one tall list ---------------------------

    def _build_main_card(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True, pady=(0, Theme.GAP))
        self.main_card = card

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Theme.PAD_CARD, pady=Theme.PAD_CARD)

        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x", pady=(0, 11))

        self.view_switch = ctk.CTkSegmentedButton(
            head,
            values=[VIEW_FILES, VIEW_RESULTS],
            command=self._switch_view,
            height=32,
            corner_radius=Theme.R_CTRL,
            fg_color=Theme.SURFACE_ALT,
            # CTkSegmentedButton has a single text_color for selected and
            # unselected alike, so a solid accent fill would force white text
            # onto the light unselected segment and make it unreadable. An
            # accent tint keeps the purple identity at readable contrast in
            # both themes.
            selected_color=Theme.ACCENT_SOFT,
            selected_hover_color=Theme.ACCENT_SOFT,
            unselected_color=Theme.SURFACE_ALT,
            unselected_hover_color=Theme.SURFACE_HOVER,
            text_color=Theme.TEXT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_LABEL, weight="bold"),
        )
        self.view_switch.set(VIEW_FILES)
        self.view_switch.pack(side="left")

        # Counters live in the header so a run can be watched from either tab.
        badges = ctk.CTkFrame(head, fg_color="transparent")
        badges.pack(side="right")

        self.file_count = self._pill(
            badges, "0 files", Theme.NEUTRAL_SOFT, Theme.TEXT_DIM, width=74
        )
        self.file_count.pack(side="left", padx=(0, 8))

        # Three zeroed pills before the first run are just noise, so the group
        # stays out of the header until a batch produces something.
        self.stat_group = ctk.CTkFrame(badges, fg_color="transparent")
        self.stat_success = self._pill(self.stat_group, "✓ 0", Theme.OK_SOFT, Theme.OK)
        self.stat_success.pack(side="left", padx=(0, 5))
        self.stat_failed = self._pill(self.stat_group, "✕ 0", Theme.BAD_SOFT, Theme.BAD)
        self.stat_failed.pack(side="left", padx=(0, 5))
        self.stat_skipped = self._pill(
            self.stat_group, "⊘ 0", Theme.NEUTRAL_SOFT, Theme.TEXT_DIM
        )
        self.stat_skipped.pack(side="left")

        # Both views share one bounded holder, so switching cannot resize the
        # card and shuffle everything below it.
        holder = ctk.CTkFrame(inner, fg_color="transparent", height=LIST_HEIGHT)
        holder.pack(fill="both", expand=True, pady=(0, 11))
        holder.pack_propagate(False)

        self.view_files = ctk.CTkFrame(holder, fg_color="transparent")
        self.file_scroll = ctk.CTkScrollableFrame(
            self.view_files,
            fg_color=Theme.SURFACE_ALT,
            corner_radius=Theme.R_CTRL,
            border_width=2,
            border_color=Theme.BORDER,
        )
        self.file_scroll.pack(fill="both", expand=True)

        self.view_results = ctk.CTkFrame(holder, fg_color="transparent")
        self.results_scroll = ctk.CTkScrollableFrame(
            self.view_results,
            fg_color=Theme.SURFACE_ALT,
            corner_radius=Theme.R_CTRL,
            border_width=2,
            border_color=Theme.BORDER,
        )
        self.results_scroll.pack(fill="both", expand=True)

        # Footers swap with the view: each tab offers only its own actions.
        self.footer = ctk.CTkFrame(inner, fg_color="transparent", height=38)
        self.footer.pack(fill="x")
        self.footer.pack_propagate(False)

        self.footer_files = ctk.CTkFrame(self.footer, fg_color="transparent")
        self.btn_add_files = ctk.CTkButton(
            self.footer_files,
            text="+  Files",
            command=self._browse_files,
            width=112,
            height=38,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_ON_ACCENT,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_BODY, weight="bold"),
        )
        self.btn_add_files.pack(side="left")

        self.btn_add_folder = self._ghost_button(
            self.footer_files, "+  Folder", self._browse_folder, width=112
        )
        self.btn_add_folder.pack(side="left", padx=(10, 0))

        self.btn_clear = ctk.CTkButton(
            self.footer_files,
            text="Clear",
            command=self._clear_files,
            width=76,
            height=38,
            fg_color="transparent",
            hover_color=Theme.BAD_SOFT,
            text_color=Theme.TEXT_DIM,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_LABEL, weight="bold"),
        )
        self.btn_clear.pack(side="right")

        self.footer_results = ctk.CTkFrame(self.footer, fg_color="transparent")
        self.btn_open_folder = self._ghost_button(
            self.footer_results, "Open folder", self._open_folder, width=124
        )
        self.btn_open_folder.configure(state="disabled")
        self.btn_open_folder.pack(side="left")

        self.btn_export = self._ghost_button(
            self.footer_results, "Export CSV", self._export_results, width=118
        )
        self.btn_export.configure(state="disabled")
        self.btn_export.pack(side="left", padx=(10, 0))

        self._render_files()
        self._render_results_empty()

    def _show_stat_pills(self, visible: bool):
        """Reveal or hide the per-status counters."""
        if visible:
            self.stat_group.pack(side="left")
        else:
            self.stat_group.pack_forget()

    def _switch_view(self, view: str):
        """Show one view and its footer, hide the other."""
        if view == VIEW_RESULTS:
            self.view_files.pack_forget()
            self.footer_files.pack_forget()
            self.view_results.pack(fill="both", expand=True)
            self.footer_results.pack(fill="x")
        else:
            self.view_results.pack_forget()
            self.footer_results.pack_forget()
            self.view_files.pack(fill="both", expand=True)
            self.footer_files.pack(fill="x")
        if self.view_switch.get() != view:
            self.view_switch.set(view)

    # -- files view -------------------------------------------------------

    def _render_files(self):
        """Rebuild the file rows from selected_files."""
        for child in self.file_scroll.winfo_children():
            child.destroy()
        self._file_row_buttons.clear()

        if not self.selected_files:
            empty = ctk.CTkFrame(self.file_scroll, fg_color="transparent")
            empty.pack(expand=True, pady=34)
            ctk.CTkLabel(
                empty, text="📄", font=ctk.CTkFont(size=32),
                text_color=Theme.TEXT_FAINT,
            ).pack()
            ctk.CTkLabel(
                empty,
                text=(
                    "Drop PDFs here" if self.dnd_ready
                    else "Add PDFs with the buttons below"
                ),
                text_color=Theme.TEXT_DIM,
                font=ctk.CTkFont(Theme.FONT, Theme.SIZE_BODY, weight="bold"),
            ).pack(pady=(10, 3))
            ctk.CTkLabel(
                empty,
                text="whole folders work too",
                text_color=Theme.TEXT_FAINT,
                font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
            ).pack()
            self.file_count.configure(
                text="0 files", fg_color=Theme.NEUTRAL_SOFT,
                text_color=Theme.TEXT_DIM,
            )
            return

        for path in self.selected_files[:MAX_FILE_ROWS]:
            self._file_row(path)

        hidden = len(self.selected_files) - MAX_FILE_ROWS
        if hidden > 0:
            ctk.CTkLabel(
                self.file_scroll,
                text=f"+ {hidden} more not shown",
                text_color=Theme.TEXT_FAINT,
                font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
            ).pack(pady=8)

        count = len(self.selected_files)
        self.file_count.configure(
            text=f"{count} file{'s' if count != 1 else ''}",
            fg_color=Theme.ACCENT_SOFT,
            text_color=Theme.ACCENT,
        )

    def _file_row(self, path: str):
        row = ctk.CTkFrame(self.file_scroll, fg_color="transparent", height=30)
        row.pack(fill="x", pady=1, padx=2)

        ctk.CTkLabel(
            row, text="📄", width=22, font=ctk.CTkFont(size=12)
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text=ellipsize(os.path.basename(path)),
            anchor="w",
            text_color=Theme.TEXT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_LABEL),
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            row,
            text=human_size(path),
            width=62,
            anchor="e",
            text_color=Theme.TEXT_FAINT,
            font=ctk.CTkFont(Theme.MONO, Theme.SIZE_MICRO),
        ).pack(side="left", padx=(0, 6))

        # Removing one wrong file used to mean clearing the whole selection.
        remove = ctk.CTkButton(
            row,
            text="✕",
            width=26,
            height=26,
            command=lambda p=path: self._remove_file(p),
            fg_color="transparent",
            hover_color=Theme.BAD_SOFT,
            text_color=Theme.TEXT_FAINT,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(size=11),
        )
        remove.pack(side="right")
        self._file_row_buttons.append(remove)

        # A row covers the list underneath it, so without its own target a
        # drop onto an existing row would be refused.
        self._register_drop_target(row)

    # -- results view -----------------------------------------------------

    def _render_results_empty(self):
        """Placeholder shown until the first result arrives."""
        self.results_empty = ctk.CTkLabel(
            self.results_scroll,
            text="Run a batch and the outcome per file shows up here",
            text_color=Theme.TEXT_FAINT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
        )
        self.results_empty.pack(pady=40)

    def _clear_results_empty(self):
        """Drop the placeholder so it cannot sit above the real rows."""
        if self.results_empty is not None:
            self.results_empty.destroy()
            self.results_empty = None

    def _result_row(self, result: UnlockResult):
        row = ctk.CTkFrame(self.results_scroll, fg_color="transparent", height=30)
        row.pack(fill="x", pady=1, padx=2)

        if result.status == Status.SUCCESS:
            glyph, tone, soft = "✓", Theme.OK, Theme.OK_SOFT
            detail = result.password_label
        elif result.status == Status.SKIPPED:
            glyph, tone, soft = "⊘", Theme.TEXT_DIM, Theme.NEUTRAL_SOFT
            detail = result.error_message or "skipped"
        else:
            glyph, tone, soft = "✕", Theme.BAD, Theme.BAD_SOFT
            detail = result.error_message or "failed"

        ctk.CTkLabel(
            row, text=glyph, width=24, height=22, fg_color=soft, text_color=tone,
            corner_radius=6, font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text=ellipsize(result.filename, 32),
            anchor="w",
            text_color=Theme.TEXT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_LABEL),
        ).pack(side="left", fill="x", expand=True, padx=(8, 8))

        # A position such as "password #2", never the secret itself.
        ctk.CTkLabel(
            row,
            text=truncate(detail, 34),
            anchor="e",
            text_color=Theme.TEXT_FAINT,
            font=ctk.CTkFont(Theme.MONO, Theme.SIZE_MICRO),
        ).pack(side="right")

    # -- password ---------------------------------------------------------

    def _build_key_card(self, parent):
        card = self._card(parent)
        card.pack(fill="x", pady=(0, Theme.GAP))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=Theme.PAD_CARD, pady=Theme.PAD_CARD)

        self.remember_var = ctk.BooleanVar(value=False)

        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x", pady=(0, 9))

        ctk.CTkLabel(
            head,
            text="Passwords",
            text_color=Theme.TEXT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_TITLE, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            head,
            text="comma-separated, tried in order",
            text_color=Theme.TEXT_FAINT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
        ).pack(side="left", padx=(10, 0))

        field = ctk.CTkFrame(inner, fg_color="transparent")
        field.pack(fill="x")

        # A real Entry with show= masks natively: the field stays clickable and
        # editable either way, and get() returns the actual text, so no shadow
        # copy can drift out of sync.
        #
        # Deliberately no placeholder_text: CustomTkinter clears show= to make a
        # placeholder readable and restores the old value afterwards, which
        # would silently revert the eye toggle on an empty field.
        self.password_input = ctk.CTkEntry(
            field,
            height=40,
            show=Theme.MASK_CHAR,
            fg_color=Theme.SURFACE_ALT,
            text_color=Theme.TEXT,
            border_width=1,
            border_color=Theme.BORDER,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(Theme.MONO, Theme.SIZE_BODY),
        )
        self.password_input.pack(side="left", fill="x", expand=True)
        self.password_input.bind("<Return>", self._on_password_enter)
        self.password_input.bind("<FocusIn>", self._on_password_focus)
        self.password_input.bind("<FocusOut>", self._on_password_blur)

        self.btn_toggle = ctk.CTkButton(
            field,
            text="👁",
            command=self._toggle_password,
            width=42,
            height=40,
            fg_color=Theme.SURFACE_ALT,
            hover_color=Theme.SURFACE_HOVER,
            text_color=Theme.TEXT_DIM,
            border_width=1,
            border_color=Theme.BORDER,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(size=14),
        )
        self.btn_toggle.pack(side="left", padx=(8, 0))

        self.remember_check = ctk.CTkCheckBox(
            inner,
            text="Remember in the OS credential store",
            variable=self.remember_var,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=6,
            border_width=2,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            border_color=Theme.BORDER_STRONG,
            text_color=Theme.TEXT_DIM,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
            state="normal" if self.keyring_available else "disabled",
        )
        self.remember_check.pack(anchor="w", pady=(11, 0))

    def _on_password_focus(self, _e):
        self.password_input.configure(border_color=Theme.ACCENT)

    def _on_password_blur(self, _e):
        self.password_input.configure(border_color=Theme.BORDER)

    # -- action -----------------------------------------------------------

    def _build_action_row(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="x", pady=(0, 14))

        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")

        self.btn_unlock = ctk.CTkButton(
            row,
            text="Unlock",
            command=self._try_start,
            height=46,
            fg_color=Theme.NEUTRAL_SOFT,
            hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT_FAINT,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_TITLE, weight="bold"),
            state="disabled",
        )
        self.btn_unlock.pack(side="left", fill="x", expand=True)

        self.btn_cancel = ctk.CTkButton(
            row,
            text="Stop",
            command=self._cancel,
            width=92,
            height=46,
            fg_color="transparent",
            hover_color=Theme.BAD_SOFT,
            text_color=Theme.TEXT_FAINT,
            border_width=1,
            border_color=Theme.BORDER,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_BODY, weight="bold"),
            state="disabled",
        )
        self.btn_cancel.pack(side="left", padx=(10, 0))

        self.progress_bar = ctk.CTkProgressBar(
            wrap,
            height=6,
            corner_radius=3,
            fg_color=Theme.NEUTRAL_SOFT,
            progress_color=Theme.ACCENT,
        )
        self.progress_bar.pack(fill="x", pady=(10, 0))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            wrap,
            text="Ready when you are",
            text_color=Theme.TEXT_FAINT,
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
        )
        self.status_label.pack(anchor="w", pady=(6, 0))

    # -- toast ------------------------------------------------------------

    def _build_toast(self):
        """Floating feedback strip, absent from the layout until it has news."""
        self.toast = ctk.CTkFrame(
            self,
            fg_color=Theme.NEUTRAL_SOFT,
            corner_radius=Theme.R_CTRL,
            height=44,
            border_width=1,
            border_color=Theme.BORDER,
        )
        self.toast_label = ctk.CTkLabel(
            self.toast,
            text="",
            text_color=Theme.TEXT,
            anchor="w",
            font=ctk.CTkFont(Theme.FONT, Theme.SIZE_LABEL, weight="bold"),
        )
        self.toast_label.pack(side="left", padx=(14, 10), pady=11)

        ctk.CTkButton(
            self.toast,
            text="✕",
            width=26,
            height=26,
            command=self._hide_toast,
            fg_color="transparent",
            hover_color=Theme.SURFACE_HOVER,
            text_color=Theme.TEXT_DIM,
            corner_radius=Theme.R_CTRL,
            font=ctk.CTkFont(size=11),
        ).pack(side="right", padx=(0, 9))

    def _toast_message(self, text: str, kind: str = "info", sticky: bool = False):
        """Show an inline message. kind: info | ok | warn | bad."""
        palette = {
            "info": (Theme.NEUTRAL_SOFT, Theme.TEXT),
            "ok": (Theme.OK_SOFT, Theme.OK),
            "warn": (Theme.WARN_SOFT, Theme.WARN),
            "bad": (Theme.BAD_SOFT, Theme.BAD),
        }
        fg, tone = palette.get(kind, palette["info"])
        self.toast.configure(fg_color=fg)
        self.toast_label.configure(text=text, text_color=tone)
        # Parked over the progress area at the very bottom, clear of the card
        # footer: a sticky error toast covering Export CSV would block it.
        self.toast.place(relx=0.5, rely=1.0, y=-8, anchor="s", relwidth=0.88)
        self.toast.lift()

        if self._toast_timer is not None:
            self.after_cancel(self._toast_timer)
            self._toast_timer = None
        if not sticky:
            self._toast_timer = self.after(TOAST_DURATION_MS, self._hide_toast)

    def _hide_toast(self):
        if self._toast_timer is not None:
            self.after_cancel(self._toast_timer)
            self._toast_timer = None
        self.toast.place_forget()

    # =====================================================================
    # THEME
    # =====================================================================

    def _toggle_theme(self):
        """Flip light/dark. Tuple tokens mean widgets repaint themselves."""
        mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(mode)
        self.btn_theme.configure(text="☾" if mode == "dark" else "☀")
        self.config["appearance_mode"] = mode
        self.config_manager.save_config(self.config)

    # =====================================================================
    # DRAG AND DROP
    # =====================================================================

    def _load_tkdnd(self) -> bool:
        """Load the tkdnd Tcl package into this interpreter.

        tkinterdnd2 normally does this from TkinterDnD.Tk.__init__, which we
        never call because the root is a ctk.CTk. Without it every
        drop_target_register raises TclError: invalid command name
        "tkdnd::drop_target" and drag-and-drop silently does nothing.
        """
        if not DRAG_DROP_AVAILABLE:
            self.logger.warning("tkinterdnd2 not installed - drops disabled")
            return False
        try:
            TkinterDnD._require(self)
            return True
        except Exception as e:
            self.logger.warning(f"Could not load tkdnd - drops disabled: {e}")
            return False

    def _register_drop_target(self, widget) -> bool:
        """Make one widget accept file drops. Returns whether it took."""
        if not self.dnd_ready:
            return False
        # The Tk root is not a BaseWidget, so tkinterdnd2 never patches these
        # methods onto it. Check rather than assume, and keep going either way.
        if not hasattr(widget, "drop_target_register"):
            return False
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            widget.dnd_bind("<<DragLeave>>", self._on_drag_leave)
            return True
        except Exception as e:
            self.logger.warning(f"Drop target registration failed: {e}")
            return False

    def _setup_dnd(self):
        """Accept drops across the window, not only on the list itself."""
        if not self.dnd_ready:
            return

        registered = sum(
            self._register_drop_target(w)
            for w in (
                self.body,
                self.main_card,
                self.file_scroll,
                self.file_scroll._parent_canvas,
                self.results_scroll,
                self.results_scroll._parent_canvas,
            )
        )
        if registered:
            self.logger.info(f"Drag-and-drop registered on {registered} targets")
        else:
            # Nothing took, so the feature is dead. Say so rather than leave
            # the UI advertising a drop zone that ignores drops.
            self.dnd_ready = False
            self.logger.error("Drag-and-drop registration failed on every target")
            self._toast_message("Drag and drop unavailable, use + Files", "warn")

    def _on_drag_enter(self, _e):
        self.file_scroll.configure(border_color=Theme.ACCENT)

    def _on_drag_leave(self, _e):
        self.file_scroll.configure(border_color=Theme.BORDER)

    def _on_drop(self, e):
        self.file_scroll.configure(border_color=Theme.BORDER)

        if self.is_processing:
            self._toast_message("Busy unlocking, try again when it finishes", "warn")
            return e.action

        before = len(self.selected_files)
        for raw in self._parse_drop_data(e.data):
            path = raw.strip()
            if os.path.isdir(path):
                self._add_pdfs_from_folder(path)
            elif (
                os.path.isfile(path)
                and is_pdf(path)
                and path not in self.selected_files
            ):
                self.selected_files.append(path)

        added = len(self.selected_files) - before
        self._refresh_files()
        # Dropping is about the file list, so show it whatever tab was open.
        self._switch_view(VIEW_FILES)
        if added:
            self._toast_message(f"Added {added} PDF{'s' if added != 1 else ''}", "ok")
        else:
            self._toast_message("No new PDFs in that drop", "warn")
        return e.action

    def _parse_drop_data(self, data: str) -> list[str]:
        """Split a drop payload into paths.

        Tk hands over a Tcl list where only paths containing spaces are
        brace-wrapped. Letting Tcl split it handles a mixed payload that a
        regex-or-whitespace split drops half of.
        """
        try:
            paths = [str(item) for item in self.tk.splitlist(data)]
        except Exception:
            self.logger.warning("Could not parse drop payload, falling back")
            paths = data.split()
        return [
            p[len("file://"):] if p.startswith("file://") else p for p in paths
        ]

    # =====================================================================
    # FILES
    # =====================================================================

    def _add_pdfs_from_folder(self, folder: str):
        """Add every PDF under folder, skipping our own output folder."""
        for path in find_pdfs(folder):
            if path not in self.selected_files:
                self.selected_files.append(path)

    def _refresh_files(self):
        self._render_files()
        self._update_unlock_state()

    def _browse_files(self):
        if self.is_processing:
            return
        initial = self.config.get("last_input_folder", os.path.expanduser("~"))
        files = filedialog.askopenfilenames(
            title="Pick PDFs",
            initialdir=initial,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not files:
            return
        self.config["last_input_folder"] = os.path.dirname(files[0])
        self.config_manager.save_config(self.config)
        added = 0
        for f in files:
            if f not in self.selected_files:
                self.selected_files.append(f)
                added += 1
        self._refresh_files()
        self._switch_view(VIEW_FILES)
        if added:
            self._toast_message(f"Added {added} PDF{'s' if added != 1 else ''}", "ok")

    def _browse_folder(self):
        if self.is_processing:
            return
        initial = self.config.get("last_input_folder", os.path.expanduser("~"))
        folder = filedialog.askdirectory(title="Pick a folder", initialdir=initial)
        if not folder:
            return
        self.config["last_input_folder"] = folder
        self.config_manager.save_config(self.config)
        before = len(self.selected_files)
        self._add_pdfs_from_folder(folder)
        added = len(self.selected_files) - before
        self._refresh_files()
        self._switch_view(VIEW_FILES)
        if added:
            self._toast_message(f"Found {added} PDF{'s' if added != 1 else ''}", "ok")
        else:
            self._toast_message("No PDFs in that folder", "warn")

    def _remove_file(self, path: str):
        if self.is_processing:
            return
        if path in self.selected_files:
            self.selected_files.remove(path)
        self._refresh_files()

    def _clear_files(self):
        if self.is_processing or not self.selected_files:
            return
        self.selected_files.clear()
        self._refresh_files()

    def _update_unlock_state(self):
        """Keep the primary button honest about what it will do.

        A disabled CTkButton keeps its fill and only dims the label, so a full
        accent button would still invite a click that does nothing. The fill
        goes flat whenever the button is not actionable.
        """
        count = len(self.selected_files)
        if self.is_processing:
            label, enabled = "Unlocking…", False
        elif count:
            label = f"Unlock {count} file{'s' if count != 1 else ''}"
            enabled = True
        else:
            label, enabled = "Unlock", False

        self.btn_unlock.configure(
            text=label,
            state="normal" if enabled else "disabled",
            fg_color=Theme.ACCENT if enabled else Theme.NEUTRAL_SOFT,
            text_color=Theme.TEXT_ON_ACCENT if enabled else Theme.TEXT_FAINT,
        )

    # =====================================================================
    # PASSWORDS
    # =====================================================================

    def _toggle_password(self):
        """Show or hide the password text.

        Only the show option changes, so the field stays editable and its
        contents are never rewritten.
        """
        self.password_visible = not self.password_visible
        self.password_input.configure(
            show="" if self.password_visible else Theme.MASK_CHAR
        )
        self.btn_toggle.configure(text="🙈" if self.password_visible else "👁")

    def _on_password_enter(self, _event):
        self._try_start()
        return "break"

    def _get_passwords(self) -> list[str]:
        """Return the entered passwords, in the order given."""
        text = self.password_input.get().strip()
        if not text:
            return []
        # Deduplicate but keep order: a repeat only costs another attempt.
        seen = set()
        passwords = []
        for candidate in text.split(","):
            candidate = candidate.strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                passwords.append(candidate)
        return passwords

    def _set_passwords(self, passwords: list[str]):
        """Populate the password field from a stored list."""
        self.password_input.delete(0, "end")
        self.password_input.insert(0, ", ".join(passwords))

    def _load_saved_data(self):
        if self.config.get("remember_passwords", False) and self.keyring_available:
            saved = PasswordManager.load_passwords()
            if saved:
                self._set_passwords(saved)
                self.remember_var.set(True)

    # =====================================================================
    # PROCESSING
    # =====================================================================

    def _try_start(self):
        """Validate inline, then run. No modal gatekeeping."""
        if self.is_processing:
            return
        if not self.selected_files:
            self._toast_message("Add some PDFs first", "warn")
            self._switch_view(VIEW_FILES)
            return

        passwords = self._get_passwords()
        if not passwords:
            self._toast_message("Enter at least one password", "warn")
            self.password_input.configure(border_color=Theme.BAD)
            self.password_input.focus_set()
            self.after(
                1200,
                lambda: self.password_input.configure(border_color=Theme.BORDER),
            )
            return

        missing = [f for f in self.selected_files if not os.path.exists(f)]
        if missing:
            self._toast_message(
                f"{len(missing)} file{'s' if len(missing) != 1 else ''} went missing",
                "bad",
            )
            return

        self._start_unlock(passwords)

    def _start_unlock(self, passwords: list[str]):
        if self.remember_var.get() and self.keyring_available:
            PasswordManager.save_passwords(passwords)
            self.config["remember_passwords"] = True
        else:
            if self.keyring_available:
                PasswordManager.clear_passwords()
            self.config["remember_passwords"] = False
        self.config_manager.save_config(self.config)

        # Reset the run view
        self.results.clear()
        self.output_folders.clear()
        self.output_folder = None
        self._result_rows = 0
        for child in self.results_scroll.winfo_children():
            child.destroy()
        self.results_empty = None
        self._render_results_empty()
        self.stat_success.configure(text="✓ 0")
        self.stat_failed.configure(text="✕ 0")
        self.stat_skipped.configure(text="⊘ 0")
        self._show_stat_pills(True)
        self.progress_bar.set(0)
        self._hide_toast()

        self.is_processing = True
        self._set_ui_processing(True)
        # The interesting view during a run is the one filling up.
        self._switch_view(VIEW_RESULTS)
        self.status_label.configure(
            text=f"Working through {len(self.selected_files)} files…",
            text_color=Theme.ACCENT,
        )

        self.result_queue = queue.Queue()
        # Pass a copy: the worker must not see the selection change under it.
        threading.Thread(
            target=self.processor.process_batch,
            args=(list(self.selected_files), passwords, self.result_queue),
            daemon=True,
        ).start()
        self._poll_queue()

    def _cancel(self):
        if not self.is_processing:
            return
        self.processor.cancel_processing()
        self.status_label.configure(text="Stopping…", text_color=Theme.BAD)
        self.btn_cancel.configure(state="disabled")

    def _set_ui_processing(self, processing: bool):
        """Enable or disable every control for the given run state.

        Each widget is listed with the condition that enables it when idle, so
        the whole lockout is readable in one place.
        """
        idle_rules = (
            (self.btn_add_files, True),
            (self.btn_add_folder, True),
            (self.btn_clear, True),
            (self.btn_export, bool(self.results)),
            (self.btn_open_folder, bool(self.output_folder)),
            (self.password_input, True),
            (self.btn_toggle, True),
            (self.remember_check, self.keyring_available),
        )
        for widget, enabled_when_idle in idle_rules:
            widget.configure(
                state="normal" if (not processing and enabled_when_idle) else "disabled"
            )

        for button in self._file_row_buttons:
            # A row may have been rebuilt underneath us; the fresh one starts
            # in the right state anyway.
            with contextlib.suppress(Exception):
                button.configure(state="disabled" if processing else "normal")

        # Stop is the one control that is only live while work is running,
        # and it should not look armed the rest of the time.
        self.btn_cancel.configure(
            state="normal" if processing else "disabled",
            border_color=Theme.BAD if processing else Theme.BORDER,
            text_color=Theme.BAD if processing else Theme.TEXT_FAINT,
        )
        self._update_unlock_state()

    def _poll_queue(self):
        """Drain worker messages, then reschedule.

        The reschedule lives in finally. Without it, one raising message would
        stop polling for good and strand the window in its processing state
        with every control disabled.
        """
        finished = False
        try:
            while True:
                msg = self.result_queue.get_nowait()
                if msg.type == MessageType.PROGRESS:
                    self._show_progress(msg.data)
                elif msg.type == MessageType.RESULT:
                    self._add_result(msg.data)
                elif msg.type == MessageType.COMPLETE:
                    finished = True
                    self._on_complete(msg.data)
                    break
        except queue.Empty:
            pass
        except Exception:
            self.logger.exception("Error handling a worker message")
        finally:
            if not finished and self.is_processing:
                self.after(100, self._poll_queue)

    def _show_progress(self, d: dict):
        total = d.get("total") or 1
        self.progress_bar.set(d["current"] / total)
        eta = d.get("eta", "")
        text = f"{d['current']} of {d['total']} done"
        if eta and eta != "Calculating...":
            text += f"  ·  {eta} left"
        self.status_label.configure(text=text, text_color=Theme.ACCENT)

    def _add_result(self, result: UnlockResult):
        self._clear_results_empty()
        # Hold the invariant here too, not only in _start_unlock: if there are
        # results, the counters are showing.
        self._show_stat_pills(True)
        self.results.append(result)
        if result.output_path:
            self.output_folder = os.path.dirname(result.output_path)
            if self.output_folder not in self.output_folders:
                self.output_folders.append(self.output_folder)

        success = sum(1 for r in self.results if r.status == Status.SUCCESS)
        skipped = sum(1 for r in self.results if r.status == Status.SKIPPED)
        failed = len(self.results) - success - skipped
        self.stat_success.configure(text=f"✓ {success}")
        self.stat_failed.configure(text=f"✕ {failed}")
        self.stat_skipped.configure(text=f"⊘ {skipped}")

        if self._result_rows < MAX_RESULT_ROWS:
            self._result_row(result)
            self._result_rows += 1
        elif self._result_rows == MAX_RESULT_ROWS:
            ctk.CTkLabel(
                self.results_scroll,
                text="Further rows omitted, export the CSV for the full list",
                text_color=Theme.TEXT_FAINT,
                font=ctk.CTkFont(Theme.FONT, Theme.SIZE_MICRO),
            ).pack(pady=8)
            self._result_rows += 1

    def _on_complete(self, data: dict):
        self.is_processing = False
        self._set_ui_processing(False)
        self.progress_bar.set(1)

        total = data["total"]
        success = data["success"]
        skipped = data.get("skipped", 0)
        failed = data.get("fail", 0)
        cancelled = data.get("cancelled", False)
        error = data.get("error")

        bits = [f"{success} of {total} unlocked"]
        if skipped:
            bits.append(f"{skipped} skipped")
        if failed:
            bits.append(f"{failed} failed")
        summary = "  ·  ".join(bits)

        if error:
            self.status_label.configure(text="Stopped early", text_color=Theme.BAD)
            self._toast_message(f"Stopped: {error}", "bad", sticky=True)
        elif cancelled:
            self.status_label.configure(text=summary, text_color=Theme.TEXT_DIM)
            self._toast_message(f"Stopped, {summary}", "warn")
        elif failed:
            self.status_label.configure(text=summary, text_color=Theme.TEXT_DIM)
            self._toast_message(summary, "warn")
        else:
            self.status_label.configure(text=summary, text_color=Theme.OK)
            self._toast_message(f"Done, {summary}", "ok")

    # =====================================================================
    # OUTPUT
    # =====================================================================

    def _open_folder(self):
        if not self.output_folder or not os.path.exists(self.output_folder):
            self._toast_message("No output folder yet", "warn")
            return
        if len(self.output_folders) > 1:
            self._toast_message(
                f"Output went to {len(self.output_folders)} folders, "
                "opening the last one",
                "info",
            )
        try:
            if sys.platform == "win32":
                os.startfile(self.output_folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", self.output_folder], check=False)
            else:
                subprocess.run(["xdg-open", self.output_folder], check=False)
        except OSError as e:
            self.logger.error(f"Could not open {self.output_folder}: {e}")
            self._toast_message("Could not open that folder", "bad")

    def _export_results(self):
        if not self.results:
            self._toast_message("Nothing to export yet", "warn")
            return
        initial = self.config.get("last_output_folder", os.path.expanduser("~"))
        path = filedialog.asksaveasfilename(
            title="Save report",
            initialdir=initial,
            initialfile=ResultsExporter.generate_filename(),
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        self.config["last_output_folder"] = os.path.dirname(path)
        self.config_manager.save_config(self.config)
        if ResultsExporter.export_to_csv(self.results, path):
            self._toast_message(f"Saved {os.path.basename(path)}", "ok")
        else:
            self._toast_message("Export failed, check the log", "bad")

    def _on_close(self):
        # A real decision with consequences, so this one stays a dialog.
        if self.is_processing:
            if not messagebox.askyesno(
                "Still unlocking",
                "A batch is still running. Quit anyway?",
            ):
                return
            self.processor.cancel_processing()
        self.destroy()
