import { API_BASE } from '../../api'
export type Step = 1 | 2 | 3

export const WEBSITES = [
  { name: '小猿众包', url: 'https://xyzb.yuanfudao.com/' },
  { name: '知乎', url: 'https://www.zhihu.com/' },
  { name: 'B站', url: 'https://www.bilibili.com/' },
  { name: 'BOSS直聘', url: 'https://www.zhipin.com/' },
]

export const STEPS = [
  { n: 1 as Step, label: '打开网站', desc: '启动浏览器并导航到目标网站' },
  { n: 2 as Step, label: '开始任务', desc: '选择并开始一个审核任务' },
  { n: 3 as Step, label: '执行任务', desc: 'AI 审核并提交反馈' },
]

export const ERROR_CAUSES = ['格式问题占比较多', '举报', '文本压线', '黄框压题干', '最终答案', '不独立', '出框', '少答案', '字太小', '答案错']

export async function executeTool(name: string, args: any = {}): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/tools/execute`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, args }),
    })
    const data = await res.json()
    return data.result || data.detail || '完成'
  } catch { return '调用失败' }
}

export function StatusDot({ ok }: { ok: boolean }) {
  return <span style={{ width: 8, height: 8, borderRadius: '50%', display: 'inline-block', background: ok ? '#4caf50' : '#ccc', marginRight: 6 }} />
}

export function opBtnStyle(): React.CSSProperties {
  return { padding: '5px 10px', borderRadius: 4, border: '1px solid #ddd', background: '#fff', cursor: 'pointer', fontSize: 11, color: '#333' }
}

export function actionBtnStyle(running: boolean): React.CSSProperties {
  return { padding: '5px 10px', borderRadius: 5, border: '1px solid #ddd', background: '#fff', cursor: running ? 'pointer' : 'not-allowed', fontSize: 12, color: running ? '#333' : '#ccc' }
}

export function tabBtnStyle(active: boolean): React.CSSProperties {
  return { padding: '4px 12px', borderRadius: 4, border: 'none', background: active ? '#1976d2' : 'transparent', color: active ? '#fff' : '#666', cursor: 'pointer', fontSize: 12 }
}
