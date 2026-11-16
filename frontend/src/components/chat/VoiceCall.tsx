import { useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { createPortal } from 'react-dom'
import { voiceAsr } from '../../api'

/* ============================================================
   语音聊天卡（2026-11-14 半双工重写，DeepSeek 替代火山 RTC）
   用户拍板「语音通话基本残废，直接用 deepseek」：
   按住说话录音 → 松开 → DeepSeek ASR 转文字 → 落库+发送 →
   AI 回答流式 → 自动朗读（DeepSeek TTS 链路）。
   砍掉：RTC SDK/波形/计时/机器人状态协议。
   ============================================================ */

/** 浏览器录音 → 16kHz 16 位 PCM WAV（DeepSeek ASR 要求；OfflineAudioContext 重采样） */
async function encodeWav16k(audioBuffer: AudioBuffer): Promise<Blob> {
  const rate = 16000
  const offline = new OfflineAudioContext(1, Math.ceil(audioBuffer.duration * rate), rate)
  const src = offline.createBufferSource()
  src.buffer = audioBuffer
  src.connect(offline.destination)
  src.start()
  const rendered = await offline.startRendering()
  const samples = rendered.getChannelData(0)
  const buf = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buf)
  const wstr = (off: number, s: string) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)) }
  wstr(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); wstr(8, 'WAVE')
  wstr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
  view.setUint16(22, 1, true); view.setUint32(24, rate, true)
  view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  wstr(36, 'data'); view.setUint32(40, samples.length * 2, true)
  let off = 44
  for (const s of samples) {
    view.setInt16(off, Math.max(-1, Math.min(1, s)) * 0x7fff, true)
    off += 2
  }
  return new Blob([buf], { type: 'audio/wav' })
}

type RecState = 'idle' | 'recording' | 'recognizing'

export default function VoiceCall({ onClose, ensureSession, onTranscript, onSendText }: {
  onClose: () => void
  ensureSession: () => Promise<string>
  onTranscript: (role: 'user' | 'assistant', content: string) => Promise<string | null>
  onSendText: (text: string, msgId: string) => void
}) {
  const [state, setState] = useState<RecState>('idle')
  const [statusText, setStatusText] = useState('按住说话，松开发送')
  const [lastTranscript, setLastTranscript] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const recordingRef = useRef(false)

  // 按住说话：pointerdown 开始录音（MediaRecorder opus）
  const startRecording = async (e: ReactPointerEvent<HTMLButtonElement>) => {
    // 守卫：识别中/录音中不可重按——重按会重置 chunksRef，两段录音数据串扰/重复发送
    // （state!=='idle' 同时挡住「松手到 onstop 之间」的快速重按窗口）
    if (recordingRef.current || state !== 'idle') return
    try {
      // 指针捕获：按住期间事件全部路由到按钮——手机上滑出按钮不丢 pointerup，
      // 桌面按住拖出也不触发 pointerleave 提前停止
      try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* 捕获失败不影响录音 */ }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data) }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        void handleRecordingStop()
      }
      recorderRef.current = recorder
      recordingRef.current = true
      recorder.start()
      setState('recording')
      setStatusText('正在录音，松开结束…')
    } catch {
      setStatusText('麦克风权限被拒绝：请在浏览器地址栏允许麦克风后重试')
    }
  }

  const stopRecording = () => {
    if (!recordingRef.current) return
    recordingRef.current = false
    recorderRef.current?.stop()
    recorderRef.current = null
  }

  // 录音结束 → 解码重采样 → WAV → ASR → 转录落库 + 发送
  const handleRecordingStop = async () => {
    const chunks = chunksRef.current
    if (!chunks.length) { setState('idle'); setStatusText('没有录到声音，请重试'); return }
    setState('recognizing')
    setStatusText('识别中…')
    try {
      const blob = new Blob(chunks, { type: chunks[0].type || 'audio/webm' })
      const arrayBuf = await blob.arrayBuffer()
      const actx = new AudioContext()
      let audioBuffer: AudioBuffer
      try {
        audioBuffer = await actx.decodeAudioData(arrayBuf)
      } finally {
        void actx.close().catch(() => {})  // 成功/失败都释放 AudioContext
      }
      const wav = await encodeWav16k(audioBuffer)
      const text = await voiceAsr(wav)
      if (!text.trim()) {
        setState('idle'); setStatusText('没有识别到内容，请再试一次'); return
      }
      setLastTranscript(text)
      await ensureSession()
      // 转录落库拿 msg_id（不追加 UI——发送链路追加唯一一条用户气泡带同 id；
      // 2026-11-16 修复「消息显示两遍 + AI 输出写进用户消息」根因）
      const r = await onTranscript('user', text)
      if (r === null) { setState('idle'); setStatusText('已保存到通话会话'); return }
      if (r === 'queued') { setState('idle'); setStatusText('AI 正在回答，你说的话会在回答后显示'); return }
      onSendText(text, r)             // 走正常发送链路 → AI 回答 → 自动朗读
      setState('idle')
      setStatusText('已发送，等待回答…（可按住继续说）')
    } catch (e: any) {
      setState('idle')
      setStatusText(e?.message || '语音识别失败，请重试')
    }
  }

  // Portal 挂 body（2026-11-16 用户实测「手机语音页面是偏的」）：安卓微信
  // X5 内核/部分 WebView 的 fixed 定位相对滚动容器偏移——脱离组件树后
  // inset:0 在任何内核下都全屏居中；卡片加安全区 padding + 小屏滚动
  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9500, display: 'flex',
      alignItems: 'center', justifyContent: 'center', background: 'rgba(15,23,42,0.4)',
      paddingTop: 'env(safe-area-inset-top)',
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      <div style={{
        width: 'min(360px, 92vw)', borderRadius: 16, padding: '20px 24px',
        maxHeight: 'calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom) - 24px)',
        overflowY: 'auto',
        background: 'var(--bg-primary)', border: '1px solid var(--border)',
        boxShadow: '0 12px 40px var(--shadow-md)', display: 'flex',
        flexDirection: 'column', alignItems: 'center', gap: 12,
      }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>语音聊天</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.7 }}>
          按住说话，松开发送——你的话会转成文字发给小元，回答自动语音朗读
        </div>

        {/* 按住说话大按钮 */}
        <button
          onPointerDown={startRecording}
          onPointerUp={stopRecording}
          onPointerCancel={stopRecording}
          onPointerLeave={stopRecording}
          aria-label="按住说话"
          style={{
            width: 96, height: 96, borderRadius: '50%', border: 'none', cursor: 'pointer',
            background: state === 'recording'
              ? 'var(--danger)'
              : state === 'recognizing' ? 'var(--bg-tertiary)' : 'var(--accent)',
            color: state === 'recognizing' ? 'var(--text-muted)' : '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'transform 0.12s', touchAction: 'none', userSelect: 'none',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.05)' }}
          onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)' }}
        >
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
        </button>

        <div style={{ fontSize: 13, color: state === 'recording' ? 'var(--danger)' : 'var(--text-secondary)' }}>
          {statusText}
        </div>

        {lastTranscript && (
          <div style={{
            fontSize: 12.5, color: 'var(--text-primary)', background: 'var(--bg-secondary)',
            borderRadius: 8, padding: '6px 10px', maxWidth: '100%', wordBreak: 'break-word',
            maxHeight: 72, overflowY: 'auto',
          }}>{lastTranscript}</div>
        )}

        <button onClick={onClose} aria-label="关闭语音聊天"
          className="yuan-tip" data-tip="关闭"
          style={{
            background: 'none', border: '1px solid var(--border)', cursor: 'pointer',
            color: 'var(--text-secondary)', fontSize: 12.5, borderRadius: 8, padding: '5px 18px',
          }}>
          关闭
        </button>
      </div>
    </div>,
    document.body,
  )
}
