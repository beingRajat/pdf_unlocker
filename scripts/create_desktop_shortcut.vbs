' Create Desktop Shortcut for PDF Unlocker Pro
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the desktop path
DesktopPath = WshShell.SpecialFolders("Desktop")

' Get the current script directory
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Create the shortcut
Set Shortcut = WshShell.CreateShortcut(DesktopPath & "\PDF Unlocker Pro.lnk")

' Set shortcut properties
Shortcut.TargetPath = ScriptDir & "\run_app.bat"
Shortcut.WorkingDirectory = fso.GetParentFolderName(ScriptDir)
Shortcut.Description = "PDF Unlocker Pro - Unlock password-protected PDFs"
Shortcut.IconLocation = "shell32.dll,265"  ' Lock icon

' Save the shortcut
Shortcut.Save

' Show success message
WScript.Echo "Desktop shortcut created successfully!" & vbCrLf & vbCrLf & _
             "You can now launch PDF Unlocker Pro from your desktop by double-clicking:" & vbCrLf & _
             "'PDF Unlocker Pro'"

