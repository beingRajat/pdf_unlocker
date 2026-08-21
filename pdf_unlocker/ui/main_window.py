"""
PDF Unlocker Pro - Premium UI with CustomTkinter
Inspired by Linear, Stripe, and Notion design systems.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional
import logging
import subprocess
import sys

import customtkinter as ctk

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False

from core.config_manager import ConfigManager
from core.password_manager import PasswordManager
from core.pdf_processor import PDFProcessor, UnlockResult, MessageType


# =============================================================================
# PREMIUM THEME - Inspired by Linear/Stripe
# =============================================================================

class Theme:
    """Premium design tokens with vibrant colors."""

    # Brand Colors (Linear-inspired purple gradient)
    BRAND_PRIMARY = "#5E5ADB"      # Indigo
    BRAND_SECONDARY = "#7C3AED"    # Purple
    BRAND_ACCENT = "#8B5CF6"       # Violet

    # Gradient colors for header
    GRADIENT_START = "#4F46E5"     # Indigo 600
    GRADIENT_END = "#7C3AED"       # Purple 600

    # Action Colors (Vibrant)
    SUCCESS = "#10B981"            # Emerald
    SUCCESS_HOVER = "#059669"
    SUCCESS_LIGHT = "#D1FAE5"

    ERROR = "#EF4444"              # Red
    ERROR_HOVER = "#DC2626"
    ERROR_LIGHT = "#FEE2E2"

    WARNING = "#F59E0B"            # Amber
    WARNING_LIGHT = "#FEF3C7"

    INFO = "#3B82F6"               # Blue
    INFO_LIGHT = "#DBEAFE"

    # Primary Button
    PRIMARY = "#5E5ADB"
    PRIMARY_HOVER = "#4F46E5"

    # Secondary/Neutral
    SECONDARY = "#6366F1"          # Indigo 500
    SECONDARY_HOVER = "#4F46E5"

    # Backgrounds
    BG_DARK = "#0F0E17"            # Near black
    BG_PRIMARY = "#FFFFFE"         # Pure white
    BG_SECONDARY = "#F8F7FF"       # Slight purple tint
    BG_CARD = "#FFFFFF"
    BG_INPUT = "#F9FAFB"
    BG_HEADER = "#1E1B4B"          # Deep indigo

    # Text
    TEXT_PRIMARY = "#1F2937"       # Gray 800
    TEXT_SECONDARY = "#6B7280"     # Gray 500
    TEXT_MUTED = "#9CA3AF"         # Gray 400
    TEXT_ON_DARK = "#F9FAFB"       # Almost white
    TEXT_ON_BRAND = "#FFFFFF"

    # Borders
    BORDER = "#E5E7EB"             # Gray 200
    BORDER_FOCUS = "#5E5ADB"       # Brand

    # Shadows (for reference)
    SHADOW_SM = "0 1px 2px rgba(0,0,0,0.05)"
    SHADOW_MD = "0 4px 6px rgba(0,0,0,0.1)"

    # Fonts
    FONT_FAMILY = "Segoe UI"
    FONT_MONO = "Consolas"

    # Accent colors for file types
    ACCENT_PDF = "#EF4444"         # Red for PDF
    ACCENT_LOCK = "#F59E0B"        # Amber for lock
    ACCENT_UNLOCK = "#10B981"      # Green for unlock


# Configure CustomTkinter
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# =============================================================================
# MAIN WINDOW
# =============================================================================

class MainWindow(ctk.CTk):
    """Premium PDF Unlocker with modern UI."""

    def __init__(self, config_manager: ConfigManager, logger: logging.Logger):
        super().__init__()

        self.config_manager = config_manager
        self.logger = logger
        self.config = config_manager.load_config()

        # State
        self.selected_files: List[str] = []
        self.results: List[UnlockResult] = []
        self.is_processing = False
        self.result_queue: Optional[queue.Queue] = None
        self.output_folder: Optional[str] = None

        # Password state
        self.password_visible = True
        self.stored_password = ""

        # Processor
        error_log = os.path.join(config_manager.get_config_dir(), "error_log.txt")
        self.processor = PDFProcessor(logger, error_log)
        self.keyring_available = PasswordManager.is_available()

        self._setup_window()
        self._build_ui()
        self._load_saved_data()
        self._setup_dnd()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self):
        """Configure window."""
        self.title("PDF Unlocker Pro")
        self.configure(fg_color=Theme.BG_SECONDARY)

        width, height = 650, 780
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(580, 700)

    def _build_ui(self):
        """Build premium UI."""
        # Header with gradient effect
        self._build_header()

        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=28, pady=(20, 28))

        # Sections
        self._build_file_section(content)
        self._build_password_section(content)
        self._build_action_section(content)
        self._build_results_section(content)

    def _build_header(self):
        """Build premium header with branding."""
        # Header container with brand color
        header = ctk.CTkFrame(
            self,
            fg_color=Theme.BG_HEADER,
            corner_radius=0,
            height=100
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        # Inner content
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=28, pady=20)

        # Left: Logo and title
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y")

        # Icon with gradient-like background
        icon_frame = ctk.CTkFrame(
            left,
            fg_color=Theme.BRAND_ACCENT,
            corner_radius=12,
            width=48,
            height=48
        )
        icon_frame.pack(side="left")
        icon_frame.pack_propagate(False)

        icon_label = ctk.CTkLabel(
            icon_frame,
            text="🔓",
            font=ctk.CTkFont(size=24),
            text_color=Theme.TEXT_ON_BRAND
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        # Title section
        title_frame = ctk.CTkFrame(left, fg_color="transparent")
        title_frame.pack(side="left", padx=(16, 0))

        title = ctk.CTkLabel(
            title_frame,
            text="PDF Unlocker Pro",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=22, weight="bold"),
            text_color=Theme.TEXT_ON_DARK
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_frame,
            text="Unlock password-protected PDFs instantly",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12),
            text_color=Theme.TEXT_MUTED
        )
        subtitle.pack(anchor="w")

        # Right: Version badge
        version_badge = ctk.CTkLabel(
            inner,
            text="✨ v1.0",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11, weight="bold"),
            text_color=Theme.BRAND_ACCENT,
            fg_color="#312E81",
            corner_radius=6,
            padx=12,
            pady=6
        )
        version_badge.pack(side="right")

    def _build_file_section(self, parent):
        """Build file selection with visual flair."""
        # Card with subtle shadow effect (border)
        card = ctk.CTkFrame(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=Theme.BORDER
        )
        card.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)

        # Header with icon
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))

        # Icon badge
        icon_badge = ctk.CTkLabel(
            header,
            text="📁",
            font=ctk.CTkFont(size=20),
            fg_color=Theme.INFO_LIGHT,
            corner_radius=8,
            width=40,
            height=40
        )
        icon_badge.pack(side="left")

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=(12, 0))

        title = ctk.CTkLabel(
            title_frame,
            text="Select PDF Files",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=15, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        title.pack(anchor="w")

        hint = ctk.CTkLabel(
            title_frame,
            text="Drag & drop files or browse",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11),
            text_color=Theme.TEXT_MUTED
        )
        hint.pack(anchor="w")

        # Count badge
        self.file_count_badge = ctk.CTkLabel(
            header,
            text="0 files",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11, weight="bold"),
            text_color=Theme.TEXT_MUTED,
            fg_color=Theme.BG_INPUT,
            corner_radius=6,
            padx=12,
            pady=6
        )
        self.file_count_badge.pack(side="right")

        # Drop zone with dashed border effect
        self.drop_zone = ctk.CTkFrame(
            inner,
            fg_color=Theme.BG_INPUT,
            corner_radius=10,
            border_width=2,
            border_color=Theme.BORDER
        )
        self.drop_zone.pack(fill="x", pady=(0, 14))

        # File list
        self.file_list = ctk.CTkTextbox(
            self.drop_zone,
            height=100,
            font=ctk.CTkFont(family=Theme.FONT_MONO, size=11),
            fg_color="transparent",
            text_color=Theme.TEXT_SECONDARY,
            border_width=0,
            corner_radius=8,
            state="disabled"
        )
        self.file_list.pack(fill="x", padx=12, pady=12)
        self._update_file_display()

        # Buttons with colors
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_browse_files = ctk.CTkButton(
            btn_row,
            text="📄 Browse Files",
            command=self._browse_files,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12, weight="bold"),
            height=38,
            corner_radius=8
        )
        self.btn_browse_files.pack(side="left", padx=(0, 10))

        self.btn_browse_folder = ctk.CTkButton(
            btn_row,
            text="📂 Browse Folder",
            command=self._browse_folder,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12, weight="bold"),
            height=38,
            corner_radius=8
        )
        self.btn_browse_folder.pack(side="left", padx=(0, 10))

        self.btn_clear = ctk.CTkButton(
            btn_row,
            text="✕ Clear",
            command=self._clear_files,
            fg_color="transparent",
            hover_color=Theme.ERROR_LIGHT,
            text_color=Theme.ERROR,
            border_width=1,
            border_color=Theme.ERROR,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12),
            height=38,
            width=90,
            corner_radius=8
        )
        self.btn_clear.pack(side="left")

    def _build_password_section(self, parent):
        """Build compact password section."""
        card = ctk.CTkFrame(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=Theme.BORDER
        )
        card.pack(fill="x", pady=(0, 16))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)

        # Header row with icon, title, and toggle button
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        # Left side: icon + title
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")

        icon_badge = ctk.CTkLabel(
            left,
            text="🔐",
            font=ctk.CTkFont(size=18),
            fg_color=Theme.WARNING_LIGHT,
            corner_radius=6,
            width=36,
            height=36
        )
        icon_badge.pack(side="left")

        title = ctk.CTkLabel(
            left,
            text="Passwords",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=14, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        title.pack(side="left", padx=(10, 0))

        hint = ctk.CTkLabel(
            left,
            text="(one per line or comma-separated)",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11),
            text_color=Theme.TEXT_MUTED
        )
        hint.pack(side="left", padx=(8, 0))

        # Right side: toggle button
        self.btn_toggle = ctk.CTkButton(
            header,
            text="👁",
            command=self._toggle_password,
            fg_color=Theme.BG_INPUT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=14),
            width=36,
            height=36,
            corner_radius=8,
            border_width=1,
            border_color=Theme.BORDER
        )
        self.btn_toggle.pack(side="right")

        # Password input - compact height
        self.password_input = ctk.CTkTextbox(
            inner,
            height=70,
            font=ctk.CTkFont(family=Theme.FONT_MONO, size=11),
            fg_color=Theme.BG_INPUT,
            text_color=Theme.TEXT_PRIMARY,
            border_width=1,
            border_color=Theme.BORDER,
            corner_radius=8
        )
        self.password_input.pack(fill="x", pady=(0, 10))
        self.password_input.bind("<Key>", self._on_password_key)
        self.password_input.bind("<FocusIn>", lambda e: self.password_input.configure(border_color=Theme.BRAND_PRIMARY))
        self.password_input.bind("<FocusOut>", lambda e: self.password_input.configure(border_color=Theme.BORDER))

        # Remember checkbox - inline
        self.remember_var = ctk.BooleanVar(value=False)
        self.remember_check = ctk.CTkCheckBox(
            inner,
            text="🔒 Remember securely",
            variable=self.remember_var,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=11),
            text_color=Theme.TEXT_SECONDARY,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            border_color=Theme.BORDER,
            checkbox_width=18,
            checkbox_height=18,
            state="normal" if self.keyring_available else "disabled"
        )
        self.remember_check.pack(anchor="w")

    def _build_action_section(self, parent):
        """Build action area with prominent buttons."""
        action = ctk.CTkFrame(parent, fg_color="transparent")
        action.pack(fill="x", pady=(0, 16))

        # Button row
        btn_row = ctk.CTkFrame(action, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 14))

        # Big unlock button with gradient-like effect
        self.btn_unlock = ctk.CTkButton(
            btn_row,
            text="🔓 Unlock PDFs",
            command=self._start_unlock,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=15, weight="bold"),
            height=50,
            corner_radius=10,
            state="disabled"
        )
        self.btn_unlock.pack(side="left", padx=(0, 12))

        # Cancel button
        self.btn_cancel = ctk.CTkButton(
            btn_row,
            text="Cancel",
            command=self._cancel,
            fg_color=Theme.ERROR,
            hover_color=Theme.ERROR_HOVER,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13, weight="bold"),
            height=50,
            width=100,
            corner_radius=10,
            state="disabled"
        )
        self.btn_cancel.pack(side="left")

        # Status with color
        self.status_label = ctk.CTkLabel(
            btn_row,
            text="⚡ Ready",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=13, weight="bold"),
            text_color=Theme.SUCCESS
        )
        self.status_label.pack(side="right")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            action,
            height=8,
            corner_radius=4,
            fg_color=Theme.BORDER,
            progress_color=Theme.SUCCESS
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

    def _build_results_section(self, parent):
        """Build results area."""
        card = ctk.CTkFrame(
            parent,
            fg_color=Theme.BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=Theme.BORDER
        )
        card.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))

        # Results icon
        icon_badge = ctk.CTkLabel(
            header,
            text="📊",
            font=ctk.CTkFont(size=20),
            fg_color=Theme.SUCCESS_LIGHT,
            corner_radius=8,
            width=40,
            height=40
        )
        icon_badge.pack(side="left")

        title = ctk.CTkLabel(
            header,
            text="Results",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=15, weight="bold"),
            text_color=Theme.TEXT_PRIMARY
        )
        title.pack(side="left", padx=(12, 0))

        # Stats
        stats = ctk.CTkFrame(header, fg_color="transparent")
        stats.pack(side="right")

        self.stat_success = ctk.CTkLabel(
            stats,
            text="✓ 0",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12, weight="bold"),
            text_color=Theme.SUCCESS,
            fg_color=Theme.SUCCESS_LIGHT,
            corner_radius=6,
            padx=14,
            pady=6
        )
        self.stat_success.pack(side="left", padx=(0, 8))

        self.stat_failed = ctk.CTkLabel(
            stats,
            text="✗ 0",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12, weight="bold"),
            text_color=Theme.ERROR,
            fg_color=Theme.ERROR_LIGHT,
            corner_radius=6,
            padx=14,
            pady=6
        )
        self.stat_failed.pack(side="left")

        # Results list
        self.results_text = ctk.CTkTextbox(
            inner,
            font=ctk.CTkFont(family=Theme.FONT_MONO, size=11),
            fg_color=Theme.BG_INPUT,
            text_color=Theme.TEXT_SECONDARY,
            border_width=1,
            border_color=Theme.BORDER,
            corner_radius=10,
            state="disabled"
        )
        self.results_text.pack(fill="both", expand=True, pady=(0, 14))

        # Action buttons
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_open_folder = ctk.CTkButton(
            btn_row,
            text="📂 Open Folder",
            command=self._open_folder,
            fg_color=Theme.INFO,
            hover_color="#2563EB",
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12, weight="bold"),
            height=38,
            corner_radius=8,
            state="disabled"
        )
        self.btn_open_folder.pack(side="left", padx=(0, 10))

        self.btn_export = ctk.CTkButton(
            btn_row,
            text="💾 Export CSV",
            command=self._export_results,
            fg_color=Theme.SECONDARY,
            hover_color=Theme.SECONDARY_HOVER,
            font=ctk.CTkFont(family=Theme.FONT_FAMILY, size=12, weight="bold"),
            height=38,
            corner_radius=8,
            state="disabled"
        )
        self.btn_export.pack(side="left")

    # =========================================================================
    # DRAG AND DROP
    # =========================================================================

    def _setup_dnd(self):
        if not DRAG_DROP_AVAILABLE:
            return
        try:
            self.file_list._textbox.drop_target_register(DND_FILES)
            self.file_list._textbox.dnd_bind("<<Drop>>", self._on_drop)
            self.file_list._textbox.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.file_list._textbox.dnd_bind("<<DragLeave>>", self._on_drag_leave)
        except Exception as e:
            self.logger.warning(f"DnD setup failed: {e}")

    def _on_drag_enter(self, e):
        self.drop_zone.configure(border_color=Theme.PRIMARY)

    def _on_drag_leave(self, e):
        self.drop_zone.configure(border_color=Theme.BORDER)

    def _on_drop(self, e):
        self.drop_zone.configure(border_color=Theme.BORDER)
        import re
        data = e.data.replace("file://", "")
        files = re.findall(r"\{([^}]+)\}", data) if "{" in data else data.split()

        for f in files:
            f = f.strip()
            if os.path.isfile(f) and f.lower().endswith(".pdf"):
                if f not in self.selected_files:
                    self.selected_files.append(f)
            elif os.path.isdir(f):
                self._add_pdfs_from_folder(f)

        self._update_file_display()
        self._update_unlock_state()
        return e.action

    # =========================================================================
    # FILE HANDLING
    # =========================================================================

    def _add_pdfs_from_folder(self, folder: str):
        try:
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        path = os.path.join(root, f)
                        if path not in self.selected_files:
                            self.selected_files.append(path)
        except Exception as e:
            self.logger.error(f"Folder scan error: {e}")

    def _browse_files(self):
        initial = self.config.get("last_input_folder", os.path.expanduser("~"))
        files = filedialog.askopenfilenames(
            title="Select PDF Files",
            initialdir=initial,
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if files:
            self.config["last_input_folder"] = os.path.dirname(files[0])
            self.config_manager.save_config(self.config)
            for f in files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
            self._update_file_display()
            self._update_unlock_state()

    def _browse_folder(self):
        initial = self.config.get("last_input_folder", os.path.expanduser("~"))
        folder = filedialog.askdirectory(title="Select Folder", initialdir=initial)
        if folder:
            self.config["last_input_folder"] = folder
            self.config_manager.save_config(self.config)
            count_before = len(self.selected_files)
            self._add_pdfs_from_folder(folder)
            if len(self.selected_files) == count_before:
                messagebox.showinfo("No PDFs Found", "No PDF files found in the selected folder.")
            else:
                self._update_file_display()
                self._update_unlock_state()

    def _clear_files(self):
        self.selected_files.clear()
        self._update_file_display()
        self._update_unlock_state()

    def _update_file_display(self):
        self.file_list.configure(state="normal")
        self.file_list.delete("1.0", "end")

        if self.selected_files:
            for i, f in enumerate(self.selected_files, 1):
                self.file_list.insert("end", f"{i}. {os.path.basename(f)}\n")
            count = len(self.selected_files)
            self.file_count_badge.configure(
                text=f"📄 {count} file{'s' if count != 1 else ''}",
                text_color=Theme.PRIMARY,
                fg_color=Theme.INFO_LIGHT
            )
        else:
            self.file_list.insert("end", "Drop PDF files here or click Browse...")
            self.file_count_badge.configure(
                text="0 files",
                text_color=Theme.TEXT_MUTED,
                fg_color=Theme.BG_INPUT
            )

        self.file_list.configure(state="disabled")

    def _update_unlock_state(self):
        state = "normal" if self.selected_files and not self.is_processing else "disabled"
        self.btn_unlock.configure(state=state)

    # =========================================================================
    # PASSWORD HANDLING
    # =========================================================================

    def _toggle_password(self):
        if self.password_visible:
            self.stored_password = self.password_input.get("1.0", "end-1c")
            self.password_input.delete("1.0", "end")
            self.password_input.insert("1.0", self._mask_text(self.stored_password))
            self.password_input.configure(text_color=Theme.TEXT_MUTED)
            self.btn_toggle.configure(text="🔒")
            self.password_visible = False
        else:
            self.password_input.delete("1.0", "end")
            self.password_input.insert("1.0", self.stored_password)
            self.password_input.configure(text_color=Theme.TEXT_PRIMARY)
            self.btn_toggle.configure(text="👁")
            self.password_visible = True

    def _on_password_key(self, e):
        if not self.password_visible and e.keysym not in ("Tab", "Escape"):
            return "break"
        return None

    def _mask_text(self, text: str) -> str:
        if not text:
            return ""
        return "\n".join(
            "".join("•" if c not in (",", " ", "\t") else c for c in line)
            for line in text.split("\n")
        )

    def _get_passwords(self) -> List[str]:
        text = self.password_input.get("1.0", "end-1c") if self.password_visible else self.stored_password
        text = text.strip()
        if not text:
            return []
        passwords = []
        for line in text.split("\n"):
            passwords.extend(p.strip() for p in line.split(",") if p.strip())
        return passwords

    def _set_passwords(self, passwords: List[str]):
        text = "\n".join(passwords)
        if self.password_visible:
            self.password_input.delete("1.0", "end")
            self.password_input.insert("1.0", text)
        else:
            self.stored_password = text
            self.password_input.delete("1.0", "end")
            self.password_input.insert("1.0", self._mask_text(text))

    def _load_saved_data(self):
        if self.config.get("remember_passwords", False) and self.keyring_available:
            saved = PasswordManager.load_passwords()
            if saved:
                self._set_passwords(saved)
                self.remember_var.set(True)

    # =========================================================================
    # PROCESSING
    # =========================================================================

    def _start_unlock(self):
        passwords = self._get_passwords()
        if not passwords:
            messagebox.showerror("No Passwords", "Please enter at least one password.")
            return

        missing = [f for f in self.selected_files if not os.path.exists(f)]
        if missing:
            messagebox.showerror("Files Missing", f"{len(missing)} file(s) not found.")
            return

        # Save preferences
        if self.remember_var.get() and self.keyring_available:
            PasswordManager.save_passwords(passwords)
            self.config["remember_passwords"] = True
        else:
            if self.keyring_available:
                PasswordManager.clear_passwords()
            self.config["remember_passwords"] = False
        self.config_manager.save_config(self.config)

        # Reset UI
        self.results.clear()
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.configure(state="disabled")
        self.stat_success.configure(text="✓ 0")
        self.stat_failed.configure(text="✗ 0")
        self.progress_bar.set(0)

        self.is_processing = True
        self._set_ui_processing(True)
        self.status_label.configure(text="🔄 Processing...", text_color=Theme.WARNING)

        self.result_queue = queue.Queue()
        threading.Thread(
            target=self.processor.process_batch,
            args=(self.selected_files, passwords, self.result_queue),
            daemon=True
        ).start()
        self._poll_queue()

    def _cancel(self):
        self.processor.cancel_processing()
        self.status_label.configure(text="⏹ Cancelling...", text_color=Theme.ERROR)
        self.btn_cancel.configure(state="disabled")

    def _set_ui_processing(self, processing: bool):
        state = "disabled" if processing else "normal"
        self.btn_browse_files.configure(state=state)
        self.btn_browse_folder.configure(state=state)
        self.btn_clear.configure(state=state)
        self.btn_unlock.configure(state="disabled" if processing else ("normal" if self.selected_files else "disabled"))
        self.btn_cancel.configure(state="normal" if processing else "disabled")
        self.btn_export.configure(state="disabled" if processing else ("normal" if self.results else "disabled"))
        self.btn_open_folder.configure(state="disabled" if processing else ("normal" if self.output_folder else "disabled"))

    def _poll_queue(self):
        try:
            while True:
                msg = self.result_queue.get_nowait()
                if msg.type == MessageType.PROGRESS:
                    d = msg.data
                    self.progress_bar.set(d["current"] / d["total"])
                    eta = d.get("eta", "")
                    text = f"🔄 {d['current']}/{d['total']}"
                    if eta:
                        text += f" • {eta}"
                    self.status_label.configure(text=text, text_color=Theme.WARNING)
                elif msg.type == MessageType.RESULT:
                    self._add_result(msg.data)
                elif msg.type == MessageType.COMPLETE:
                    self._on_complete(msg.data)
                    return
        except queue.Empty:
            pass
        if self.is_processing:
            self.after(100, self._poll_queue)

    def _add_result(self, result: UnlockResult):
        self.results.append(result)
        if result.output_path:
            self.output_folder = os.path.dirname(result.output_path)

        success_count = sum(1 for r in self.results if r.status == "Success")
        fail_count = len(self.results) - success_count
        self.stat_success.configure(text=f"✓ {success_count}")
        self.stat_failed.configure(text=f"✗ {fail_count}")

        self.results_text.configure(state="normal")
        if result.status == "Success":
            self.results_text.insert("end", f"✅ {result.filename} → {result.password_used}\n")
        else:
            self.results_text.insert("end", f"❌ {result.filename} → {result.error_message}\n")
        self.results_text.see("end")
        self.results_text.configure(state="disabled")

    def _on_complete(self, data: dict):
        self.is_processing = False
        self._set_ui_processing(False)
        self.progress_bar.set(1)

        total, success = data["total"], data["success"]
        cancelled = data.get("cancelled", False)

        if cancelled:
            self.status_label.configure(text="⏹ Cancelled", text_color=Theme.ERROR)
            messagebox.showinfo("Cancelled", f"Processed {success + data['fail']}/{total} files.")
        else:
            self.status_label.configure(text="✅ Complete!", text_color=Theme.SUCCESS)
            messagebox.showinfo("Complete", f"🎉 Unlocked {success} of {total} PDF(s)!")

    def _open_folder(self):
        if not self.output_folder or not os.path.exists(self.output_folder):
            messagebox.showerror("Error", "Output folder not found.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(self.output_folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", self.output_folder])
            else:
                subprocess.run(["xdg-open", self.output_folder])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def _export_results(self):
        if not self.results:
            return
        from core.results_exporter import ResultsExporter
        initial = self.config.get("last_output_folder", os.path.expanduser("~"))
        path = filedialog.asksaveasfilename(
            title="Export Results",
            initialdir=initial,
            initialfile=ResultsExporter.generate_filename(),
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")]
        )
        if path:
            self.config["last_output_folder"] = os.path.dirname(path)
            self.config_manager.save_config(self.config)
            if ResultsExporter.export_to_csv(self.results, path):
                messagebox.showinfo("Exported", f"Results saved to:\n{path}")
            else:
                messagebox.showerror("Error", "Failed to export results.")

    def _on_close(self):
        if self.is_processing:
            if messagebox.askyesno("Processing", "Unlocking in progress. Exit anyway?"):
                self.processor.cancel_processing()
                self.destroy()
        else:
            self.destroy()
