Unicode true
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
Name "MagicC"
OutFile "..\dist\MagicC-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\MagicC"
InstallDirRegKey HKCU "Software\MagicC" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "..\media\app.ico"
UninstallIcon "..\media\app.ico"
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom OptionsPage OptionsLeave
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\MagicC.exe"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
Var StartupCheck
Var MenuCheck
Var StartupEnabled
Var MenuEnabled
Function .onInit
  StrCpy $StartupEnabled 0
  StrCpy $MenuEnabled 0
  ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "MagicC"
  ${If} $0 != ""
    StrCpy $StartupEnabled 1
  ${EndIf}
FunctionEnd
Function OptionsPage
  !insertmacro MUI_HEADER_TEXT "安装选项" "选择开机启动和文件右键菜单。"
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateCheckbox} 0 8u 100% 16u "开机启动 MagicC（仅显示托盘图标）"
  Pop $StartupCheck
  ${NSD_SetState} $StartupCheck $StartupEnabled
  ${NSD_CreateCheckbox} 0 36u 100% 28u "启用 Windows 11 新右键菜单（信任 MagicC 本地签名证书）"
  Pop $MenuCheck
  ${NSD_SetState} $MenuCheck $MenuEnabled
  ${NSD_CreateLabel} 0 78u 100% 42u "这是本地测试签名。勾选后请求管理员确认，将 MagicC 证书添加到本地计算机的受信任人存储；卸载时移除。未勾选则使用传统右键菜单。"
  Pop $0
  nsDialogs::Show
FunctionEnd
Function OptionsLeave
  ${NSD_GetState} $StartupCheck $StartupEnabled
  ${NSD_GetState} $MenuCheck $MenuEnabled
FunctionEnd
Section "MagicC" SEC_MAIN
  SetOutPath "$INSTDIR"
  File "..\dist\MagicC.exe"
  File "..\dist\MagicCShell.dll"
  File /oname=MagicC.ico "..\media\app.ico"
  File "..\dist\MagicC.Menu.msix"
  File "..\dist\MagicC.cer"
  File "..\dist\menu.ps1"
  File "..\dist\trust.ps1"
  ${If} $StartupEnabled == 1
    ExecWait '"$INSTDIR\MagicC.exe" --enable-startup' $0
  ${Else}
    ExecWait '"$INSTDIR\MagicC.exe" --disable-startup' $0
  ${EndIf}
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION "开机启动配置失败，可以安装后在设置中重试。"
  ${EndIf}
  ${If} $MenuEnabled == 1
    nsExec::ExecToLog 'powershell.exe -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "$INSTDIR\menu.ps1" -Action Install -TrustLocalCertificate'
    Pop $0
    ${If} $0 != 0
      MessageBox MB_ICONEXCLAMATION "Windows 11 新菜单注册失败，将使用传统右键菜单。"
    ${EndIf}
  ${Else}
    nsExec::ExecToLog 'powershell.exe -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "$INSTDIR\menu.ps1" -Action Uninstall'
    Pop $0
  ${EndIf}
  WriteRegStr HKCU "Software\MagicC" "InstallDir" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\MagicC"
  CreateShortcut "$SMPROGRAMS\MagicC\MagicC.lnk" "$INSTDIR\MagicC.exe"
  CreateShortcut "$SMPROGRAMS\MagicC\卸载 MagicC.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MagicC" "DisplayName" "MagicC"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MagicC" "DisplayVersion" "1.1.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MagicC" "DisplayIcon" "$INSTDIR\MagicC.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MagicC" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MagicC" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MagicC" "NoRepair" 1
SectionEnd
Section "Uninstall"
  ExecWait '"$INSTDIR\MagicC.exe" --disable-startup' $0
  nsExec::ExecToLog 'powershell.exe -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "$INSTDIR\menu.ps1" -Action Uninstall'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "右键菜单注销失败，请重试卸载。"
    Abort
  ${EndIf}
  DeleteRegKey HKCU "Software\Classes\*\shell\MagicCShare"
  DeleteRegKey HKCU "Software\MagicC"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MagicC"
  Delete "$SMPROGRAMS\MagicC\MagicC.lnk"
  Delete "$SMPROGRAMS\MagicC\卸载 MagicC.lnk"
  RMDir "$SMPROGRAMS\MagicC"
  Delete /REBOOTOK "$INSTDIR\MagicCShell.dll"
  Delete /REBOOTOK "$INSTDIR\MagicC.exe"
  Delete "$INSTDIR\MagicC.ico"
  Delete "$INSTDIR\MagicC.Menu.msix"
  Delete "$INSTDIR\MagicC.cer"
  Delete "$INSTDIR\menu.ps1"
  Delete "$INSTDIR\trust.ps1"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
