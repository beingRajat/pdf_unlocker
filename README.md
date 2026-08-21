# PDF Unlocker Pro

A professional desktop application for unlocking password-protected PDF files with a clean, user-friendly interface.

## Features

- **Multiple Input Methods**: Browse individual files, select entire folders, or drag-and-drop PDFs directly into the application
- **Batch Processing**: Process multiple PDFs simultaneously with progress tracking and ETA
- **Password Management**: Securely store passwords using your system's credential manager (Windows Credential Locker, macOS Keychain, Linux Secret Service)
- **Smart Password Handling**: Enter multiple passwords at once (comma-separated or one per line) - the app tries them all
- **Progress Tracking**: Real-time progress bar with estimated time remaining
- **Results Export**: Export processing results to CSV for record-keeping
- **Multi-threaded**: Processes up to 3 PDFs concurrently while keeping the UI responsive
- **Professional UI**: Clean, intuitive interface that anyone can use

## Installation

### Requirements

- Python 3.8 or higher
- Windows, macOS, or Linux

### Setup

1. **Clone or download** this repository

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python pdf_unlocker.py
   ```

### Dependencies

- `pikepdf>=8.0.0` - PDF manipulation
- `keyring>=24.0.0` - Secure password storage
- `platformdirs>=4.0.0` - Cross-platform configuration paths
- `tkinterdnd2>=0.3.0` - Drag-and-drop support
- `customtkinter>=5.2.0` - Modern UI framework with DPI awareness

## Usage

### Basic Workflow

1. **Select PDFs**:
   - Click "Browse Files" to select individual PDFs
   - Click "Browse Folder" to select all PDFs in a folder
   - Drag-and-drop files or folders directly into the file list area

2. **Enter Passwords**:
   - Type passwords in the text area (one per line or comma-separated)
   - Click the eye icon (👁) to show/hide passwords
   - Check "Remember these passwords" to save them securely for future use

3. **Unlock PDFs**:
   - Click "Unlock PDFs" to start processing
   - Monitor progress with the progress bar and status updates
   - Click "Cancel" if you need to stop

4. **View Results**:
   - Results show which files succeeded and which passwords worked
   - Click "Open Output Folder" to view unlocked PDFs
   - Click "Export Results" to save a CSV report

### Password Input Formats

You can enter multiple passwords in two ways:

**One per line**:
```
password123
mySecret456
unlock789
```

**Comma-separated**:
```
password123, mySecret456, unlock789
```

**Mixed**:
```
password123, mySecret456
unlock789
```

### Output Location

Unlocked PDFs are saved in an "unlocked" subfolder next to the original files:

```
Original:  C:\Documents\locked.pdf
Unlocked:  C:\Documents\unlocked\unlocked_locked.pdf
```

### Secure Password Storage

When you check "Remember these passwords for future use":
- Passwords are encrypted and stored in your system's credential manager
- Windows: Windows Credential Locker
- macOS: Keychain
- Linux: Secret Service API (requires GNOME Keyring or KWallet)
- Passwords automatically load on next launch

**Note**: The checkbox will be disabled if secure storage is not available on your system.

## Configuration

Configuration and logs are stored in platform-specific locations:

**Windows**:
- Config: `C:\Users\{username}\AppData\Local\PDFUnlockerPro\PDFUnlocker\config.json`
- Logs: `C:\Users\{username}\AppData\Local\PDFUnlockerPro\PDFUnlocker\Logs\`

**macOS**:
- Config: `~/Library/Application Support/PDFUnlocker/config.json`
- Logs: `~/Library/Logs/PDFUnlocker/`

**Linux**:
- Config: `~/.config/PDFUnlocker/config.json`
- Logs: `~/.local/state/PDFUnlocker/log/`

### Configuration File

The `config.json` file stores:
- Last input/output folders (for convenience)
- Remember passwords preference

You can manually delete this file to reset all settings.

## Building Standalone Executable

To create a standalone .exe (Windows) or app bundle (macOS):

### Windows

```bash
# Run the build script
build_exe.bat

# Or manually:
pyinstaller --onefile --noconsole --name "PDF Unlocker Pro" pdf_unlocker.py
```

The executable will be in the `dist/` folder.

### macOS/Linux

```bash
pyinstaller --onefile --windowed --name "PDF Unlocker Pro" pdf_unlocker.py
```

## Troubleshooting

### "Drag-and-drop support is not available"

If you see this warning on startup:
- The `tkinterdnd2` library is not properly installed
- Drag-and-drop will be disabled, but Browse buttons still work
- Try reinstalling: `pip install --upgrade --force-reinstall tkinterdnd2`

### "Remember passwords (unavailable)"

If the password remember checkbox is disabled:
- Your system's keyring backend is not available
- You can still use the app, passwords just won't be saved
- On Linux, install `gnome-keyring` or `kwallet`

### "None of the provided passwords worked"

If all passwords fail:
- Double-check your passwords for typos
- Some PDFs have owner passwords vs user passwords (this tool tries user passwords)
- The PDF might use advanced encryption that requires specialized tools

### Application won't start

1. Check Python version: `python --version` (need 3.8+)
2. Reinstall dependencies: `pip install -r requirements.txt --upgrade`
3. Check logs in the log directory for error details

### Files are locked/in use

- Close any PDF viewers (Adobe Reader, Preview, etc.)
- Ensure the files aren't open in other applications
- Check file permissions

## Logging

The application creates detailed logs for troubleshooting:

- **Main log** (`pdf_unlocker.log`): All application activity
- **Error log** (`error_log.txt`): Detailed error information
- Logs automatically rotate (5MB max, keeps last 5 files)

Check these logs if you encounter issues.

## Security & Privacy

- Passwords are NEVER stored in plain text
- Secure storage uses OS-level encryption
- Passwords are only stored if you explicitly check the "Remember" box
- No data is sent over the network
- All processing happens locally on your computer

## Limitations

- Can only unlock PDFs with known passwords (not a password cracker)
- Processes user passwords, not owner/permissions passwords
- Very large PDFs (100+ MB) may take longer to process
- Maximum 3 PDFs processed concurrently (configurable in code)

## License

This software is provided as-is for personal and commercial use.

## Support

For issues, questions, or suggestions:
1. Check the log files for error details
2. Review this README's troubleshooting section
3. Open an issue on the project repository (if applicable)

## Changelog

### Version 1.0.0
- Initial release
- Multi-threaded PDF unlocking
- Drag-and-drop support
- Secure password storage
- CSV export functionality
- Cross-platform support (Windows, macOS, Linux)
