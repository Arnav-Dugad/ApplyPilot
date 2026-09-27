; Inno Setup script for the ApplyPilot Windows installer. Run via packaging/build.ps1.
; Installs per user (no administrator prompt). Your data in %LOCALAPPDATA%\ApplyPilot is kept on uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7C1E2B8E-4E0B-4E7D-9A62-3B0F1F0C2A11}
AppName=ApplyPilot
AppVersion={#AppVersion}
AppVerName=ApplyPilot {#AppVersion}
AppPublisher=Arnav Dugad
AppPublisherURL=https://github.com/Arnav-Dugad/ApplyPilot
AppSupportURL=https://github.com/Arnav-Dugad/ApplyPilot/issues
AppUpdatesURL=https://github.com/Arnav-Dugad/ApplyPilot/releases
DefaultDirName={localappdata}\Programs\ApplyPilot
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=ApplyPilot-Setup-{#AppVersion}
SetupIconFile=applypilot.ico
UninstallDisplayIcon={app}\ApplyPilot.exe
UninstallDisplayName=ApplyPilot
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\build\pyinstaller\dist\ApplyPilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove files from the previous version's bundle so upgrades never mix library versions.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\ApplyPilot"; Filename: "{app}\ApplyPilot.exe"
Name: "{autodesktop}\ApplyPilot"; Filename: "{app}\ApplyPilot.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ApplyPilot.exe"; Description: "Launch ApplyPilot"; Flags: nowait postinstall skipifsilent
; Automatic updates run the installer silently with /RELAUNCH=1 so ApplyPilot reopens on the new version.
Filename: "{app}\ApplyPilot.exe"; Flags: nowait; Check: ShouldRelaunch

[UninstallRun]
; Remove the "start with Windows" entry if the user had enabled it.
Filename: "{sys}\reg.exe"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v ApplyPilot /f"; Flags: runhidden; RunOnceId: "RemoveAutostart"

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;
