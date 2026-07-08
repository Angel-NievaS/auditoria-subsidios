; Inno Setup script — Auditoría de Subsidios Talento Digital
; Para compilar: abrir este archivo con Inno Setup Compiler o ejecutar:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

#define AppName      "Auditoria Subsidios"
#define AppVersion   "1.1"
#define AppPublisher "Sustantiva SPA"
#define AppExeName   "Auditoria Subsidios.exe"
#define SourceDir    "dist\Auditoria Subsidios"

[Setup]
AppId={{A3F2B1C4-8D7E-4F2A-9B6C-1E5D3A7F0C2B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=https://sustantiva.cl
AppPublisher={#AppPublisher}
DefaultDirName=C:\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=Auditoria_Subsidios_v{#AppVersion}_Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el &Escritorio"; GroupDescription: "Iconos adicionales:"

[Files]
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar";        Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
