import { useState } from 'react'
import { useInstallApp } from '../hooks/useInstallApp'

/** 设置页「安装到桌面」卡（T17，2026-11-18）：
 * - 已 standalone 运行 → 「已安装」状态行
 * - Chrome/Edge（Android/桌面，beforeinstallprompt 已捕获）→ 一键安装按钮
 * - iOS Safari（无安装 API）→ 系统分享三步引导（适配而非对抗）
 * - 微信内（MicroMessenger）→ 引导用系统浏览器打开（微信不支持安装）
 * - 其余（无安装能力浏览器）→ 整卡隐藏
 */
export default function PwaInstallCard() {
  const { canInstall, installed, ios, install } = useInstallApp()
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const isWx = /MicroMessenger/i.test(navigator.userAgent)

  const card: React.CSSProperties = { background: 'var(--bg-primary)', borderRadius: 12, border: '1px solid var(--border)', overflow: 'hidden' }
  const title: React.CSSProperties = { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', padding: '16px 20px', borderBottom: '1px solid var(--border-light)' }
  const sub: React.CSSProperties = { fontSize: 11, color: 'var(--text-muted)', fontWeight: 400 }
  const hint: React.CSSProperties = { fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.9 }
  const muted: React.CSSProperties = { fontSize: 11, color: 'var(--text-muted)' }

  if (!canInstall && !ios && !isWx && !installed) return null

  const doInstall = async () => {
    setBusy(true)
    setMsg('')
    const r = await install()
    setBusy(false)
    if (r === 'installed') setMsg('已安装！以后从桌面图标打开，就是全屏 App。')
    else if (r === 'dismissed') setMsg('已取消。随时可点这里再次安装。')
    else setMsg('当前浏览器暂不支持直接安装，请用 Chrome/Edge 打开本页。')
  }

  return (
    <div style={card}>
      <div style={title}>
        安装到桌面
        <span style={sub}>　像 App 一样全屏打开小元AI（免商店下载，零资质）</span>
      </div>

      {installed ? (
        <div style={{ padding: '14px 20px' }}>
          <div style={{ fontSize: 13, color: 'var(--success)', fontWeight: 600 }}>已安装到桌面</div>
          <div style={{ ...muted, marginTop: 4 }}>从桌面图标打开即为全屏应用；数据与网页端完全同步。</div>
        </div>
      ) : isWx ? (
        <div style={{ padding: '14px 20px' }}>
          <div style={hint}>
            微信内不支持安装到桌面。请点右上角「···」→<b> 在浏览器中打开 </b>（推荐 Chrome/Edge），
            再回到本页安装或按系统提示操作——安装后从桌面图标打开即为全屏 App，
            还可绕开微信浏览器的一些兼容问题。
          </div>
        </div>
      ) : ios ? (
        <div style={{ padding: '14px 20px' }}>
          <div style={hint}>
            1. 点浏览器底部（或右上角）<b>分享按钮</b><br />
            2. 在菜单中选择<b>「添加到主屏幕」</b><br />
            3. 点右上角「添加」——完成。从桌面图标打开即为全屏 App。
          </div>
          <div style={{ ...muted, marginTop: 6 }}>iOS 系统没有「一键安装」接口，走系统分享引导即可。</div>
        </div>
      ) : (
        <div style={{ padding: '14px 20px' }}>
          <div style={hint}>
            安装后从桌面图标打开：全屏无地址栏、状态栏同品牌色，体验和 App 一致；
            消息、设置与网页端完全同步。
          </div>
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
            <button onClick={doInstall} disabled={busy}
              style={{ padding: '8px 18px', borderRadius: 6, border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>
              {busy ? '处理中…' : '安装'}
            </button>
            {msg && <span style={{ fontSize: 12, color: msg.startsWith('已安装') ? 'var(--success)' : 'var(--text-secondary)' }}>{msg}</span>}
          </div>
        </div>
      )}
    </div>
  )
}
