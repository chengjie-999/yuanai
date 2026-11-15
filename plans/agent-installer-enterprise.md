# Agent 企业级安装流程设计方案（2026-11-06 用户拍板立项，2026-11-07 已落地，仅 EV 证书/静默参数挂账）

## 背景与问题

用户部署后实测暴露三问题：

1. **SmartScreen 拦截**——未签名 exe 浏览器下载（带 MOTW）必弹「Windows 已保护你的电脑」。**已拍板：暂不买证书**（个人备案办不了 EV/OV；个人 IV 证书 SmartScreen 初期仍拦），下载页指引「更多信息→仍要运行」过渡，有营业执照后买 EV 签名根治。
2. **安装流程非企业级**——现状双击裸 exe 直接跑（bootstrap 引导选目录/快捷方式，无安装向导、无协议页、无控制面板卸载）。
3. **崩溃已修（ef82c24）**——`config/settings.py` 把 `.jwt_secret` 写 `__file__` 旁，exe 冻结模式 _MEI 临时目录 FileNotFoundError 启动即崩；修复落数据根（%LOCALAPPDATA%\XiaoYuanAI\），test_frozen_settings.py 回归。

## 核心约束

- **服务器是 Linux（docker），无法动态编译 Inno Setup 安装器**（ISCC 仅 Windows）。
- **T2 免输码链路不能退步**：安装码必须随下载物零输入传递。
- Authenticode 数字签名对**文件内容**签名——**改文件名不影响签名有效性**（关键性质，见方案 A）。
- 用户原则：傻瓜操作（per-user 免 UAC 安装、一键流程）、能不配置就不配置。

## 方案 A（推荐）：固定签名安装器 + 文件名内嵌码

```
下载物 = 一份固定内容的 Inno Setup 安装器（未来签名一次，长期复用）
下载端点 Content-Disposition 文件名 = yuanai-agent-setup-v{版本}_{安装码}.exe
用户双击 → 安装向导（协议勾选/选目录/开始菜单/桌面快捷方式）→ 完成
安装器启动时读 ParamStr(0)（自身文件名）提取 YUAN-XXXX-XXXX-XXXX
→ 写入 %LOCALAPPDATA%\XiaoYuanAI\install_code.txt（或 HKCU 注册表）
→ agent.exe 首启读该码静默注册（复用 register_device）
码丢失（文件名被改/安全软件复制到 temp 改名）→ 现有弹码框兜底
```

**要点**：

- 签名与码解耦：安装器内容固定 → 签名一次长期有效；每用户差异只在文件名 → 服务器下载端点动态 Content-Disposition 即可（现有 download-exe 逻辑微调：发 setup 文件 + 自定义文件名，零新编译）。
- 安装目录：`{localappdata}\Programs\XiaoYuanAI\`（per-user 免 UAC，傻瓜原则；企业惯例同 Chrome/VSCode）；数据仍落 %LOCALAPPDATA%\XiaoYuanAI\（不动）。
- 协议页：安装向导嵌入《用户协议》全文+勾选（C11 合规延伸，安装场景留痕）。
- 卸载：Inno Setup 原生控制面板卸载；卸载前停托盘进程、清快捷方式；**用户数据默认保留**（卸载器勾选「同时删除数据」才删，防误删）。
- 自动更新兼容：现有 yuan --update / 托盘检查更新（裸 exe 覆盖 bin/ 目录）与新安装器并存；安装器只在版本清单标记 installer=true 时用作下载物，更新仍走旧链路。
- 升级：Inno Setup 同 AppId 覆盖安装（保留数据目录与安装码文件）。
- 旧 bootstrap（agent/bootstrap.py）：Inno Setup 承担其职责后退役；旧版裸 exe 用户不受影响（文件名码+弹码框链路保留）。

## 方案 B（备选）：完善现有 bootstrap，不引入 Inno Setup

自绘安装向导（协议/目录/快捷方式）+ 注册表 UninstallString 实现控制面板卸载。零新依赖但「企业级观感」弱于 Inno Setup（无标准安装器体验），不推荐。

## 实施步骤（任务清单）

1. **本地安装 Inno Setup 6**（ISCC 编译链，一次性）
2. **yuanai_agent.iss 模板**：AppId 固定、per-user 安装目录、协议页、开始菜单/桌面快捷方式、卸载器、可选开机自启、`--uninstall` 停进程钩子
3. **安装码传递**：安装器读 ParamStr(0) 提取码 → 写 %LOCALAPPDATA%\XiaoYuanAI\install_code.txt
4. **agent 首启改造**：读码优先级 = install_code.txt > 自身文件名 > 弹码框（tray/main 现逻辑扩展）
5. **云端下载端点**：versions 清单加 installer 标记；download-exe 发 setup（文件名 yuanai-agent-setup-v{版本}_{码}.exe）；自动更新清单排除 installer
6. **测试**：干净机模拟（安装/卸载/升级/码丢失兜底/数据保留/卸载删数据勾选）+ test 回归
7. **打包发布**：build_agent.py 增 setup 产物（ISCC 编译 + sha256 + 版本命名统一）；**等全部完成并完善后再打包上传**（用户拍板）

## SmartScreen 现状过渡（已上线）

下载卡使用指南黄色提示：「如提示『Windows 已保护你的电脑』：点『更多信息』→『仍要运行』即可（软件未签名的正常提示）」。

## 挂账

- EV 证书（有营业执照后）：对安装器 + agent.exe 双签名，SmartScreen 根治
- 安装器多语言/静默安装参数（/SILENT 供企业批量部署，远期）
