; 小元AI Agent 企业级安装器（2026-11-07 立项，设计见 plans/agent-installer-enterprise.md）
;
; 编译（build_agent.py 自动执行）：
;   ISCC /DAppVersion=20261106 /DExeSource=<abs>\dist\yuanai-agent.exe yuanai_agent.iss
;
; 核心设计：
; - AppId 固定 + per-user 免 UAC（{localappdata}\XiaoYuanAI，与数据根同地）
; - 免输码衔接：安装器读自身文件名（ParamStr(0)）提取安装码 → 写
;   %LOCALAPPDATA%\XiaoYuanAI\install_code.txt → agent 首启静默注册（弹码框兜底）
;   签名对文件名改动免疫（Authenticode 签的是内容），下载端点动态文件名带码
; - 协议页（《用户协议》全文，C11 安装场景留痕）；卸载停托盘进程、
;   数据默认保留（确认后才删）

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define MyAppName "小元AI Agent"
#define MyAppPublisher "小元AI"

[Setup]
; AppId 固定 GUID：升级=覆盖安装（同 AppId 不重装不清数据）。
; 注意：AppId 的花括号内嵌 ISPP 宏会编译失败（{{#X} 两种闭合都实测过），
; GUID 必须硬编码
AppId={{7E4A0F2E-2B6C-4D4E-9A5C-A1B2C3D4E5F6}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} v{#AppVersion}
AppPublisher={#MyAppPublisher}
; 版本号是 YYYYMMDD（非法 Windows 四段式），VersionInfo 用默认 1.0.0.0；
; 展示版本在 AppVerName/卸载清单里
; per-user 免 UAC：非管理员也能装（傻瓜原则）；不触发安装器复制到 temp，
; ParamStr(0) 保持真实文件名（安装码提取依赖这一点）
PrivilegesRequired=lowest
DefaultDirName={localappdata}\XiaoYuanAI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\bin\小元AI Agent.exe
UninstallDisplayName={#MyAppName} v{#AppVersion}
; 协议页：docs/agreements/用户协议.txt（build_agent.py 由 .md 生成）；
; ..\.. 两级上跳=仓库根，无论相对脚本目录还是 cwd 解析都正确
LicenseFile=..\..\docs\agreements\用户协议.txt
OutputDir=..\..\dist
OutputBaseFilename=yuanai-agent-setup-tmp
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\agent_icon.ico
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Files]
; 裸 exe（PyInstaller onefile 产物）→ 安装为固定名（安装码不再依赖 exe 文件名，
; 走 install_code.txt；升级覆盖同名文件）
Source: "{#ExeSource}"; DestDir: "{app}\bin"; DestName: "小元AI Agent.exe"; \
  Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\bin\小元AI Agent.exe"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\bin\小元AI Agent.exe"; \
  Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "附加任务:"

[Run]
; 安装完直接启动（默认勾选；托盘常驻形态）
Filename: "{app}\bin\小元AI Agent.exe"; Description: "立即运行 {#MyAppName}(&R)"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载前停掉常驻托盘进程（杀进程失败不阻断卸载）
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM 小元AI Agent.exe"; \
  Flags: runhidden; RunOnceId: "StopTray"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\bin"
Type: files; Name: "{app}\install_code.txt"

[Code]
{ 安装码提取：setup 文件名 = yuanai-agent-setup-v[版本]_YUAN-XXXX-XXXX-XXXX.exe
  读 ParamStr(0)（安装器被复制到临时目录时为空——此时由弹码框兜底，不影响安装）
  注意：Pascal 注释花括号内不能再出现花括号字符（曾把注释提前截断） }
function ExtractInstallCode(): string;
var
  fname, code: string;
  p, i, n: Integer;
  c: Char;
begin
  Result := '';
  fname := UpperCase(ExtractFileName(ParamStr(0)));
  p := Pos('_YUAN-', fname);
  if p = 0 then
    Exit;
  code := Copy(fname, p + 1, Length(fname) - p);
  { 去扩展名：正常双击是 .exe；Inno 会把安装器复制到临时目录执行
    （is-XXXX.tmp 下同名 .tmp）——按第一个点截断两者通吃 }
  p := Pos('.', code);
  if p > 0 then
    code := Copy(code, 1, p - 1);
  { 校验：YUAN-XXXX-XXXX-XXXX（长度 8-40，仅大写字母/数字/连字符） }
  n := Length(code);
  if (n < 8) or (n > 40) then
    Exit;
  for i := 1 to n do
  begin
    c := code[i];
    if not (((c >= 'A') and (c <= 'Z')) or ((c >= '0') and (c <= '9')) or (c = '-')) then
      Exit;
  end;
  Result := code;
end;

{ 安装完成阶段：把安装码写进数据根 install_code.txt（agent 首启静默注册后
  自行清理；文件写入失败静默——弹码框兜底，不阻断安装） }
procedure CurStepChanged(CurStep: TSetupStep);
var
  code: string;
  dataRoot: string;
begin
  if CurStep <> ssPostInstall then
    Exit;
  Log('install-code: ParamStr(0)=' + ParamStr(0));
  code := ExtractInstallCode();
  Log('install-code: extracted=' + code);
  if code = '' then
    Exit;
  dataRoot := ExpandConstant('{localappdata}\XiaoYuanAI');
  Log('install-code: dataRoot=' + dataRoot);
  try
    ForceDirectories(dataRoot);
    SaveStringToFile(dataRoot + '\install_code.txt', code, False);
    Log('install-code: written');
  except
    Log('install-code: write failed');
  end;
end;

{ 卸载时询问是否连数据一起删（默认保留——用户数据不因卸载丢失，傻瓜设计）；
  静默卸载（/VERYSILENT）不弹框也不删数据（自动化测试/企业批量场景） }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  dataRoot: string;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  if UninstallSilent() then
    Exit;
  dataRoot := ExpandConstant('{localappdata}\XiaoYuanAI');
  if DirExists(dataRoot) then
  begin
    if MsgBox('卸载时是否同时删除本机数据？' + #13#10 +
              '（包括设备身份/配置/使用记录；选择「否」则数据保留，' +
              '重新安装后自动恢复）', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(dataRoot, True, True, True);
    end;
  end;
end;
