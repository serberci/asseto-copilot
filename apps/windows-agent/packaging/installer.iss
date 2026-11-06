; Inno Setup script. Compile on Windows with ISCC after the PyInstaller build.
; Settings and diagnostic recordings live in %APPDATA%\AssettoCorsaCoachAgent.
; Uninstall asks before deleting them. The default is to keep them.

#define AppName "Assetto Corsa Coach Agent"
#define AppVersion "0.1.0"
#define AppExe "AssettoCorsaCoachAgent.exe"

[Setup]
AppId={{8F3A1C2E-4B77-4A1E-9C2D-6B0E5A9D4F11}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\AssettoCorsaCoachAgent
DefaultGroupName={#AppName}
OutputBaseFilename=AssettoCorsaCoachAgent-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "startup"; Description: "Launch when Windows starts"; Flags: unchecked

[Files]
Source: "..\dist\AssettoCorsaCoachAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AssettoCorsaCoachAgent"; ValueData: """{app}\{#AppExe}"" --minimized"; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox('Delete settings and diagnostic recordings too? They are kept if you choose No.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\AssettoCorsaCoachAgent'), True, True, True);
  end;
end;
