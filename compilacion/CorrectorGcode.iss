; ============================================================
;  CorrectorGcode.iss  -  Inno Setup Script
;  Instalador profesional para el Corrector G-Code
;  (impresora de cemento). Requiere el .exe compilado con
;  PyInstaller en ..\build\dist\CorrectorGcode.exe
;
;  Compilacion:
;      "ISCC.exe" CorrectorGcode.iss
; ============================================================

#define MyAppName "Corrector G-Code"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Proyecto Isaac"
#define MyAppExeName "CorrectorGcode.exe"

[Setup]
AppId={{2A1B9C3E-4F5D-4A6B-8C7D-9E0F1A2B3C4D}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CorrectorGcode
DefaultGroupName=Corrector G-Code
DisableProgramGroupPage=yes
SetupIconFile=..\build\icono.ico
OutputDir=..\distribucion
OutputBaseFilename=CorrectorGcode-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\build\dist\CorrectorGcode.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ANALISIS.md"; DestDir: "{app}\Documentacion"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\Documentacion"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\*"
Type: dirifempty; Name: "{app}"