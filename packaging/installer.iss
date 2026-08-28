; Instalador Windows do Confortimetro Klimaa (Inno Setup 6).
; Compilar: iscc packaging\installer.iss  (depois do PyInstaller)
; Instala em %LOCALAPPDATA% -> nao pede permissao de administrador.

#define AppName "Confortimetro Klimaa"
#define AppVersion "0.1.0"

[Setup]
AppId={{2C0B0F2E-6C6F-4B57-9E2E-9E3C2E0A9A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=GAIA - UFPel
DefaultDirName={localappdata}\ConfortimetroKlimaa
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ConfortimetroKlimaa-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\dist\ConfortimetroKlimaa\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\ConfortimetroKlimaa.exe"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\ConfortimetroKlimaa.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ConfortimetroKlimaa.exe"; Description: "Abrir o {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// O EnergyPlus 9.4 nao e embutido: a simulacao carrega o pyenergyplus da
// instalacao local. Procura pelos diretorios padrao antes de instalar; o
// programa faz uma busca mais ampla (PATH, registro, ENERGYPLUS_DIR) ao abrir.
function FindEnergyPlus(): String;
var
  Roots: array[0..1] of String;
  FindRec: TFindRec;
  I: Integer;
  Candidate: String;
begin
  Result := '';
  Roots[0] := 'C:\';
  Roots[1] := ExpandConstant('{commonpf}') + '\';
  for I := 0 to 1 do
  begin
    if FindFirst(Roots[I] + 'EnergyPlusV*', FindRec) then
    try
      repeat
        Candidate := Roots[I] + FindRec.Name;
        if FileExists(Candidate + '\Energy+.idd') then
        begin
          // Preferencia para a 9.4; qualquer outra serve so como aviso.
          if Pos('V9-4', FindRec.Name) > 0 then
          begin
            Result := Candidate;
            Exit;
          end;
          if Result = '' then
            Result := Candidate;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  Found: String;
  ErrorCode: Integer;
begin
  Result := True;
  Found := FindEnergyPlus();

  if Found = '' then
  begin
    if MsgBox('O EnergyPlus 9.4 nao foi encontrado nesta maquina.' #13#10#13#10
              'A instalacao do Confortimetro continua, mas para simular e'
              #13#10 'preciso instalar o EnergyPlus 9.4.' #13#10#13#10
              'Abrir agora a pagina de download?',
              mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open',
                'https://github.com/NREL/EnergyPlus/releases/tag/v9.4.0',
                '', '', SW_SHOW, ewNoWait, ErrorCode);
  end
  else if Pos('V9-4', Found) = 0 then
    MsgBox('Foi encontrado o EnergyPlus em:' #13#10 + Found + #13#10#13#10
           'O programa espera a versao 9.4 e a simulacao pode falhar com'
           #13#10 'outra versao.', mbInformation, MB_OK);
end;
