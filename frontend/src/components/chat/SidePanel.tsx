import { AGENT_CONFIG } from '../../config/agents'
import KnowledgePanel from './panels/KnowledgePanel'
import AnalysisPanel from './panels/AnalysisPanel'
import AutomationPanel from './panels/AutomationPanel'

export type PanelType = 'automation' | 'analysis' | 'knowledge' | null

const PANEL_META: Record<string, { icon: string; desc: string }> = {
  automation: { icon: '🤖', desc: '浏览器控制、截图监控、题目审核' },
  analysis: { icon: '📊', desc: '数据集管理、统计分析、图表生成' },
  knowledge: { icon: '📚', desc: '知识库检索与文档查询' },
}

export default function SidePanel({ panel, onClose, agentOnline }: {
  panel: PanelType; onClose: () => void; agentOnline: boolean
}) {
  const open = panel !== null
  const meta = panel ? PANEL_META[panel] : null
  const agent = panel ? AGENT_CONFIG[panel] : null

  return (
    <div style={{
      width: open ? 380 : 0,
      overflow: open ? 'hidden' : 'hidden',
      background: 'var(--bg-primary)',
      borderLeft: open ? '1px solid var(--border)' : 'none',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      transition: 'width 0.25s ease',
    }}>
      {open && agent && meta && (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <div style={{
            padding: '12px 14px', borderBottom: '1px solid var(--border-light)',
            display: 'flex', alignItems: 'center', gap: 10,
            background: 'var(--bg-secondary)', flexShrink: 0,
          }}>
            <span style={{ fontSize: 18, lineHeight: 1 }}>{meta.icon}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: agent.color, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: agent.color, display: 'inline-block', flexShrink: 0 }} />
                {agent.label}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{meta.desc}</div>
            </div>
            <span
              onClick={onClose}
              style={{
                width: 22, height: 22, borderRadius: '50%',
                background: 'var(--bg-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1,
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--hover-bg)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
            >✕</span>
          </div>

          {/* Panel body */}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            {panel === 'knowledge' && <KnowledgePanel />}
            {panel === 'analysis' && <AnalysisPanel />}
            {panel === 'automation' && <AutomationPanel agentOnline={agentOnline} />}
          </div>
        </div>
      )}
    </div>
  )
}
