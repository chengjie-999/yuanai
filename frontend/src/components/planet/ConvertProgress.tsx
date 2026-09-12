import { useEffect, useRef, useState } from 'react'
import { getJob } from '../../api/planet'
import { LoaderIcon, CheckIcon, AlertIcon } from '../icons'

/* 任务轮询 hook：1.5s 拉一次，done/failed 自停 */
export function usePlanetJob(jobId: number | null, onDone?: (job: any) => void) {
  const [job, setJob] = useState<any>(null)
  const doneRef = useRef<((job: any) => void) | undefined>(onDone)
  doneRef.current = onDone

  useEffect(() => {
    if (!jobId) return
    let stop = false
    const poll = async () => {
      try {
        const j = await getJob(jobId)
        if (stop) return
        setJob(j)
        if (j.status === 'done') { doneRef.current?.(j); return }
        if (j.status === 'failed') return
        setTimeout(poll, 1500)
      } catch { if (!stop) setTimeout(poll, 2500) }
    }
    poll()
    return () => { stop = true }
  }, [jobId])

  return job
}

/* 任务进度条：pending/running 显示进度，done 绿勾，failed 红叉 */
export default function JobProgress({ job }: { job: any }) {
  if (!job) return null
  const status = job.status
  const pct = job.progress || 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', fontSize: 12 }}>
      {status === 'done' ? (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--success)' }}>
          <CheckIcon size={14} /> {job.message || '完成'}
        </span>
      ) : status === 'failed' ? (
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--danger)' }}>
          <AlertIcon size={14} /> {job.error || '失败'}
        </span>
      ) : (
        <>
          <LoaderIcon size={13} style={{ animation: 'spin 0.8s linear infinite', color: 'var(--accent)' }} />
          <span style={{ color: 'var(--text-secondary)' }}>{job.message || '处理中...'}</span>
          <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', maxWidth: 160 }}>
            <div style={{ height: '100%', width: `${pct}%`, background: 'var(--accent)', borderRadius: 2, transition: 'width 0.3s' }} />
          </div>
        </>
      )}
    </div>
  )
}
