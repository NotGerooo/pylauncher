; ============================================================
; Gero's Launcher — Inno Setup Script
; ============================================================
; Requisitos:
;   - Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;   - El .exe ya compilado con PyInstaller en dist\GerosLauncher.exe
;   - El icono en assets\icon.ico (ajusta la ruta si es diferente)
;
; Para compilar:
;   Abre este archivo en Inno Setup Compiler y presiona Compile (F9)
; ============================================================

#define AppName      "Gero's Launcher"
#define AppVersion   "1.0.0"
#define AppPublisher "NotGero"
#define AppExeName   "GerosLauncher.exe"
#define AppURL       "https://github.com/NotGerooo/pylauncher"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Directorio de instalación por defecto
DefaultDirName={autopf}\GerosLauncher
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Carpeta de salida del instalador generado
OutputDir=installer_output
OutputBaseFilename=GerosLauncher_Setup_v{#AppVersion}

; Icono del instalador (el mismo del launcher)
SetupIconFile=assets\icon.ico

; Compresión
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Requiere privilegios de administrador para instalar en Program Files
PrivilegesRequired=admin

; Mostrar asistente moderno
WizardStyle=modern

; El instalador se ve con imagen lateral
; WizardImageFile=assets\installer_banner.bmp  ; opcional (164x314 px)

; Información de la licencia (opcional)
; LicenseFile=LICENSE.txt

; Metadatos para Windows
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
; Opciones que el usuario puede elegir durante la instalación
Name: "desktopicon";   Description: "Crear acceso directo en el Escritorio";  GroupDescription: "Accesos directos:"; Flags: unchecked
Name: "startmenuicon"; Description: "Crear acceso directo en el Menú Inicio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
; Ejecutable principal
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Icono por separado (para accesos directos)
Source: "assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; Si tienes otros archivos junto al .exe (datos, dlls extra), agrégalos aquí:
; Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Acceso directo en el Menú Inicio
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: startmenuicon

; Acceso directo en el Escritorio
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

; Acceso directo para desinstalar en el Menú Inicio
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[Run]
; Opción para ejecutar el launcher al terminar la instalación
Filename: "{app}\{#AppExeName}"; Description: "Iniciar {#AppName} ahora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; No hace falta nada extra; Inno Setup borra los archivos listados en [Files]

[Code]
// Código Pascal opcional — puedes agregar lógica personalizada aquí.
// Por ahora está vacío; Inno Setup maneja todo automáticamente.
