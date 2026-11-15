; Inno Setup script for the MusicHub desktop installer.
; Build: build_installer.bat (needs Inno Setup: winget install JRSoftware.InnoSetup)
; Produces installer_output\MusicHub-<version>-Setup.exe

#define MyAppName "MusicHub"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Shreya Kaunla"
#define MyAppExeName "MusicHub.exe"

[Setup]
AppId={{8C27B1A4-6B7D-4E22-9A1B-7C4F2E9D5A31}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-Setup
OutputDir=installer_output
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
LicenseFile=LICENSE

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\MusicHub\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; keep user data (%LOCALAPPDATA%\MusicHub) — only remove app files
Type: filesandordirs; Name: "{app}"
