# PDF Unlocker

A Windows desktop app that strips encryption from password-protected PDFs in
batch — you supply the passwords, it writes decrypted copies alongside the
originals. It is **not** a password cracker; it only opens files whose password
you already know.

The decryption itself is about ten lines of `pikepdf`. Everything around it is
the part worth reading:

- **Threaded work that never touches a widget.** Workers post typed
  `QueueMessage` objects to a `queue.Queue`; the window drains it on the Tk
  thread via `after()`. Tkinter is not thread-safe, so a violation surfaces as
  an intermittent crash rather than a failing test.
- **A batch that cannot strand the UI.** `process_batch` emits exactly one
  `COMPLETE` on every path, fatal errors included, so the window never sits
  disabled waiting for a message that is not coming.
- **A probe that refuses to guess.** Trying the empty password first separates
  three cases that look identical from outside — unencrypted, owner-locked,
  user-password-locked — so the app never reports that a password worked on a
  file that had none.
- **Secrets that stay secret.** A result carries the 1-based *index* of the
  password that matched, never its value. Nothing reaches the screen, the log
  or the exported CSV.
- **Writes that survive interruption.** Config saves go to a temp file and
  `os.replace`, and exported CSV cells are escaped against spreadsheet formula
  injection because filenames and qpdf error strings are attacker-influenced.
- **Themes as `(light, dark)` token pairs.** CustomTkinter resolves each pair
  against the current appearance mode, so switching themes needs no repainting
  code anywhere in the UI.
- **Tests that build their own PDFs.** Fixtures are generated in-process with
  `pikepdf`, so there is no binary test data, and each regression test names
  the defect it prevents.

Each of those decisions is documented where it lives, next to the code it
governs, rather than in a separate design doc that drifts:

| Decision | Where the reasoning is |
|---|---|
| Empty-password probe, three outcomes | `PDFProcessor._attempt_unlock` in [`core/pdf_processor.py`](pdf_unlocker/core/pdf_processor.py) |
| Guaranteed `COMPLETE`, index-only results | `PDFProcessor.process_batch` and `UnlockResult` in the same file |
| Worker/UI boundary | module docstring and `MainWindow._poll_queue` in [`ui/main_window.py`](pdf_unlocker/ui/main_window.py) |
| Atomic config write | `ConfigManager.save_config` in [`core/config_manager.py`](pdf_unlocker/core/config_manager.py) |
| Formula-injection escaping | `_sanitize` in [`core/results_exporter.py`](pdf_unlocker/core/results_exporter.py) |
| Output-folder exclusion rules | `find_pdfs` in [`core/file_scanner.py`](pdf_unlocker/core/file_scanner.py) |
| Theme token pairs | module docstring in [`ui/theme.py`](pdf_unlocker/ui/theme.py) |
| Dependency upper bounds | comment above `dependencies` in [`pyproject.toml`](pyproject.toml) |
| The defects the suite pins | test docstrings in [`tests/test_pdf_processor.py`](tests/test_pdf_processor.py) |

## Quick start

```bash
pip install -r requirements.txt
python -m pdf_unlocker
```

Or double-click `scripts\run_app.bat`, which installs dependencies on first run.
`scripts\create_desktop_shortcut.vbs` puts a shortcut to that on your desktop.

Requires Python 3.9 or newer.

## How it works

For each file the engine tries the empty password first, which separates three
cases that look identical from the outside:

| Case | Reported as |
|---|---|
| Not encrypted at all | **Skipped** — nothing to unlock |
| Encrypted, no user password (permissions-only / owner lock) | **Success** — "no user password" |
| Encrypted with a user password | **Success** — "password #N", or **Failed** |

That third column is the whole point of the design: the app never claims a
password worked on a file that had none.

Decryption itself relies on `pikepdf.Pdf.save()`, which omits encryption from
its output. The pinned upper bound on pikepdf in `requirements.txt` exists
because that behaviour is load-bearing.

## Usage

The window is one panel with a **Files / Results** switcher, a password field,
and the unlock button. Counters sit in the panel header, so a run can be
watched from either tab.

1. **Add PDFs** — `+ Files`, `+ Folder`, or drag and drop files or folders
   anywhere on the window. Folder scans recurse but skip the `unlocked` output
   folder, so re-running a folder never reprocesses its own results. Remove a
   single file with the `✕` on its row.
2. **Enter passwords** — one password, or several separated by commas. The
   field is masked; the eye button reveals it. It stays editable either way.
3. **Unlock** — the button names what it will do ("Unlock 6 files"). Progress,
   counts and an ETA update live, and the view switches to Results so you can
   watch it fill. `Stop` halts after the file currently being written.
4. **Review** — `Open folder` reveals the output; `Export CSV` writes a report.

Feedback is inline. A floating strip at the bottom reports what happened
instead of a modal dialog, so nothing blocks the window mid-run. The only
dialog left is the confirmation when you close during a batch.

### Keyboard

| | |
|---|---|
| `Ctrl+O` | add files |
| `Ctrl+Shift+O` | add a folder |
| `Ctrl+Enter` / `Enter` in the field | unlock |
| `Ctrl+L` | clear the list |
| `Esc` | stop a running batch |

### Appearance

Dark by default, with a light theme behind the `☾`/`☀` button in the top-right.
The choice is saved to `config.json`. Every colour token is a `(light, dark)`
pair, so CustomTkinter repaints the whole window on toggle with no per-widget
theme code.

### Output location

```
Original:  C:\Documents\statement.pdf
Unlocked:  C:\Documents\unlocked\unlocked_statement.pdf
```

One `unlocked` folder is created beside each source folder. Existing files with
the same name are overwritten.

## Passwords and privacy

- Nothing leaves your computer. All processing is local.
- **Passwords are never displayed, logged or exported.** The results pane and
  the CSV record *which* password matched by position ("password #2"), never
  its value.
- Checking "Remember in the OS credential store" stores passwords there
  (Windows Credential Locker / macOS Keychain / Linux Secret Service) via
  `keyring`. Unchecking it and unlocking again deletes them. The checkbox is
  disabled if no keyring backend is available.
- Exported CSV cells are escaped against spreadsheet formula injection, since
  filenames and PDF error strings end up in that file.

## Project layout

```
pdf_unlocker/
├── pdf_unlocker/            application package
│   ├── __main__.py          python -m pdf_unlocker
│   ├── app.py               bootstrap: DPI, config, logging, window
│   ├── logging_config.py    rotating file log + optional console
│   ├── core/                no UI imports anywhere in here
│   │   ├── config_manager.py    JSON config at platformdirs paths
│   │   ├── file_scanner.py      PDF discovery and exclusion rules
│   │   ├── password_manager.py  OS keyring integration
│   │   ├── pdf_processor.py     threaded unlock engine
│   │   └── results_exporter.py  CSV report
│   └── ui/
│       ├── main_window.py   window, layout and event handling
│       └── theme.py         design tokens, each a (light, dark) pair
├── tests/                   pytest suite
├── scripts/                 run, build and shortcut helpers
├── entry_point.py           PyInstaller target only
└── pyproject.toml
```

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest        # test suite
python -m ruff check .  # lint
```

Fixtures are built in-process by the `make_pdf` fixture in `tests/conftest.py`;
add tests there rather than checking in binary PDFs. Each regression test in
`test_pdf_processor.py` names the defect it prevents in its docstring.

## Building a standalone executable

```bash
scripts\build_exe.bat
```

Runs the test suite first, then produces `dist\PDF Unlocker.exe`. The
`--collect-all tkinterdnd2` flag is required: drag-and-drop depends on a Tcl
package that PyInstaller does not detect on its own.

No prebuilt binary is published. An unsigned, PyInstaller-packed executable
that removes PDF passwords is close to a worst case for antivirus heuristics,
and a SmartScreen warning on a security tool is worse than no download at all.
Build it yourself, or run from source.

## Configuration and logs

| | Windows |
|---|---|
| Config | `%LOCALAPPDATA%\PDFUnlockerPro\PDFUnlocker\config.json` |
| Logs | `%LOCALAPPDATA%\PDFUnlockerPro\PDFUnlocker\Logs\pdf_unlocker.log` |

macOS and Linux paths follow `platformdirs` conventions. Logs rotate at 5 MB,
keeping five files. Deleting `config.json` resets all settings. Config is
written via a temp file and atomic replace, so an interrupted save cannot
truncate it.

## Troubleshooting

**"None of the provided passwords worked"** — the password is wrong, or the PDF
uses an encryption scheme qpdf cannot open. Owner-locked files no longer need a
password at all, so this message now means the user password really is unknown.

**Drag and drop does nothing** — the window logs whether it registered at
startup; check the log for "Drag-and-drop registered on N targets". If drops are
unavailable the empty state says "Add PDFs with the buttons below" instead of
"Drop PDFs here", and a warning strip appears. Reinstall with
`pip install --upgrade --force-reinstall tkinterdnd2`. `+ Files` always works.

**The remember checkbox is greyed out** — no keyring backend. On Linux install
`gnome-keyring` or `kwallet`.

**A file will not open** — close it in any PDF viewer first, and check the log
for the underlying qpdf error.

## Limitations

- Not a password cracker; you must know the password.
- Files are processed 3 at a time (`DEFAULT_MAX_WORKERS` in
  `pdf_unlocker/core/pdf_processor.py`, or pass `max_workers` to
  `PDFProcessor`).
- Very large PDFs take proportionally longer; there is no per-file progress.
- Output filenames collide if two runs target the same folder; the later run
  overwrites.
- The file and result lists render the first 60 and 200 rows respectively and
  count the remainder; export the CSV for the complete record.

## License

MIT. See [LICENSE](LICENSE).
