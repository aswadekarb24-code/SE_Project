; Inno Setup script for the Windows installer (NFR-04: standalone .exe
; installer package). Must be compiled on Windows with Inno Setup
; (https://jrsoftware.org/isinfo.php) -- not runnable in this Linux
; environment; see docs/progress/cycle-5.md for what was/wasn't verified
; here vs. what still needs a Windows machine.
;
; Expects build/pyinstaller.release.spec to have already been built,
; producing dist/HMS.exe (see build/pyinstaller.release.spec's docstring).

#define MyAppName "Hybrid Offline-First HMS"
#define MyAppVersion "0.1.0"
#define MyAppExeName "HMS.exe"

[Setup]
AppId={{B6F6E1B0-3E36-4C2B-9A7C-6C6E7B6E2B10}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer-output
OutputBaseFilename=HMS-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
