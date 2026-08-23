import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { SUB_AGENTS } from '../config/agents'
import Mascot from './Mascot'
import LandingHeader from './LandingHeader'

/* ============================================================
   小元AI 官网首页 — 公开页面（免登录）
   区块：Header / Hero / 多智能体能力 / 特性展示 / CTA / Footer
   零外部依赖：内联样式 + CSS 变量 + 内联 SVG 图标
   ============================================================ */

/* 特性卡静态内容（图标为 lucide 风格 stroke 路径） */
const FEATURES = [
  {
    icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
    title: '多模型智能对话',
    desc: '对话为统一入口，自动识别意图并路由到最合适的模型与 Agent 处理。',
  },
  {
    icon: 'M18 20V10M12 20V4M6 20v-6',
    title: '数据分析与可视化',
    desc: '数据集管理、统计分析、图表生成，结果直达交互式 3D 分析大屏。',
  },
  {
    icon: 'M21 12a9 9 0 1 1-9-9M12 2v6m0 0l-2-2m2 2l2-2',
    title: '网页数据采集',
    desc: '网页爬取、数据抓取、内容提取，采集结果自动沉淀为可用数据集。',
  },
  {
    icon: 'M4 4h16v16H4zM9 9h6v6H9zM9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2',
    title: '自动化任务执行',
    desc: '浏览器控制、题目审核、截图监控，重复性工作交给 Agent 自动完成。',
  },
  {
    icon: 'M10 2v7.5L4.5 18a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 9.5V2M8.5 2h7M7 16h10',
    title: '生命科学分析',
    desc: '基因表达分布分析、火山图、PubMed 文献检索、药物可行性评估。',
  },
  {
    icon: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
    title: '知识库检索',
    desc: '向量知识库秒级语义检索，让 Agent 基于你的文档给出有据可依的回答。',
  },
  {
    icon: 'M4 17l6-6-6-6M12 19h8',
    title: 'Claude Code 桥接',
    desc: '云端对话直连本机 Claude Code，代码编写、终端命令、Git 操作一步到位。',
  },
]

/* 功能入口 — 指向已实现的独立功能页（登录后直达） */
const ENTRIES = [
  {
    icon: 'M18 20V10M12 20V4M6 20v-6',
    title: '数据分析工作台',
    desc: '数据集上传、一键统计分析、图表生成',
    to: '/chat/agent/analysis',
  },
  {
    icon: 'M21.21 15.89A10 10 0 1 1 8 2.83M22 12A10 10 0 0 0 12 2v10z',
    title: 'RFM 客户分群大屏',
    desc: '交互式 3D 客户价值分群散点',
    to: '/chat/agent/rfm',
  },
  {
    icon: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
    title: '知识库检索',
    desc: '文档知识库语义检索与查询',
    to: '/chat/agent/knowledge',
  },
  {
    icon: 'M4 4h16v16H4zM9 9h6v6H9zM9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2',
    title: '浏览器自动化',
    desc: '浏览器控制、题目审核、截图监控',
    to: '/chat/agent/automation',
  },
  {
    icon: 'M3 4h18v12H3zM3 20h18M7 8h.01M7 12h.01M7 16h.01',
    title: 'Agent 运行状态',
    desc: '本机 Agent 在线状态与模型配置',
    to: '/chat/agent',
  },
]

export default function LandingPage() {
  const { isAdmin } = useAuth()
  const [visible, setVisible] = useState(false)

  // 入场淡入动画（同 LoginPage 惯例）
  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
  }, [])

  return (
    <div className={`landing-page ${visible ? 'visible' : ''}`}>
      {/* ============ Header（sticky，共享组件） ============ */}
      <LandingHeader />

      {/* ============ Hero 区 ============ */}
      <section className="landing-hero">
        <div className="landing-orb orb-1" />
        <div className="landing-orb orb-2" />
        <div className="landing-orb orb-3" />
        <div className="landing-hero-content">
          <div className="landing-hero-mascot">
            <Mascot size={96} />
          </div>
          <h1 className="landing-hero-title">小元AI</h1>
          <p className="landing-hero-desc">云边协同 · 多智能体协作平台</p>
          <p className="landing-hero-sub">数据分析 / 数据采集 / 自动化 / 生命科学 / 多智能体协作</p>
          <div className="landing-hero-actions">
            <Link to="/chat" className="landing-cta landing-cta-primary">进入对话</Link>
            <a href="#agents" className="landing-cta landing-cta-ghost">了解能力 ↓</a>
          </div>
        </div>
      </section>

      {/* ============ 多智能体能力 ============ */}
      <section className="landing-section" id="agents">
        <h2 className="landing-section-title">多智能体协同</h2>
        <p className="landing-section-desc">
          统筹 Agent 自动识别意图，把任务委派给最擅长的专业 Agent —— 一个对话入口，一支 Agent 团队
        </p>
        <div className="landing-agent-grid">
          {SUB_AGENTS.map((agent, i) => (
            <div key={agent.key} className="landing-agent-card" style={{ animationDelay: `${i * 0.08}s` }}>
              <span className="landing-agent-dot" style={{ background: agent.color }} />
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 6px', color: 'var(--text-primary)' }}>
                {agent.label}
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 }}>
                {agent.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ============ 特性展示 ============ */}
      <section className="landing-section" id="features">
        <h2 className="landing-section-title">核心能力</h2>
        <p className="landing-section-desc">从对话到执行，覆盖数据分析、数据采集与自动化全链路</p>
        <div className="landing-feature-grid">
          {FEATURES.map((feat, i) => (
            <div key={feat.title} className="landing-feature-card" style={{ animationDelay: `${i * 0.06}s` }}>
              <span className="landing-feature-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d={feat.icon}/>
                </svg>
              </span>
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 6px', color: 'var(--text-primary)' }}>
                {feat.title}
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 }}>
                {feat.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ============ 功能入口（登录后直达各功能面板） ============ */}
      <section className="landing-section" id="apps">
        <h2 className="landing-section-title">功能入口</h2>
        <p className="landing-section-desc">登录后直达各功能面板 —— 分析大屏、知识库、自动化等</p>
        <div className="landing-entry-grid">
          {ENTRIES.map((entry, i) => (
            <Link key={entry.title} to={entry.to} className="landing-entry-card" style={{ animationDelay: `${i * 0.06}s` }}>
              <span className="landing-feature-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d={entry.icon}/>
                </svg>
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 4px', color: 'var(--text-primary)' }}>
                  {entry.title}
                </h3>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                  {entry.desc}
                </p>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="landing-entry-arrow">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </Link>
          ))}
        </div>
      </section>

      {/* ============ CTA 区 ============ */}
      <section className="landing-section landing-cta-band-wrap">
        <div className="landing-cta-band">
          <h2 style={{ fontSize: 24, fontWeight: 800, margin: '0 0 10px', color: '#fff' }}>
            让 AI Agent 团队为你工作
          </h2>
          <p style={{ fontSize: 14, opacity: 0.85, margin: '0 0 24px', color: '#fff' }}>
            一个对话入口，驱动数据分析、数据采集与自动化任务
          </p>
          <Link to="/chat" className="landing-cta landing-cta-light">立即开始</Link>
        </div>
      </section>

      {/* ============ Footer ============ */}
      <footer className="landing-footer">
        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>小元AI</span>
        <span style={{ color: 'var(--text-secondary)' }}>云边协同 · 多智能体协作平台</span>
        <Link to="/about" style={{ fontSize: 12, color: 'var(--text-muted)', textDecoration: 'none' }}>关于我们</Link>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>© 2026 小元AI</span>
        {isAdmin && (
          <Link to="/chat/admin" style={{ fontSize: 12, color: 'var(--text-muted)', textDecoration: 'none' }}>
            管理后台
          </Link>
        )}
      </footer>

      <style>{`
        /* ============================
           官网首页 — 全局样式
           ============================ */
        /* 锚点平滑滚动（Hero「了解能力 ↓」跳转） */
        html { scroll-behavior: smooth; }

        .landing-page {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
          background: var(--bg-primary);
          opacity: 0;
          transition: opacity 0.5s ease;
        }
        .landing-page.visible { opacity: 1; }

        /* ============================
           Hero 区
           ============================ */
        .landing-hero {
          position: relative;
          background: linear-gradient(135deg, #1565c0 0%, #0d47a1 40%, #1a237e 100%);
          overflow: hidden;
          padding: 88px 24px 96px;
        }
        [data-theme="dark"] .landing-hero {
          background: linear-gradient(135deg, #0d2137 0%, #0a1628 40%, #0f1a2e 100%);
        }

        /* 装饰光晕（复用登录页 orb 思路） */
        .landing-orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.3;
          animation: orb-float 12s ease-in-out infinite;
        }
        [data-theme="dark"] .landing-orb { opacity: 0.18; }
        @keyframes orb-float {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%  { transform: translate(30px, -20px) scale(1.05); }
          66%  { transform: translate(-20px, 15px) scale(0.95); }
        }

        .landing-hero-content {
          position: relative;
          z-index: 1;
          max-width: 640px;
          margin: 0 auto;
          text-align: center;
          color: #fff;
        }
        .landing-hero-mascot {
          display: inline-block;
          margin-bottom: 20px;
          animation: logo-in 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        @keyframes logo-in {
          from { opacity: 0; transform: scale(0.8); }
          to   { opacity: 1; transform: scale(1); }
        }
        .landing-hero-title {
          font-size: 44px;
          font-weight: 800;
          margin: 0 0 10px;
          letter-spacing: 2px;
          animation: fade-up 0.6s 0.1s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .landing-hero-desc {
          font-size: 17px;
          opacity: 0.9;
          margin: 0 0 14px;
          letter-spacing: 3px;
          animation: fade-up 0.6s 0.2s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .landing-hero-sub {
          font-size: 13px;
          opacity: 0.7;
          margin: 0 0 36px;
          animation: fade-up 0.6s 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        @keyframes fade-up {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .landing-hero-actions {
          display: flex;
          justify-content: center;
          gap: 14px;
          animation: fade-up 0.6s 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .landing-cta {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          height: 46px;
          padding: 0 34px;
          border-radius: 23px;
          font-size: 15px;
          font-weight: 700;
          text-decoration: none;
          transition: all 0.15s;
        }
        .landing-cta-primary {
          background: #fff;
          color: #1565c0;
          box-shadow: 0 4px 20px rgba(0,0,0,0.18);
        }
        .landing-cta-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 28px rgba(0,0,0,0.25);
        }
        .landing-cta-ghost {
          border: 1px solid rgba(255,255,255,0.5);
          color: #fff;
          background: transparent;
        }
        .landing-cta-ghost:hover {
          background: rgba(255,255,255,0.12);
        }

        /* ============================
           通用 Section
           ============================ */
        .landing-section {
          max-width: 960px;
          margin: 0 auto;
          padding: 72px 24px 0;
          width: 100%;
          box-sizing: border-box;
        }
        .landing-section-title {
          font-size: 26px;
          font-weight: 800;
          margin: 0 0 10px;
          color: var(--text-primary);
          text-align: center;
        }
        .landing-section-desc {
          font-size: 14px;
          color: var(--text-secondary);
          margin: 0 auto 40px;
          text-align: center;
          max-width: 520px;
          line-height: 1.7;
        }

        /* ============================
           多智能体卡片网格
           ============================ */
        .landing-agent-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
          gap: 16px;
        }
        .landing-agent-card {
          position: relative;
          padding: 20px 20px 20px 24px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
          transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
          animation: fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
          overflow: hidden;
        }
        .landing-agent-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 8px 24px rgba(0,0,0,0.08);
          border-color: var(--accent);
        }
        [data-theme="dark"] .landing-agent-card:hover {
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .landing-agent-dot {
          position: absolute;
          left: 0; top: 0; bottom: 0;
          width: 4px;
          border-radius: 0 2px 2px 0;
        }

        /* ============================
           特性卡片网格
           ============================ */
        .landing-feature-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }
        .landing-feature-card {
          padding: 24px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
          transition: transform 0.15s, box-shadow 0.15s;
          animation: fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .landing-feature-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }
        [data-theme="dark"] .landing-feature-card:hover {
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .landing-feature-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 44px; height: 44px;
          border-radius: 10px;
          background: var(--accent-light);
          color: var(--accent);
          margin-bottom: 14px;
          flex-shrink: 0;
        }

        /* ============================
           功能入口卡片
           ============================ */
        .landing-entry-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 14px;
        }
        .landing-entry-card {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 18px 20px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
          text-decoration: none;
          transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
          animation: fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .landing-entry-card .landing-feature-icon { margin-bottom: 0; }
        .landing-entry-card:hover {
          transform: translateY(-3px);
          border-color: var(--accent);
          box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }
        [data-theme="dark"] .landing-entry-card:hover {
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .landing-entry-arrow {
          color: var(--text-muted);
          flex-shrink: 0;
          transition: transform 0.15s, color 0.15s;
        }
        .landing-entry-card:hover .landing-entry-arrow {
          transform: translateX(3px);
          color: var(--accent);
        }

        /* ============================
           CTA 带
           ============================ */
        .landing-cta-band-wrap { padding-bottom: 72px; }
        .landing-cta-band {
          background: linear-gradient(135deg, #1565c0 0%, #1a237e 100%);
          border-radius: 20px;
          padding: 48px 32px;
          text-align: center;
        }
        [data-theme="dark"] .landing-cta-band {
          background: linear-gradient(135deg, #0d2137 0%, #0f1a2e 100%);
        }
        .landing-cta-light {
          background: #fff;
          color: #1565c0;
          box-shadow: 0 4px 20px rgba(0,0,0,0.18);
        }
        .landing-cta-light:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 28px rgba(0,0,0,0.25);
        }

        /* ============================
           Footer
           ============================ */
        .landing-footer {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 16px;
          flex-wrap: wrap;
          padding: 28px 24px 36px;
          border-top: 1px solid var(--border);
          font-size: 13px;
        }

        /* ============================
           响应式
           ============================ */
        /* 平板：缩小 Hero 标题 */
        @media (max-width: 1024px) {
          .landing-hero { padding: 64px 24px 72px; }
          .landing-hero-title { font-size: 36px; }
        }

        /* 手机：卡片单列、Hero 收缩 */
        @media (max-width: 800px) {
          .landing-hero { padding: 48px 16px 56px; }
          .landing-hero-title { font-size: 30px; }
          .landing-hero-desc { font-size: 14px; letter-spacing: 2px; }
          .landing-hero-actions { flex-direction: column; align-items: center; }
          .landing-cta { width: min(100%, 280px); }  /* 全宽按钮，方便拇指点按 */
          /* 光晕降模糊半径与透明度，减轻移动端 GPU 负担 */
          .landing-orb { filter: blur(60px); opacity: 0.22; }
          .landing-section { padding: 48px 16px 0; }
          .landing-section-title { font-size: 22px; }
          .landing-agent-grid,
          .landing-feature-grid,
          .landing-entry-grid { grid-template-columns: 1fr; }
          .landing-cta-band-wrap { padding-bottom: 48px; }
          .landing-cta-band { padding: 36px 20px; }
          .landing-footer { gap: 10px; }
        }

        /* 小屏手机：进一步收缩 */
        @media (max-width: 480px) {
          .landing-hero { padding: 40px 12px 48px; }
          .landing-hero-title { font-size: 26px; }
          .landing-hero-sub { margin-bottom: 28px; }
          .landing-orb { filter: blur(50px); }
          .orb-3 { display: none; }  /* 隐藏第三个光晕，减渲染量 */
          .landing-section { padding: 40px 12px 0; }
          .landing-section-title { font-size: 20px; }
          .landing-cta-band { padding: 32px 16px; border-radius: 16px; }
        }
      `}</style>
    </div>
  )
}
