import { useEffect, useRef, useState } from 'react'
import { voiceStart, voiceEnd } from '../../api'

type CallStatus = 'connecting' | 'active' | 'error'

// 语音通话悬浮卡片：桌面居中卡片，手机全屏；挂断/关闭时自动 StopVoiceChat + 退房 + 销毁引擎
export default function VoiceCall({ onClose }: { onClose: () => void }) {
  const [status, setStatus] = useState<CallStatus>('connecting')
  const [errorMsg, setErrorMsg] = useState('')
  const [seconds, setSeconds] = useState(0)
  const [botVolume, setBotVolume] = useState(0)   // AI 说话音量 0-255
  const [micVolume, setMicVolume] = useState(0)   // 麦克风音量 0-255
  const credsRef = useRef<{ room_id: string; task_id: string } | null>(null)

  useEffect(() => {
    let disposed = false
    let engine: any = null

    const teardown = async () => {
      // 停止任务 + 退房 + 销毁引擎（幂等，unmount 时由 React 自动调用）
      if (credsRef.current) {
        voiceEnd(credsRef.current.room_id, credsRef.current.task_id)
        credsRef.current = null
      }
      if (engine) {
        try { await engine.leaveRoom() } catch { /* 忽略 */ }
        try { engine.destroy() } catch { /* 忽略 */ }
        engine = null
      }
    }

    const connect = async () => {
      try {
        const creds = await voiceStart()
        credsRef.current = { room_id: creds.room_id, task_id: creds.task_id }

        // 动态加载 RTC SDK（按需分包，不进主 bundle）
        const { default: VERTC } = await import('@volcengine/rtc')
        engine = VERTC.createEngine(creds.app_id)

        // 机器人入房发布音频流 = 通话真正建立
        engine.on(VERTC.events.onUserPublishStream, (e: any) => {
          if (e.mediaType === 1) setStatus('active')  // MediaType.AUDIO
        })
        engine.on(VERTC.events.onError, (e: any) => {
          console.error('RTC error:', e)
          if (!disposed) { setStatus('error'); setErrorMsg(`RTC 错误：${e.errorCode || e.message || '未知错误'}`) }
        })
        // 音量回调 → 波形动画（本地麦克风 + 远端机器人）
        engine.enableAudioPropertiesReport({ interval: 200 })
        engine.on(VERTC.events.onLocalAudioPropertiesReport, (infos: any[]) => {
          setMicVolume(infos?.[0]?.audioPropertiesInfo?.linearVolume ?? 0)
        })
        engine.on(VERTC.events.onRemoteAudioPropertiesReport, (infos: any[]) => {
          setBotVolume(infos?.[0]?.audioPropertiesInfo?.linearVolume ?? 0)
        })

        await engine.joinRoom(creds.rtc_token, creds.room_id, { userId: creds.user_id },
          { isAutoPublish: true, isAutoSubscribeAudio: true })
        await engine.startAudioCapture()
        if (!disposed) setStatus('active')
      } catch (err: any) {
        console.error('语音通话连接失败:', err)
        if (!disposed) { setStatus('error'); setErrorMsg(err?.message || '连接失败，请重试') }
      }
    }
    connect()

    return () => { disposed = true; teardown() }
  }, [])

  // 通话计时
  useEffect(() => {
    if (status !== 'active') return
    const t = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [status])

  // Esc 挂断
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  const volume = Math.max(botVolume, micVolume)
  const bars = 16

  return (
    <>
      <style>{`
        .voice-call-card {
          position: fixed; left: 50%; top: 50%; transform: translate(-50%, -50%);
          width: 320px; border-radius: 16px; z-index: 9999;
          background: var(--bg-primary); border: 1px solid var(--border);
          box-shadow: 0 12px 40px var(--shadow-md);
          display: flex; flex-direction: column; align-items: center;
          padding: 28px 20px 24px; gap: 14px;
        }
        .voice-call-bars { display: flex; align-items: center; gap: 3px; height: 44px; }
        .voice-call-bar {
          width: 4px; border-radius: 2px; background: var(--success);
          transition: height 0.12s ease;
        }
        .voice-call-bar.idle { animation: voicePulse 1.4s ease-in-out infinite; }
        @keyframes voicePulse {
          0%, 100% { opacity: 0.35; } 50% { opacity: 1; }
        }
        @media (max-width: 768px) {
          .voice-call-card { width: 100vw; height: 100vh; max-height: 100vh; inset: 0;
            top: 0; left: 0; transform: none; border-radius: 0; border: none; justify-content: center; }
        }
      `}</style>
      <div className="voice-call-card" onClick={(e) => e.stopPropagation()}>
        <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-primary)' }}>小元AI 语音通话</div>

        {status === 'connecting' && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', fontSize: 13 }}>
              <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid var(--accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              正在连接…
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>请允许浏览器使用麦克风</div>
          </>
        )}

        {status === 'error' && (
          <>
            <div style={{ fontSize: 13, color: 'var(--danger)', textAlign: 'center', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {errorMsg}
            </div>
            <button onClick={onClose} className="btn btn-outline" style={{ marginTop: 6 }}>关闭</button>
          </>
        )}

        {status === 'active' && (
          <>
            <div className="voice-call-bars">
              {Array.from({ length: bars }).map((_, i) => {
                // 相位错开让波形更自然；音量低时进入呼吸动画
                const idle = volume < 8
                const phase = 0.55 + 0.45 * (((i * 53) % 11) / 11)
                const h = idle ? 8 + 10 * (((i * 53) % 11) / 11) : 6 + Math.min(34, (volume / 255) * 34 * phase)
                return <div key={i} className={`voice-call-bar${idle ? ' idle' : ''}`}
                  style={{ height: h, animationDelay: `${(i * 0.09) % 1.4}s` }} />
              })}
            </div>
            <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
              {fmt(seconds)}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {botVolume >= 8 ? '小元AI 正在说话…' : '我在听，请说话'}
            </div>
            <button onClick={onClose} title="挂断" aria-label="挂断"
              style={{
                width: 56, height: 56, borderRadius: '50%', border: 'none', cursor: 'pointer',
                background: 'var(--danger)', color: '#fff', display: 'flex', alignItems: 'center',
                justifyContent: 'center', marginTop: 8, transition: 'transform 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7 2 2 0 0 1 1.72 2v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.42 19.42 0 0 1-3.33-2.67m-2.67-3.34a19.79 19.79 0 0 1-3.07-8.63A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91" />
                <line x1="22" y1="2" x2="2" y2="22" />
              </svg>
            </button>
          </>
        )}
      </div>
    </>
  )
}
