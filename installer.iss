; Instalador do Lolitos Control (Inno Setup 6).
; Gerado automaticamente por gerar-instalador.bat — ou abra no Inno Setup e clique em Compile.
#define AppName "Lolitos Control"
#define AppVersion "1.7.3"
#define AppExe "LolitosControl.exe"
#define OldExe "LolitosOtimizacoes.exe"
#define OldName "Lolitos Otimizações"
#define AppId "LolitosControl"
#define OldAppId "LolitosOtimizacoes"

[Setup]
AppId={{6B1F3C2E-4A5D-4E7B-9C1A-1F0B0D5E9A77}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Lolitos
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} - instalador
DefaultDirName={autopf}\Lolitos Control
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
ShowLanguageDialog=auto
UsePreviousLanguage=yes
OutputDir=dist
OutputBaseFilename=LolitosControl-{#AppVersion}-Setup
SetupIconFile=build\lolitos.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardImageFile=build\wizard.bmp,build\wizard@2x.bmp
WizardSmallImageFile=build\wizard-small.bmp,build\wizard-small@2x.bmp
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=force
RestartApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"; LicenseFile: "legal\TERMOS_DE_USO.txt"
Name: "en"; MessagesFile: "compiler:Default.isl"; LicenseFile: "legal\TERMS_OF_USE_EN.txt"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"; LicenseFile: "legal\TERMINOS_DE_USO_ES.txt"

[Messages]
ptbr.WelcomeLabel2=Isto vai instalar o [name/ver] no seu computador.%n%nOtimizador do Windows para jogos: Boost em um clique, otimização por jogo (Steam, Epic, EA, Riot, Battle.net, Ubisoft, GOG...), Preparar e jogar, overlay de FPS e ferramentas de manutenção, rede e testes. Inclui módulo especial para Black Desert Online.%n%nTudo o que o app aplica pode ser desfeito.
en.WelcomeLabel2=This will install [name/ver] on your computer.%n%nWindows optimizer for gaming: one-click Boost, per-game optimization (Steam, Epic, EA, Riot, Battle.net, Ubisoft, GOG...), Prepare and play, FPS overlay and maintenance, network and test tools. Includes a special module for Black Desert Online.%n%nEverything the app applies can be undone.
es.WelcomeLabel2=Esto instalará [name/ver] en tu computadora.%n%nOptimizador de Windows para juegos: Boost en un clic, optimización por juego (Steam, Epic, EA, Riot, Battle.net, Ubisoft, GOG...), Preparar y jugar, overlay de FPS y herramientas de mantenimiento, red y pruebas. Incluye un módulo especial para Black Desert Online.%n%nTodo lo que aplica la app se puede deshacer.

[CustomMessages]
ptbr.DesktopIcon=Criar atalho na área de trabalho
en.DesktopIcon=Create a desktop shortcut
es.DesktopIcon=Crear acceso directo en el escritorio
ptbr.AutoStart=Iniciar com o Windows (minimizado na bandeja, para o overlay e a tecla funcionarem)
en.AutoStart=Start with Windows (minimized to the tray, so the overlay and hotkey work)
es.AutoStart=Iniciar con Windows (minimizado en la bandeja, para que el overlay y la tecla funcionen)
ptbr.Uninstall=Desinstalar
en.Uninstall=Uninstall
es.Uninstall=Desinstalar
ptbr.OpenNow=Abrir o %1 agora
en.OpenNow=Open %1 now
es.OpenNow=Abrir %1 ahora
ptbr.DeleteData=Apagar também o histórico, backups e configurações do app?%n%n(Os ajustes que estão aplicados no Windows continuam. Para desfazê-los, use a tela Restauração ANTES de desinstalar.)
en.DeleteData=Also delete the app's history, backups and settings?%n%n(Tweaks currently applied to Windows stay in place. To undo them, use the Restore screen BEFORE uninstalling.)
es.DeleteData=¿Borrar también el historial, las copias de seguridad y la configuración de la app?%n%n(Los ajustes aplicados en Windows se mantienen. Para deshacerlos, usa la pantalla Restauración ANTES de desinstalar.)
ptbr.LangCode=pt
en.LangCode=en
es.LangCode=es

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"
Name: "autostart"; Description: "{cm:AutoStart}"; Flags: unchecked

[Files]
Source: "dist\LolitosControl\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "legal\*.txt"; DestDir: "{app}\legal"; Flags: ignoreversion
; PresentMon (Intel, MIT) para o FPS do overlay — baixado e conferido por tools\get_presentmon.py
Source: "vendor\PresentMon.exe"; DestDir: "{app}\tools"; Flags: ignoreversion skipifsourcedoesntexist

[InstallDelete]
; restos da versão com o nome antigo (Lolitos Otimizações, até a 1.3.x)
Type: files; Name: "{app}\{#OldExe}"
Type: files; Name: "{autodesktop}\{#OldName}.lnk"
Type: filesandordirs; Name: "{autoprograms}\{#OldName}"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:Uninstall} {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; tarefa agendada: abre já como administrador no logon, sem pedir o UAC toda vez
Filename: "schtasks.exe"; Parameters: "/Create /F /RL HIGHEST /SC ONLOGON /DELAY 0000:15 /TN {#AppId} /TR ""\""{app}\{#AppExe}\"" --tray"""; Flags: runhidden; Tasks: autostart
Filename: "{app}\{#AppExe}"; Description: "{cm:OpenNow,{#AppName}}"; Flags: nowait postinstall skipifsilent shellexec
; atualização automática (instalador rodado pelo próprio app com /VERYSILENT /relaunch=1): reabre o app
Filename: "{app}\{#AppExe}"; Flags: nowait shellexec; Check: ShouldRelaunch

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillApp"
Filename: "schtasks.exe"; Parameters: "/Delete /F /TN {#OldAppId}"; Flags: runhidden; RunOnceId: "DelOldTask"
Filename: "schtasks.exe"; Parameters: "/Delete /F /TN {#AppId}"; Flags: runhidden; RunOnceId: "DelTask"

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:relaunch|0}') = '1');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  { fecha o app (inclusive na bandeja) antes de copiar os arquivos }
  Exec('taskkill.exe', '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec('taskkill.exe', '/F /IM {#OldExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { o app abre no idioma escolhido no instalador (dá para trocar nas Configurações) }
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\lang.txt'), CustomMessage('LangCode'), False);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if MsgBox(CustomMessage('DeleteData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\{#AppId}'), True, True, True);
end;
