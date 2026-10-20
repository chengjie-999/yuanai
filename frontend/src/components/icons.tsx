/* ============================================================
   共享图标库 — 手写内联 SVG stroke（lucide 风格，零图标库）
   UI 规范：能用图标表达的控件不用文字，语义文字放 title/aria-label
   用法：<SendIcon size={16} /> 随 currentColor 着色
   ============================================================ */

import type { CSSProperties, ReactNode } from 'react'

export interface IconProps {
  size?: number
  style?: CSSProperties
  className?: string
}

const Svg = ({ size = 16, style, className, children }: IconProps & { children: ReactNode }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
    style={style} className={className} aria-hidden="true">{children}</svg>
)

/* 发送（纸飞机） */

/* @提及（群聊定向） */
export const AtSignIcon = (p: IconProps) => <Svg {...p}><circle cx="12" cy="12" r="4" /><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8" /></Svg>

/* 图钉（置顶主对话） */
export const PinIcon = (p: IconProps) => <Svg {...p}><path d="M12 17v5" /><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1z" /></Svg>

/* 喇叭（自动朗读开关） */
export const SpeakerIcon = (p: IconProps) => <Svg {...p}><path d="M11 5 6 9H2v6h4l5 4V5Z" /><path d="M15.54 8.46a5 5 0 0 1 0 7.07" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14" /></Svg>

/* 喇叭静音（自动朗读关闭态） */
export const SpeakerOffIcon = (p: IconProps) => <Svg {...p}><path d="M11 5 6 9H2v6h4l5 4V5Z" /><line x1="22" x2="16" y1="9" y2="15" /><line x1="16" x2="22" y1="9" y2="15" /></Svg>

/* 回形针（上传附件） */
export const PaperclipIcon = (p: IconProps) => <Svg {...p}><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" /></Svg>

/* 左侧栏面板 */

/* 加号（新建） */
export const PlusIcon = (p: IconProps) => <Svg {...p}><path d="M5 12h14" /><path d="M12 5v14" /></Svg>

/* 减号（缩小） */

/* 垃圾桶（删除） */
export const TrashIcon = (p: IconProps) => <Svg {...p}><path d="M3 6h18" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></Svg>

/* 叉（关闭/取消） */
export const XIcon = (p: IconProps) => <Svg {...p}><path d="M18 6 6 18" /><path d="m6 6 12 12" /></Svg>

/* 云（云端模式） */

/* 显示器（本地 Agent） */
export const MonitorIcon = (p: IconProps) => <Svg {...p}><rect width="20" height="14" x="2" y="3" rx="2" /><line x1="8" x2="16" y1="21" y2="21" /><line x1="12" x2="12" y1="17" y2="21" /></Svg>

/* 显示器关闭（离线） */
export const MonitorOffIcon = (p: IconProps) => <Svg {...p}><path d="M17 17H4a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2h16" /><path d="m22 15-5-5" /><path d="m9 18 1 3h4l1-3" /><path d="m2 2 20 20" /></Svg>

/* 终端（Claude Code） */

/* 左/右箭头（收起展开） */
export const ChevronLeftIcon = (p: IconProps) => <Svg {...p}><path d="m15 18-6-6 6-6" /></Svg>
export const ChevronRightIcon = (p: IconProps) => <Svg {...p}><path d="m9 18 6-6-6-6" /></Svg>

/* 对话框（对话） */

/* 盾牌（管理） */

/* 齿轮（设置） */

/* 钥匙（修改密码） */

/* 退出登录 */

/* 首页（房子） */

/* 用户（关于我们） */

/* 登录（进入） */

/* 柱状图（分析面板） */
export const BarChartIcon = (p: IconProps) => <Svg {...p}><line x1="12" x2="12" y1="20" y2="10" /><line x1="18" x2="18" y1="20" y2="4" /><line x1="6" x2="6" y1="20" y2="16" /></Svg>

/* 机器人（自动化面板） */
export const BotIcon = (p: IconProps) => <Svg {...p}><path d="M12 8V4H8" /><rect width="16" height="12" x="4" y="8" rx="2" /><path d="M2 14h2" /><path d="M20 14h2" /><path d="M15 13v2" /><path d="M9 13v2" /></Svg>

/* 剪贴板（面板通用） */
export const ClipboardIcon = (p: IconProps) => <Svg {...p}><rect width="8" height="4" x="8" y="2" rx="1" ry="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /></Svg>

/* 返回（左箭头） */
export const ArrowLeftIcon = (p: IconProps) => <Svg {...p}><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></Svg>

/* 对勾（保存/确认） */
export const CheckIcon = (p: IconProps) => <Svg {...p}><polyline points="20 6 9 17 4 12" /></Svg>

/* 麦克风（语音） */

/* 下载 */
export const DownloadIcon = (p: IconProps) => <Svg {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></Svg>

/* 添加用户 */

/* 解锁（解冻/解绑） */

/* 雪花（冻结） */

/* 刷新 */
export const RefreshIcon = (p: IconProps) => <Svg {...p}><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" /></Svg>

/* 搜索 */
export const SearchIcon = (p: IconProps) => <Svg {...p}><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></Svg>

/* 上传 */
export const UploadIcon = (p: IconProps) => <Svg {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" x2="12" y1="3" y2="15" /></Svg>

/* 复制 */

/* 链接（绑定） */
export const LinkIcon = (p: IconProps) => <Svg {...p}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></Svg>

/* 断开链接（解绑） */

/* 包裹（拖拽上传占位） */
export const PackageIcon = (p: IconProps) => <Svg {...p}><path d="m7.5 4.27 9 5.15" /><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" /><path d="m3.3 7 8.7 5 8.7-5" /><path d="M12 22V12" /></Svg>

/* 下/上箭头（折叠展开/更多） */
export const ChevronDownIcon = (p: IconProps) => <Svg {...p}><path d="m6 9 6 6 6-6" /></Svg>
export const ChevronUpIcon = (p: IconProps) => <Svg {...p}><path d="m18 15-6-6-6 6" /></Svg>
export const ArrowDownIcon = (p: IconProps) => <Svg {...p}><path d="M12 5v14" /><path d="m19 12-7 7-7-7" /></Svg>

/* 播放/停止（监控启停） */

/* 文件夹/文件 */
export const FolderIcon = (p: IconProps) => <Svg {...p}><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" /></Svg>
export const FileIcon = (p: IconProps) => <Svg {...p}><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /></Svg>

/* 趋势（环比涨跌） */
export const TrendingUpIcon = (p: IconProps) => <Svg {...p}><polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" /></Svg>
export const TrendingDownIcon = (p: IconProps) => <Svg {...p}><polyline points="22 17 13.5 8.5 8.5 13.5 2 7" /><polyline points="16 17 22 17 22 11" /></Svg>

/* 警告三角 */
export const AlertIcon = (p: IconProps) => <Svg {...p}><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><line x1="12" x2="12" y1="9" y2="13" /><line x1="12" x2="12.01" y1="17" y2="17" /></Svg>

/* 实心圆点（监控中） */
export const CircleDotIcon = (p: IconProps) => <Svg {...p}><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" /></Svg>
export const CircleIcon = (p: IconProps) => <Svg {...p}><circle cx="12" cy="12" r="10" /></Svg>

/* 加载中（旋转，配合 animation: spin 使用） */
export const LoaderIcon = (p: IconProps) => <Svg {...p}><path d="M21 12a9 9 0 1 1-6.219-8.56" /></Svg>

/* 书籍（知识库） */
export const BookIcon = (p: IconProps) => <Svg {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></Svg>

/* 星球（知识星球） */
export const PlanetIcon = (p: IconProps) => <Svg {...p}><circle cx="12" cy="12" r="10" /><path d="M14.8 9A21.1 21.1 0 0 0 12 3 21.1 21.1 0 0 0 9.2 9" /><path d="M14.8 15A21.1 21.1 0 0 1 12 21 21.1 21.1 0 0 1 9.2 15" /><path d="M3 15h18" /><path d="M3 9h18" /></Svg>

/* 思维导图（分支树） */

/* 笔记（文档） */
export const NoteIcon = (p: IconProps) => <Svg {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="8" x2="16" y1="13" y2="13" /><line x1="8" x2="16" y1="17" y2="17" /></Svg>

/* 铅笔（编辑） */
export const EditIcon = (p: IconProps) => <Svg {...p}><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" /></Svg>

/* 银河（螺旋星系 — 知识星球一级） */
export const GalaxyIcon = (p: IconProps) => <Svg {...p}><path d="M12 12c-1.5-2.5-3.5-3.5-6-3.5 0 2.5 1 4.5 3 5.5-2 1-3 3-3 5.5 2.5 0 4.5-1 6-3.5 1.5 2.5 3.5 3.5 6 3.5 0-2.5-1-4.5-3-5.5 2-1 3-3 3-5.5-2.5 0-4.5 1-6 3.5z" /><circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" /></Svg>

/* 恒星（四芒星 — 知识星球二级：导图） */
export const StarIcon = (p: IconProps) => <Svg {...p}><path d="M12 2l2.2 7.8L22 12l-7.8 2.2L12 22l-2.2-7.8L2 12l7.8-2.2z" /><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" /></Svg>

/* 行星（带光环 — 知识星球三级：笔记） */
export const RingPlanetIcon = (p: IconProps) => <Svg {...p}><circle cx="12" cy="12" r="5.2" /><ellipse cx="12" cy="12" rx="9.5" ry="3.2" transform="rotate(-18 12 12)" /></Svg>

/* 卫星（小月亮 — 知识星球三级：手改笔记/自由笔记） */
export const MoonIcon = (p: IconProps) => <Svg {...p}><path d="M12 3a6.4 6.4 0 0 0 9 9 9 9 0 1 1-9-9Z" /></Svg>

/* 魔棒（AI 生成） */
export const WandIcon = (p: IconProps) => <Svg {...p}><path d="m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72Z" /><path d="m14 7 3 3" /><path d="M5 6v4" /><path d="M19 14v4" /><path d="M10 2v2" /><path d="M7 8H3" /><path d="M21 16h-4" /><path d="M11 3H9" /></Svg>
