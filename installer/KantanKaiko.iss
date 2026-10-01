; Build with scripts/build-installer.ps1. The application remains per-user.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef NumericVersion
  #define NumericVersion "1.0.0"
#endif
#ifndef SourceExe
  #define SourceExe "..\dist\KantanKaiko.exe"
#endif
#ifndef OutputDirectory
  #define OutputDirectory "..\dist"
#endif

[Setup]
AppId={{8C259DA6-E5C1-4EF9-8E4D-965A268316A2}
AppName=かんたん解凍
AppVersion={#AppVersion}
AppPublisher=neoenox
AppPublisherURL=https://github.com/neoenox/unzip-tool
AppSupportURL=https://github.com/neoenox/unzip-tool/issues
DefaultDirName={localappdata}\Programs\KantanKaiko
DefaultGroupName=かんたん解凍
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDirectory}
OutputBaseFilename=KantanKaiko-Setup-{#AppVersion}
VersionInfoVersion={#NumericVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
UninstallDisplayIcon={app}\KantanKaiko.exe
SetupLogging=yes

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\かんたん解凍"; Filename: "{app}\KantanKaiko.exe"
Name: "{autodesktop}\かんたん解凍"; Filename: "{app}\KantanKaiko.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KantanKaiko.exe"; Description: "かんたん解凍を起動する"; Flags: nowait postinstall skipifsilent
