#define AppName "Sentinel"
#define AppVersion "0.1.0"

#ifndef SourceDir
  #define SourceDir "..\\..\\dist\\SentinelPilot"
#endif

#ifndef AppInstallDir
  #define AppInstallDir "{localappdata}\\Sentinel"
#endif

#ifndef OutputDir
  #define OutputDir "..\\..\\dist\\installer"
#endif

[Setup]
AppId={{7D5E2D4F-5E24-4A14-8A4B-6B2A3E7F7D11}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={#AppInstallDir}
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename=SentinelPilot-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=no
SetupLogging=yes
UninstallDisplayIcon={app}\SentinelPilot.exe

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\SentinelPilot.exe"; Parameters: "pilot --config config\pilot.config.yaml"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\SentinelPilot.exe"; Parameters: "pilot --config config\pilot.config.yaml"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\SentinelPilot.exe"; Parameters: "pilot --config config\pilot.config.yaml"; WorkingDir: "{app}"; Description: "Launch Sentinel now"; Flags: nowait postinstall skipifsilent