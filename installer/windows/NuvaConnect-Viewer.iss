; Inno Setup — Instalador SOLO del Host (equipo que se deja controlar)
#define AppName "NuvaConnect"
#define AppVersion "0.1.0"
#define AppPublisher "NuvaProd"

[Setup]
AppId={{B7B4B6E2-5C1E-4E7A-9E4D-NUVACONNECTVIEW}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\NuvaConnect
DefaultGroupName=NuvaConnect
OutputBaseFilename=NuvaConnect-Viewer-Setup
OutputDir=..\..\dist_installer
SetupIconFile=nuvaconnect.ico
UninstallDisplayIcon={app}\NuvaConnect.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\..\dist\NuvaConnect\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NuvaConnect (Controlar otro equipo)"; Filename: "{app}\NuvaConnect.exe"
Name: "{group}\Desinstalar NuvaConnect"; Filename: "{uninstallexe}"
Name: "{autodesktop}\NuvaConnect"; Filename: "{app}\NuvaConnect.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NuvaConnect.exe"; Description: "Iniciar NuvaConnect"; Flags: nowait postinstall skipifsilent

[Code]
var
  RelayPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  RelayPage := CreateInputQueryPage(wpSelectDir,
    'Servidor relay', 'Configura el servidor de conexion de NuvaConnect',
    'Ingresa la direccion del servidor relay (la IP de tu servidor):');
  RelayPage.Add('Host del relay (ej. 164.92.100.25):', False);
  RelayPage.Add('Puerto (ej. 9765):', False);
  RelayPage.Values[0] := 'localhost';
  RelayPage.Values[1] := '9765';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    RegWriteStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'NUVA_RELAY_HOST', RelayPage.Values[0]);
    RegWriteStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
      'NUVA_RELAY_PORT', RelayPage.Values[1]);
  end;
end;
