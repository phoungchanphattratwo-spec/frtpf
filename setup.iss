#define MyAppName "Facebook Register Tool"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "KLS"
#define MyAppExeName "FRT.exe"
#define MyAppURL "https://t.me/ftoolpro"
#define SourceDir "C:\Users\KLS COMPUTER\Desktop\FRT_dist\FRT"
#define ProjectDir "C:\Users\KLS COMPUTER\Desktop\FRT"

[Setup]
; ── Application Identity ────────────────────────────────────────────────────
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright=Copyright (C) 2024-2026 {#MyAppPublisher}
AppComments=Facebook Account Registration and Management Tool

; ── Installation Directories ────────────────────────────────────────────────
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
UsePreviousAppDir=yes
DirExistsWarning=auto

; ── Output Configuration ────────────────────────────────────────────────────
OutputDir=C:\Users\KLS COMPUTER\Desktop\FRT_Output
OutputBaseFilename=FRT_Setup_v1.1.0
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright=Copyright (C) 2024-2026 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; ── Compression Settings ────────────────────────────────────────────────────
Compression=lzma2/max
SolidCompression=yes
InternalCompressLevel=max
CompressionThreads=auto

; ── User Interface ──────────────────────────────────────────────────────────
WizardStyle=modern
SetupIconFile={#ProjectDir}\app_icon.ico
UninstallDisplayIcon={#ProjectDir}\app_icon.ico
UninstallDisplayName={#MyAppName}
; WizardImageFile=compiler:WizModernImage-IS.bmp
; WizardSmallImageFile=compiler:WizModernSmallImage-IS.bmp

; ── Security & Privileges ───────────────────────────────────────────────────
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; ── Architecture ────────────────────────────────────────────────────────────
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; ── Installation Behavior ───────────────────────────────────────────────────
DisableProgramGroupPage=yes
DisableWelcomePage=no
DisableDirPage=auto
DisableReadyPage=no
AlwaysShowDirOnReadyPage=yes
AlwaysShowGroupOnReadyPage=yes
ShowLanguageDialog=auto
AllowCancelDuringInstall=yes
CloseApplications=yes
RestartApplications=no

; ── Requirements ────────────────────────────────────────────────────────────
MinVersion=10.0
OnlyBelowVersion=0

; ── Uninstall Configuration ─────────────────────────────────────────────────
Uninstallable=yes
CreateUninstallRegKey=yes
UninstallLogMode=append
UninstallFilesDir={app}\uninst

; ── Miscellaneous ───────────────────────────────────────────────────────────
LicenseFile={#ProjectDir}\license.txt
InfoBeforeFile=
InfoAfterFile=
ChangesAssociations=no
ChangesEnvironment=no
AppMutex=FRT_SingleInstance_Mutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Run {#MyAppName} on Windows startup"; GroupDescription: "Startup:"

[Files]
; ── Main application (PyInstaller output) ────────────────────────────────────
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Icon file for uninstaller ────────────────────────────────────────────────
Source: "{#ProjectDir}\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; ── scrcpy (screen casting) ──────────────────────────────────────────────────
Source: "{#ProjectDir}\scrcpy-win64-v3.1\*"; DestDir: "{app}\scrcpy-win64-v3.1"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── APK files ────────────────────────────────────────────────────────────────
Source: "{#ProjectDir}\com.facebook.katana_*.apk"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#ProjectDir}\com.facebook.lite_*.apk";   DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; ── Assets ───────────────────────────────────────────────────────────────────
Source: "{#ProjectDir}\reactions\*"; DestDir: "{app}\reactions"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ProjectDir}\logo\*";      DestDir: "{app}\logo";      Flags: ignoreversion recursesubdirs createallsubdirs

; ── License ──────────────────────────────────────────────────────────────────
Source: "{#ProjectDir}\license.txt"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Create empty writable folders the app needs at runtime
Name: "{app}\account_backup"
Name: "{app}\vpn"
Name: "{app}\logs"

[Icons]
Name: "{group}\{#MyAppName}";                        Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}";  Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";                  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"

[Registry]
; Startup entry (optional task)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
; Refresh icon cache so the app icon shows correctly without reboot
Filename: "{cmd}"; Parameters: "/c ie4uinit.exe -show"; Flags: runhidden waituntilterminated
Filename: "{cmd}"; Parameters: "/c taskkill /f /im explorer.exe & del /f /q ""%localappdata%\IconCache.db"" & del /f /q ""%localappdata%\Microsoft\Windows\Explorer\iconcache*"" & start explorer.exe"; Flags: runhidden waituntilterminated
; Launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Remove startup entry on uninstall
Filename: "{cmd}"; Parameters: "/c reg delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Run"" /v ""{#MyAppName}"" /f"; Flags: runhidden

[Code]
// ============================================================================
// Deep validation and installation checks
// ============================================================================

// Check if required files exist before installation
function CheckRequiredFiles(): Boolean;
var
  MissingFiles: String;
  FilesToCheck: array[0..2] of String;
  I: Integer;
begin
  Result := True;
  MissingFiles := '';
  
  // Define critical files to check
  FilesToCheck[0] := ExpandConstant('{#SourceDir}\FRT.exe');
  FilesToCheck[1] := ExpandConstant('{#ProjectDir}\license.txt');
  FilesToCheck[2] := ExpandConstant('{#ProjectDir}\app_icon.ico');
  
  // Check each file
  for I := 0 to GetArrayLength(FilesToCheck) - 1 do
  begin
    if not FileExists(FilesToCheck[I]) then
    begin
      Result := False;
      MissingFiles := MissingFiles + #13#10 + '  • ' + ExtractFileName(FilesToCheck[I]);
    end;
  end;
  
  // Show error if files are missing
  if not Result then
  begin
    MsgBox(
      'Installation cannot continue. Required files are missing:' + #13#10 +
      MissingFiles + #13#10#13#10 +
      'Please rebuild the application using PyInstaller first.',
      mbError, MB_OK);
  end;
end;

// Check disk space before installation
function CheckDiskSpace(): Boolean;
begin
  // Always return true - disk space check is optional
  // Inno Setup will handle disk space automatically
  Result := True;
end;

// Check Windows version compatibility
function CheckWindowsVersion(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  
  // Require Windows 10 or later (version 10.0)
  Result := (Version.Major >= 10);
  
  if not Result then
  begin
    MsgBox(
      'This application requires Windows 10 or later.' + #13#10#13#10 +
      'Your Windows version: ' + IntToStr(Version.Major) + '.' + IntToStr(Version.Minor) + #13#10#13#10 +
      'Please upgrade your operating system.',
      mbError, MB_OK);
  end;
end;

// Check if application is currently running
function CheckIfAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  
  // Try to kill the process if it's running
  if Exec('tasklist', '/FI "IMAGENAME eq FRT.exe"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      if MsgBox(
        'Facebook Register Tool is currently running.' + #13#10#13#10 +
        'The application must be closed before installation can continue.' + #13#10#13#10 +
        'Click OK to close it automatically, or Cancel to exit setup.',
        mbConfirmation, MB_OKCANCEL) = IDOK then
      begin
        Exec('taskkill', '/F /IM FRT.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        Sleep(1000);
      end
      else
      begin
        Result := False;
      end;
    end;
  end;
end;

// Main initialization function with all checks
function InitializeSetup(): Boolean;
begin
  Result := True;
  
  // Run all validation checks
  if not CheckWindowsVersion() then
  begin
    Result := False;
    Exit;
  end;
  
  if not CheckDiskSpace() then
  begin
    Result := False;
    Exit;
  end;
  
  // Skip file validation during installation - files are embedded in installer
  // if not CheckRequiredFiles() then
  // begin
  //   Result := False;
  //   Exit;
  // end;
  
  if not CheckIfAppRunning() then
  begin
    Result := False;
    Exit;
  end;
  
  // All checks passed
  Result := True;
end;

// Show installation progress with custom messages
procedure CurStepChanged(CurStep: TSetupStep);
begin
  case CurStep of
    ssInstall:
      begin
        WizardForm.StatusLabel.Caption := 'Installing Facebook Register Tool...';
      end;
    ssPostInstall:
      begin
        WizardForm.StatusLabel.Caption := 'Finalizing installation...';
      end;
  end;
end;

// Ask user whether to keep account_backup data on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  MsgResult: Integer;
  BackupPath: String;
  BackupSize: Int64;
begin
  if CurUninstallStep = usUninstall then
  begin
    BackupPath := ExpandConstant('{app}\account_backup');
    
    // Check if backup folder exists and has data
    if DirExists(BackupPath) then
    begin
      MsgResult := MsgBox(
        'Do you want to keep your account backup data?' + #13#10 +
        '(account_backup folder)' + #13#10#13#10 +
        'Click YES to keep your data, NO to delete everything.',
        mbConfirmation, MB_YESNO);
        
      if MsgResult = IDNO then
      begin
        WizardForm.StatusLabel.Caption := 'Removing user data...';
        DelTree(ExpandConstant('{app}\account_backup'), True, True, True);
        DelTree(ExpandConstant('{app}\vpn'), True, True, True);
        DelTree(ExpandConstant('{app}\logs'), True, True, True);
      end;
    end;
  end;
end;

// Verify installation after completion
procedure DeinitializeSetup();
begin
  // This function runs after setup completes or is cancelled
  // No verification needed here - Inno Setup handles this automatically
end;
