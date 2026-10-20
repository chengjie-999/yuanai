import { useEffect, useRef, useState } from 'react'
import { voiceStart, voiceEnd } from '../../api'

type CallStatus = 'connecting' | 'active' | 'error'

// 机器人状态（来自 RTC 数据流 conv 消息，AGENT_BRIEF 枚举）
const AGENT_STATE_TEXT: Record<number, string> = {
  0: '待机中',
  1: '我在听，请说话',
  2: '小元AI 正在思考…',
  3: '小元AI 正在说话…',
  4: '已打断',
  5: '本轮结束',
}

interface TranscriptItem { role: 'user' | 'assistant'; text: string }

/** TLV 解析：| type(4B) | length(4B 大端) | value |（官方 rtc-aigc-demo 协议） */
function tlv2String(buf: ArrayBuffer): { type: string; value: string } {
  const typeBytes = new Uint8Array(buf, 0, 4)
  const lenBytes = new Uint8Array(buf, 4, 4)
  let type = ''
  for (let i = 0; i < 4; i++) type += String.fromCharCode(typeBytes[i])
  const len = (lenBytes[0] << 24) | (lenBytes[1] << 16) | (lenBytes[2] << 8) | lenBytes[3]
  const value = new TextDecoder().decode(new Uint8Array(buf, 8, len))
  return { type, value }
}

/** TLV 编码（反向）：给机器人发命令用 */
function string2tlv(str: string, type: string): ArrayBuffer {
  const typeBuf = new Uint8Array(4)
  for (let i = 0; i < 4; i++) typeBuf[i] = type.charCodeAt(i)
  const valBuf = new TextEncoder().encode(str)
  const buf = new Uint8Array(8 + valBuf.length)
  buf.set(typeBuf, 0)
  const len = valBuf.length
  buf[4] = (len >> 24) & 0xff
  buf[5] = (len >> 16) & 0xff
  buf[6] = (len >> 8) & 0xff
  buf[7] = len & 0xff
  buf.set(valBuf, 8)
  return buf.buffer
}

// 语音通话悬浮卡片：桌面居中卡片，手机全屏；挂断/关闭时自动 StopVoiceChat + 退房 + 销毁引擎。
// 机器人通过 RTC 数据流实时推送字幕（subv）与状态（conv），最终字幕落入聊天会话。
// 「朗读文字回复」开启时，通话期间聊天产生的 AI 文字回复会经 ctrl 命令让机器人朗读。
export default function VoiceCall({ onClose, ensureSession, onTranscript, lastAssistantText, entMode }: {
  onClose: () => void
  ensureSession: () => Promise<string>
  onTranscript: (role: 'user' | 'assistant', content: string) => void
  lastAssistantText: string
  entMode: boolean
}) {
  const [status, setStatus] = useState<CallStatus>('connecting')
  const [errorMsg, setErrorMsg] = useState('')
  const [seconds, setSeconds] = useState(0)
  const [botVolume, setBotVolume] = useState(0)   // AI 说话音量 0-255
  const [micVolume, setMicVolume] = useState(0)   // 麦克风音量 0-255
  const [agentState, setAgentState] = useState(1) // conv 状态码（默认在听）
  const [agentDesc, setAgentDesc] = useState('')  // conv 描述（可能含错误信息）
  const [transcript, setTranscript] = useState<TranscriptItem[]>([])
  const [speakTextReply, setSpeakTextReply] = useState(false)  // 朗读文字回复开关（默认关，避免与机器人语音重叠）
  const credsRef = useRef<{ room_id: string; task_id: string; user_id: string } | null>(null)
  const engineRef = useRef<any>(null)
  const transcriptEndRef = useRef<HTMLDivElement>(null)
  // 记录已朗读过的文字（初始化为挂载时的最新值，避免重播历史回复）
  const lastSpokenRef = useRef(lastAssistantText)
  // 始终指向最新 props（mount effect 内闭包不冻结首帧值）
  const propsRef = useRef({ ensureSession, onTranscript, entMode })
  propsRef.current = { ensureSession, onTranscript, entMode }

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
        engineRef.current = null  // 同步清理，避免朗读 effect 读到已销毁引擎
      }
    }

    // 最终字幕：卡片展示 + 通知父级（父级负责 UI 追加与持久化，走 propsRef 拿最新回调）
    const handleFinalTranscript = (role: 'user' | 'assistant', text: string) => {
      if (!text.trim()) return
      setTranscript((prev) => [...prev, { role, text }])
      propsRef.current.onTranscript(role, text)
    }

    const connect = async () => {
      // 通话开始即解析会话（欢迎页自动新建并切进聊天页），后续转录由父级锚定该会话
      propsRef.current.ensureSession().catch(() => { /* 会话解析失败仅影响转录落库 */ })
      try {
        // E5：娱乐模式通话走娱乐人设（后端同通道换 SystemMessages）
        const creds = await voiceStart(propsRef.current.entMode ? 'entertainment' : 'work')
        credsRef.current = { room_id: creds.room_id, task_id: creds.task_id, user_id: creds.user_id }
        // connecting 阶段挂断：此时 teardown 已跑过但 credsRef 为空，重跑一次停掉机器人任务
        if (disposed) { await teardown(); return }

        // 动态加载 RTC SDK（按需分包，不进主 bundle）
        const { default: VERTC, RoomProfileType } = await import('@volcengine/rtc')
        if (disposed) { await teardown(); return }
        engine = VERTC.createEngine(creds.app_id)
        engineRef.current = engine

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
        // 机器人数据流：字幕（subv）+ 状态（conv）——官方 rtc-aigc-demo 协议
        engine.on(VERTC.events.onRoomBinaryMessageReceived, (e: any) => {
          if (disposed) return
          try {
            const { type, value } = tlv2String(e.message as ArrayBuffer)
            if (type === 'subv') {
              const data = JSON.parse(value)?.data?.[0]
              if (!data?.text) return
              const role = data.userId === creds.user_id ? 'user' : 'assistant'
              if (data.definite) {
                handleFinalTranscript(role, data.text)
              }
            } else if (type === 'conv') {
              const stage = JSON.parse(value)?.Stage
              if (stage) {
                setAgentState(stage.Code ?? 0)
                setAgentDesc(typeof stage.Description === 'string' ? stage.Description : '')
              }
            }
          } catch (err) {
            console.warn('语音数据流解析失败:', err)
          }
        })

        await engine.joinRoom(creds.rtc_token, creds.room_id, { userId: creds.user_id },
          { isAutoPublish: true, isAutoSubscribeAudio: true, roomProfileType: RoomProfileType.chat })
        if (disposed) { await teardown(); return }
        await engine.startAudioCapture()
        if (disposed) { await teardown(); return }
        setStatus('active')
      } catch (err: any) {
        console.error('语音通话连接失败:', err)
        if (!disposed) { setStatus('error'); setErrorMsg(err?.message || '连接失败，请重试') }
      }
    }
    connect()

    return () => { disposed = true; teardown() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 通话计时
  useEffect(() => {
    if (status !== 'active') return
    const t = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [status])

  // 字幕自动滚动
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  // Esc 挂断
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // 朗读文字回复：通话期间聊天产生的 AI 文字回复，经 ctrl 命令让机器人朗读（官方协议）
  useEffect(() => {
    if (!speakTextReply || status !== 'active') return
    if (!lastAssistantText || lastAssistantText === lastSpokenRef.current) return
    const eng = engineRef.current
    const creds = credsRef.current
    if (!eng || !creds) return  // 引擎未就绪：不推进标记，就绪后可补发
    try {
      eng.sendUserBinaryMessage(
        `voiceChat_${creds.task_id}`,
        string2tlv(JSON.stringify({
          Command: 'ExternalTextToSpeech',
          InterruptMode: 0,
          Message: lastAssistantText,
        }), 'ctrl'),
      )
      // 发送成功才推进，避免失败消息被永久消费
      lastSpokenRef.current = lastAssistantText
    } catch (err) {
      console.warn('发送朗读命令失败:', err)
    }
  }, [lastAssistantText, speakTextReply, status])

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  const volume = Math.max(botVolume, micVolume)
  const bars = 16
  const stateText = status === 'active' ? AGENT_STATE_TEXT[agentState] || '通话中' : ''

  return (
    <>
      <style>{`
        .voice-call-card {
          position: fixed; left: 50%; top: 50%; transform: translate(-50%, -50%);
          width: 340px; border-radius: 16px; z-index: 9999;
          background: var(--bg-primary); border: 1px solid var(--border);
          box-shadow: 0 12px 40px var(--shadow-md);
          display: flex; flex-direction: column; align-items: center;
          padding: 24px 18px 20px; gap: 10px;
        }
        .voice-call-bars { display: flex; align-items: center; gap: 3px; height: 36px; }
        .voice-call-bar {
          width: 4px; border-radius: 2px; background: var(--success);
          transition: height 0.12s ease;
        }
        .voice-call-bar.idle { animation: voicePulse 1.4s ease-in-out infinite; }
        @keyframes voicePulse {
          0%, 100% { opacity: 0.35; } 50% { opacity: 1; }
        }
        .voice-transcript {
          width: 100%; flex: 1; min-height: 0; max-height: 180px; overflow-y: auto;
          display: flex; flex-direction: column; gap: 6px; padding: 4px 2px;
          text-align: left;
        }
        .voice-transcript-item {
          font-size: 12px; line-height: 1.5; border-radius: 8px; padding: 5px 9px;
          max-width: 92%; word-break: break-word;
        }
        .voice-transcript-item.user {
          align-self: flex-end; background: var(--accent); color: #fff;
        }
        .voice-transcript-item.assistant {
          align-self: flex-start; background: var(--bg-tertiary); color: var(--text-primary);
        }
        @media (max-width: 768px) {
          .voice-call-card { width: 100vw; height: 100dvh; max-height: 100dvh; inset: 0;
            top: 0; left: 0; transform: none; border-radius: 0; border: none; justify-content: flex-start;
            padding-top: 12vh; }
          .voice-transcript { max-height: 40vh; }
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
            <div className="voice-transcript">
              {transcript.map((item, i) => (
                <div key={i} className={`voice-transcript-item ${item.role}`}>{item.text}</div>
              ))}
              <div ref={transcriptEndRef} />
            </div>
            <div className="voice-call-bars">
              {Array.from({ length: bars }).map((_, i) => {
                // 相位错开让波形更自然；音量低时进入呼吸动画
                const idle = volume < 8
                const phase = 0.55 + 0.45 * (((i * 53) % 11) / 11)
                const h = idle ? 8 + 10 * (((i * 53) % 11) / 11) : 6 + Math.min(30, (volume / 255) * 30 * phase)
                return <div key={i} className={`voice-call-bar${idle ? ' idle' : ''}`}
                  style={{ height: h, animationDelay: `${(i * 0.09) % 1.4}s` }} />
              })}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{stateText}</div>
            {agentDesc && agentDesc !== stateText && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: '100%', wordBreak: 'break-word' }}>{agentDesc}</div>
            )}
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer', userSelect: 'none' }}
              title="通话期间在聊天里发送文字，AI 的回复会用语音读出来">
              <input type="checkbox" checked={speakTextReply}
                onChange={(e) => setSpeakTextReply(e.target.checked)}
                style={{ cursor: 'pointer', accentColor: 'var(--accent)' }} />
              朗读文字回复
            </label>
            <div style={{ fontSize: 22, fontWeight: 600, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
              {fmt(seconds)}
            </div>
            <button onClick={onClose} title="挂断" aria-label="挂断"
              style={{
                width: 56, height: 56, borderRadius: '50%', border: 'none', cursor: 'pointer',
                background: 'var(--danger)', color: '#fff', display: 'flex', alignItems: 'center',
                justifyContent: 'center', marginTop: 4, transition: 'transform 0.15s', flexShrink: 0,
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
