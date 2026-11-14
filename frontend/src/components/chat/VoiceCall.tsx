import { useRef, useState } from 'react'
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
  onTranscript: (role: 'user' | 'assistant', content: string) => void
  onSendText: (text: string) => void
}) {
  const [state, setState] = useState<RecState>('idle')
  const [statusText, setStatusText] = useState('按住说话，松开发送')
  const [lastTranscript, setLastTranscript] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const recordingRef = useRef(false)

  // 按住说话：pointerdown 开始录音（MediaRecorder opus）
  const startRecording = async () => {
    if (recordingRef.current) return
    try {
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
      const audioBuffer = await actx.decodeAudioData(arrayBuf)
      actx.close()
      const wav = await encodeWav16k(audioBuffer)
      const text = await voiceAsr(wav)
      if (!text.trim()) {
        setState('idle'); setStatusText('没有识别到内容，请再试一次'); return
      }
      setLastTranscript(text)
      await ensureSession()
      onTranscript('user', text)   // 转录落库 + 追加气泡
      onSendText(text)             // 走正常发送链路 → AI 回答 → 自动朗读
      setState('idle')
      setStatusText('已发送，等待回答…（可按住继续说）')
    } catch (e: any) {
      setState('idle')
      setStatusText(e?.message || '语音识别失败，请重试')
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9500, display: 'flex',
      alignItems: 'center', justifyContent: 'center', background: 'rgba(15,23,42,0.4)',
    }}>
      <div style={{
        width: 'min(360px, 92vw)', borderRadius: 16, padding: '20px 24px',
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
    </div>
  )
}
