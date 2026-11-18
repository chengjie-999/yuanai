# 手机端 PWA「添加到主屏幕」方案（2026-11-17 立项）

**状态**：✅ P0+P1 已落地（2026-11-18）。P0：`public/manifest.webmanifest` + `public/icons/`（`scripts/gen_pwa_icons.py` PIL 重绘 mascot，192/512/180/maskable）+ `public/sw.js` 最小壳（API 永不缓存、微信内不注册）+ main.tsx 生产注册（updateViaCache none 绕 nginx immutable）。P1：设置页「安装到桌面」卡（`PwaInstallCard`：已安装态/一键安装/iOS 分享引导/微信引导）+ 对话页 `InstallBanner` 安装横幅（拒绝记档不再烦）+ wxTip 文案补安装引导。挂账：push 通知、iOS 角标（未排期）。真机验证路径见 §四。

**背景**：用户评估手机端路线（微信小程序/商店 App 均卡算法备案 3-6 个月行政流程，网页是唯一零资质路线）后拍板登记 PWA——桌面安装后 App 级全屏体验、走系统内核（Chrome/Safari），**彻底绕开微信 X5 的全部适配坑**（长按/偏移/卡住等 T16 所修问题在 PWA 形态下自然消失）。零资质、零商店、ICP 域名直接可用。

**总原则沿用**：「适配而不是对抗」——微信内不启用 Service Worker（微信缓存行为怪异，避让）；iOS 无安装 API 就走系统分享引导（适配），不 hack。

## 一、技术组成

| 项 | 内容 | 文件 |
|---|---|---|
| 1. Manifest | `manifest.webmanifest`：name/short_name=小元AI、start_url=/、display=standalone、theme/background_color 品牌色、lang=zh-CN、图标 192+512 | `frontend/public/` |
| 2. 图标 | 用现有 `public/mascot.svg`（吉祥物唯一事实源）转 PNG 192/512，一次性生成入库 | `scripts/gen_pwa_icons.py`（PIL，与 agent_icon 同套） |
| 3. Service Worker | 最小壳：只缓存 app shell（index.html + hashed 静态资产，stale-while-revalidate）；**硬规则：/api/ 与 /downloads 等动态请求永不缓存**（缓存错 API 响应 = 大事故）；版本化缓存名 + 新版本下次启动生效 | `frontend/public/sw.js` + main.tsx 注册 |
| 4. 微信内跳过 SW | UA MicroMessenger 不注册 SW（微信缓存行为怪异——避让而非对抗） | main.tsx |
| 5. 安装入口 | Android Chrome/Edge：`beforeinstallprompt` → 顶部条/设置页「安装到桌面」按钮；iOS Safari：无安装 API → 「分享 → 添加到主屏幕」图文引导；拒绝后 localStorage 记档不再烦；已 standalone 运行时不显示 | 设置页卡 + 引导条组件 |
| 6. 全屏细节 | standalone 下 safe-area（--safe-top/bottom 已有）、`<meta theme-color>` 状态栏同品牌色 | index.html |

## 二、风险与边界

- SW 注册失败/浏览器不支持 → 静默降级，零影响
- **API 永不进缓存**（code review 重点项）；静态缓存仅限 hashed 资产（index.html 走 no-cache 网络优先）
- 不干扰现有 prerender/SEO 链路；与 nginx 缓存头配合（hashed 资产 immutable 已有）

## 三、执行分层

| 层 | 内容 |
|---|---|
| P0 | Manifest + 图标 + SW 最小壳 + 注册（微信跳过） |
| P1 | 安装提示（Android beforeinstallprompt / iOS 分享引导）+ 设置页「安装到桌面」卡 + 新版本生效提示 |
| 挂账 | push 通知（VAPID + 授权，国内浏览器支持有限）；iOS 桌面图标角标等 |

## 四、验证路径（真机）

1. 安卓 Chrome 打开 → 出现安装提示/菜单「安装应用」→ 桌面图标 → 全屏打开（无地址栏）
2. 断网重开 → 界面壳可看（数据需联网）
3. 发版后 → 新版本在下次启动生效
4. iOS Safari → 分享 → 添加到主屏幕 → 全屏
5. 微信内访问 → 不受影响（不注册 SW），提示用系统浏览器打开（复用 wxTip 条强化引导）

## 五、关联

- 看板 T17；与 T16（长按体系）并行不冲突——PWA 形态下 T16 多数坑自然消失，T16 仍做（微信内用户不变）
- 后端零改动；部署仅需前端构建产物（sw.js/manifest 静态文件）
