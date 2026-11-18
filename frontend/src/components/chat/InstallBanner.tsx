import { useState } from 'react'
import { useInstallApp, dismissInstallPrompt } from '../../hooks/useInstallApp'

/** PWA 安装横幅（T17，2026-11-18）：Chrome/Edge 捕获到 beforeinstallprompt
 * 且用户未拒绝过时，在对话页顶部提示「安装到桌面」；点 ✕ 记档不再烦
 * （设置页「安装到桌面」卡随时可再装）。iOS 无安装 API 走分享引导，
 * 不弹此横幅（无法一键安装，弹了也没用）。
 */
export default function InstallBanner() {
  const { canInstall, installed, ios, dismissed, install } = useInstallApp()
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  // 已安装 / iOS（走分享引导）/ 已拒绝 / 尚无安装事件 → 不显示
  if (installed || ios || dismissed || !canInstall) return null

  const doInstall = async () => {
    setBusy(true)
    setMsg('')
    const r = await install()
    setBusy(false)
    if (r === 'installed') setMsg('已安装！从桌面图标打开就是全屏 App。')
    else if (r === 'dismissed') dismissInstallPrompt()
  }

  return (
    <div style={{
      margin: '8px 12px 0', padding: '8px 12px', borderRadius: 8,
      background: 'var(--accent-soft)', border: '1px solid var(--accent)',
      fontSize: 12.5, color: 'var(--text-primary)', display: 'flex',
      alignItems: 'center', gap: 8, flexShrink: 0,
    }}>
      <span style={{ flex: 1, lineHeight: 1.6 }}>
        {msg || '把小元AI 装到桌面，像 App 一样全屏打开'}
      </span>
      {!msg && (
        <button onClick={doInstall} disabled={busy}
          style={{ background: 'var(--accent)', color: '#fff', border: 'none',
                   borderRadius: 6, padding: '4px 12px', fontSize: 12.5,
                   fontWeight: 600, cursor: 'pointer', flexShrink: 0 }}>
          {busy ? '…' : '安装'}
        </button>
      )}
      <button onClick={dismissInstallPrompt} aria-label="暂时不要"
        style={{ background: 'none', border: 'none', cursor: 'pointer',
                 color: 'var(--text-muted)', fontSize: 12, flexShrink: 0, padding: '2px 6px' }}>
        暂不
      </button>
    </div>
  )
}
