; Inno Setup script. Turns the dist\HYSalesEngine folder into one Setup.exe.
[Setup]
AppName=HY Developer Sales Engine
AppVersion=1.0
AppPublisher=HY Developer
DefaultDirName={autopf}\HY Sales Engine
DefaultGroupName=HY Sales Engine
OutputDir=Output
OutputBaseFilename=HYSalesEngine-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
UninstallDisplayName=HY Developer Sales Engine

[Files]
Source: "..\dist\HYSalesEngine\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\HY Sales Engine"; Filename: "{app}\HYSalesEngine.exe"
Name: "{autodesktop}\HY Sales Engine"; Filename: "{app}\HYSalesEngine.exe"

[Run]
Filename: "{app}\HYSalesEngine.exe"; Description: "Open HY Sales Engine now"; Flags: nowait postinstall skipifsilent
; Your data (database, keys, visuals, backups) lives in %APPDATA%\HYSalesEngine and is NOT removed when you uninstall or update.
