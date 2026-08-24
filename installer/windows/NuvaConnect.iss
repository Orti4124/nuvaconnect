; Script de Inno Setup para NuvaConnect (Windows)
; Genera un instalador NuvaConnect-Setup.exe con accesos directos y
; opción de configurar el servidor relay durante la instalación.
;
; Requiere: Inno Setup 6 (https://jrsoftware.org/isinfo.php)
; Compilar:  iscc installer\windows\NuvaConnect.iss
; (build.ps1 hace pyinstaller + iscc por ti.)

#define AppName "NuvaConnect"
#define AppVersion "0.1.0"
#define AppPublisher "NuvaProd"
#define AppURL "https://nuvaprod.com"

[Setup]
AppId={{B7B4B6E2-5C1E-4E7A-9E4D-NUVACONNECT01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputBaseFilename=NuvaConnect-Setup
OutputDir=..\..\dist_installer
SetupIconFile=nuvaconnect.ico
UninstallDisplayIcon={app}\NuvaConnect.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Requiere permisos de admin para instalar en Archivos de Programa.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
; Copia todo el directorio generado por PyInstaller (dist\NuvaConnect\).
Source: "..\..\dist\NuvaConnect\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NuvaConnect (Controlar otro equipo)"; Filename: "{app}\NuvaConnect.exe"
Name: "{group}\NuvaConnect Host (Compartir mi equipo)"; Filename: "{app}\NuvaConnect-Host.exe"
Name: "{group}\Desinstalar NuvaConnect"; Filename: "{uninstallexe}"
Name: "{autodesktop}\NuvaConnect"; Filename: "{app}\NuvaConnect.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NuvaConnect.exe"; Description: "Iniciar NuvaConnect"; Flags: nowait postinstall skipifsilent

; ------------------------------------------------------------------
; Pregunta por el servidor relay durante la instalación y lo guarda
; como variable de entorno de sistema para host y viewer.
; ------------------------------------------------------------------
[Code]
var
  RelayPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  RelayPage := CreateInputQueryPage(wpSelectDir,
    'Servidor relay',
    'Configura el servidor de conexión de NuvaConnect',
    'Ingresa la dirección del servidor relay de tu empresa (déjalo por defecto para pruebas locales):');
  RelayPage.Add('Host del relay (ej. relay.nuvaprod.com):', False);
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
