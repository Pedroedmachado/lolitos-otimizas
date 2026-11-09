; Instalador do Lolitos Otimizações (Inno Setup 6).
; Gerado automaticamente por gerar-instalador.bat — ou abra no Inno Setup e clique em Compile.
#define AppName "Lolitos Otimizações"
#define AppVersion "1.2.0"
#define AppExe "LolitosOtimizacoes.exe"
#define AppId "LolitosOtimizacoes"

[Setup]
AppId={{6B1F3C2E-4A5D-4E7B-9C1A-1F0B0D5E9A77}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Lolitos
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} - instalador
DefaultDirName={autopf}\Lolitos Otimizacoes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
LicenseFile=legal\TERMOS_DE_USO.txt
OutputDir=dist
OutputBaseFilename=LolitosOtimizacoes-{#AppVersion}-Setup
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
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
ptbr.WelcomeLabel2=Isto vai instalar o [name/ver] no seu computador.%n%nOtimizador do Windows para jogos: Boost em um clique, otimização por jogo (Steam, Epic, EA, Riot, Battle.net, Ubisoft, GOG...), Preparar e jogar, overlay de FPS e ferramentas de rede. Inclui módulo especial para Black Desert Online.%n%nTudo o que o app aplica pode ser desfeito.

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"
Name: "autostart"; Description: "Iniciar com o Windows (minimizado na bandeja, para o overlay e a tecla funcionarem)"; Flags: unchecked

[Files]
Source: "dist\LolitosOtimizacoes\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "legal\TERMOS_DE_USO.txt"; DestDir: "{app}\legal"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; tarefa agendada: abre já como administrador no logon, sem pedir o UAC toda vez
Filename: "schtasks.exe"; Parameters: "/Create /F /RL HIGHEST /SC ONLOGON /DELAY 0000:15 /TN {#AppId} /TR ""\""{app}\{#AppExe}\"" --tray"""; Flags: runhidden; Tasks: autostart
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName} agora"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillApp"
Filename: "schtasks.exe"; Parameters: "/Delete /F /TN {#AppId}"; Flags: runhidden; RunOnceId: "DelTask"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  { fecha o app (inclusive na bandeja) antes de copiar os arquivos }
  Exec('taskkill.exe', '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if MsgBox('Apagar também o histórico, backups e configurações do app?' + #13#10 +
              '(Os ajustes que estão aplicados no Windows continuam. Para desfazê-los, use a tela ' +
              'Restauração ANTES de desinstalar.)', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\{#AppId}'), True, True, True);
end;
