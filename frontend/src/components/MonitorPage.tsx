import { useState, useEffect, useRef, useCallback } from 'react'
import { getMonitorScreenshot, getMonitors, API_BASE } from '../api'

export default function MonitorPage() {
  const [screenshot, setScreenshot] = useState<string | null>(null)
  const [monitors, setMonitors] = useState<{ monitor: number; width: number; height: number; label: string }[]>([])
  const [currentMonitor, setCurrentMonitor] = useState(0)
  const [info, setInfo] = useState('')
  const [liveMode, setLiveMode] = useState(true)
  const [frameSize, setFrameSize] = useState('')
  const [streamInterval, setStreamInterval] = useState(100)
  const esRef = useRef<EventSource | null>(null)
  const frameCountRef = useRef(0)
  const lastTimeRef = useRef(Date.now())

  const stopLive = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    setLiveMode(false)
    setFrameSize('')
  }, [])

  const startLive = useCallback(() => {
    if (esRef.current) esRef.current.close()
    const token = localStorage.getItem('token') || ''
    const url = `${API_BASE}/monitor/stream?monitor=${currentMonitor}&interval=${streamInterval / 1000}&token=${token}`
    const es = new EventSource(url)
    esRef.current = es
    frameCountRef.current = 0
    lastTimeRef.current = Date.now()

    es.onmessage = (e) => {
      if (e.data.startsWith('ERROR:')) {
        setInfo(e.data.slice(6))
        return
      }
      setScreenshot(e.data)

      frameCountRef.current += 1
      const now = Date.now()
      const elapsed = (now - lastTimeRef.current) / 1000
      if (elapsed >= 2) {
        const fps = (frameCountRef.current / elapsed).toFixed(1)
        const bytes = (e.data.length * 0.75) | 0
        const sizeStr = bytes > 1024 * 1024
          ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
          : `${(bytes / 1024).toFixed(0)} KB`
        setFrameSize(`${fps} fps · ${sizeStr}/帧`)
        frameCountRef.current = 0
        lastTimeRef.current = now
      }
    }

    es.onerror = () => {
      setInfo('实时流连接断开')
      setLiveMode(false)
      es.close()
      esRef.current = null
    }
  }, [currentMonitor, streamInterval, stopLive])

  const toggleLive = () => {
    if (liveMode) {
      stopLive()
    } else {
      setLiveMode(true)
    }
  }

  const fetchScreenshot = useCallback(async () => {
    const data = await getMonitorScreenshot(currentMonitor)
    if (data.status === 'ok' && data.screenshot) {
      setScreenshot(data.screenshot)
      setInfo(`${data.width}×${data.height}`)
    } else {
      setInfo(data.detail || '截图失败')
    }
  }, [currentMonitor])

  const fetchMonitors = useCallback(async () => {
    const data = await getMonitors()
    if (data.status === 'ok' && data.monitors) {
      setMonitors(data.monitors)
    }
  }, [])

  useEffect(() => {
    fetchMonitors()
  }, [fetchMonitors, fetchScreenshot])

  useEffect(() => {
    if (liveMode) {
      startLive()
      return () => { if (esRef.current) { esRef.current.close(); esRef.current = null } }
    }
  }, [liveMode, startLive])

  const handleMonitorChange = (m: number) => {
    setCurrentMonitor(m)
    if (!liveMode) fetchScreenshot()
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 20px 20px', gap: 12, boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>📺 屏幕监控</h2>
        <span style={{ fontSize: 13, color: '#999', minWidth: 120 }}>{liveMode ? frameSize : info}</span>
        {liveMode && (
          <span style={{ fontSize: 12, color: '#4caf50', fontWeight: 600 }}>● 实时</span>
        )}
        <div style={{ flex: 1 }} />
        <select
          value={currentMonitor}
          onChange={(e) => handleMonitorChange(Number(e.target.value))}
          style={{
            padding: '6px 10px', borderRadius: 6, border: '1px solid #ddd',
            fontSize: 13, outline: 'none', background: '#fff',
          }}
        >
          {monitors.map((m) => (
            <option key={m.monitor} value={m.monitor}>
              {m.label} ({m.width}×{m.height})
            </option>
          ))}
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#999', whiteSpace: 'nowrap' }}>间隔</span>
          <input
            type="range"
            min={10}
            max={600}
            step={10}
            value={streamInterval}
            onChange={(e) => setStreamInterval(Number(e.target.value))}
            style={{ width: 80, cursor: 'pointer' }}
          />
          <span style={{ fontSize: 12, color: '#666', minWidth: 32 }}>{streamInterval}ms</span>
        </div>
        <button
          onClick={toggleLive}
          className={`btn ${liveMode ? 'btn-danger' : 'btn-primary'}`}
          style={{ fontWeight: liveMode ? 600 : 400 }}
        >
          {liveMode ? '⏹ 停止' : '▶ 实时流'}
        </button>
        {!liveMode && (
          <button
            onClick={fetchScreenshot}
            className="btn btn-primary"
          >
            刷新
          </button>
        )}
      </div>

      <div style={{
        flex: 1, border: '1px solid #e0e0e0', borderRadius: 8, overflow: 'hidden',
        background: '#fafafa', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0,
      }}>
        {screenshot ? (
          <img
            src={`data:image/jpeg;base64,${screenshot}`}
            alt="屏幕截图"
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        ) : (
          <span style={{ color: '#ccc', fontSize: 14 }}>等待截图...</span>
        )}
      </div>
    </div>
  )
}
