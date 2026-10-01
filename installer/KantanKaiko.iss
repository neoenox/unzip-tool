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
DisableProgramGroupPage=no
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
UninstallDisplayName=かんたん解凍
SetupLogging=yes
ChangesAssociations=yes

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\かんたん解凍"; Filename: "{app}\KantanKaiko.exe"
Name: "{autodesktop}\かんたん解凍"; Filename: "{app}\KantanKaiko.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\KantanKaiko.Archive"; ValueType: string; ValueData: "かんたん解凍 アーカイブ"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\KantanKaiko.Archive\DefaultIcon"; ValueType: string; ValueData: """{app}\KantanKaiko.exe"",0"
Root: HKCU; Subkey: "Software\Classes\KantanKaiko.Archive\shell\open\command"; ValueType: string; ValueData: """{app}\KantanKaiko.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "かんたん解凍"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\shell\open\command"; ValueType: string; ValueData: """{app}\KantanKaiko.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.zip\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".zip"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.7z\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".7z"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.rar\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".rar"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.tar\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".tar"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.gz\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".gz"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.tgz\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".tgz"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.bz2\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".bz2"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.tbz\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".tbz"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.xz\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".xz"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\.txz\OpenWithProgids"; ValueType: string; ValueName: "KantanKaiko.Archive"; ValueData: ""; Flags: uninsdeletevalue uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\Classes\Applications\KantanKaiko.exe\SupportedTypes"; ValueType: string; ValueName: ".txz"; ValueData: ""

[Run]
Filename: "{app}\KantanKaiko.exe"; Description: "かんたん解凍を起動する"; Flags: nowait postinstall skipifsilent
