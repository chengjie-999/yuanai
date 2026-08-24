import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import LandingHeader from './LandingHeader'

/* ============================================================
   关于我 — 公开简历页（免登录，/about）
   署名用网名「程林析」（不公开真实姓名）
   ============================================================ */

/* 技能栈（静态内容） */
const SKILLS = [
  {
    icon: 'M3 3v18h18M7 16l4-4-4-4M11 19h6',
    title: '数据分析',
    desc: 'pandas / matplotlib / seaborn，统计建模、RFM 分群、流失预测、时间序列分析，PyCharm 科学模式（#%%）工作流',
  },
  {
    icon: 'M12 20V10M18 20V4M6 20v-6',
    title: '机器学习',
    desc: '回归 / 分类 / 聚类 / 交叉验证，特征工程与模型评估',
  },
  {
    icon: 'M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.4 1 2.3v1h6v-1c0-.9.4-1.8 1-2.3A7 7 0 0 0 12 2zM9 21h6',
    title: 'AI Agent 开发',
    desc: 'LangChain、多智能体编排、意图路由、工具调用、RAG 向量知识库、云边协同架构',
  },
  {
    icon: 'M16 18l6-6-6-6M8 6l-6 6 6 6',
    title: 'Web 开发',
    desc: 'Python（FastAPI）+ React / TypeScript，WebSocket / SSE 实时通信，全栈独立开发',
  },
  {
    icon: 'M12 2v4m0 12v4M2 12h4m12 0h4M5 5l2.8 2.8m8.4 8.4L19 19M19 5l-2.8 2.8M7.8 16.2L5 19',
    title: '基础设施',
    desc: 'MySQL / Redis / Milvus / Docker / Nginx，火山引擎云上部署',
  },
  {
    icon: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
    title: '数据采集与自动化',
    desc: '网页爬取、浏览器自动化（Selenium / CDP）、截图监控、审核流程自动化',
  },
]

/* 联系方式（公开信息；如有变更请直接修改） */
const CONTACTS: { icon: string; label: string; value: string; href?: string }[] = [
  {
    icon: 'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM22 6l-10 7L2 6',
    label: '邮箱',
    value: 'chengjie2017020@163.com',
    href: 'mailto:chengjie2017020@163.com',
  },
  {
    icon: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z',
    label: '微信',
    value: '17852428208（手机同号）',
  },
  {
    icon: 'M9 19c-4.3 1.4-4.3-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.8 5.4 3.1 5.4 3.1a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.5c0 4.6 2.7 5.7 5.5 6-.6.6-.6 1.2-.5 2V21',
    label: 'GitHub',
    value: 'chengjie-999',
    href: 'https://github.com/chengjie-999',
  },
  {
    icon: 'M21 12a9 9 0 1 1-9-9M12 7v5l3 3',
    label: 'Gitee',
    value: 'chengjie999',
    href: 'https://gitee.com/chengjie999',
  },
]

export default function AboutPage() {
  const [visible, setVisible] = useState(false)

  // 入场淡入动画（同 LandingPage 惯例）
  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
  }, [])

  return (
    <div className={`about-page ${visible ? 'visible' : ''}`}>
      <LandingHeader />

      {/* ============ 页头 ============ */}
      <section className="about-hero">
        <h1 className="about-hero-title">程林析</h1>
        <p className="about-hero-desc">数据分析师 · AI 应用开发者 · 小元AI 作者</p>
        <p className="about-hero-sub">用代码做分析，用 Agent 做自动化 —— 喜欢 Python，追求简洁而清晰的设计</p>
      </section>

      {/* ============ 个人简介 ============ */}
      <section className="about-section">
        <h2 className="about-section-title">简介</h2>
        <div className="about-intro-card">
          <p>
            一名数据分析师，同时也是 AI 应用开发者。日常以 PyCharm 科学模式（<code>#%%</code> 逐块运行）做数据分析，
            擅长统计建模、客户分群与预测分析。
          </p>
          <p>
            目前专注于多智能体 AI 平台 —— <Link to="/" style={{ color: 'var(--accent)', textDecoration: 'none' }}>小元AI</Link> 的独立开发：
            云边协同架构下，统筹 Agent 识别意图并委派数据分析、数据采集、自动化等专业 Agent 协作完成任务，
            覆盖从对话、分析到执行的全链路。
          </p>
          <p>
            相信 AI 的落地方式不是炫技，而是把真实工作流交给 Agent 团队 —— 人负责定义问题，Agent 负责执行。
          </p>
        </div>
      </section>

      {/* ============ 技能栈 ============ */}
      <section className="about-section">
        <h2 className="about-section-title">技能栈</h2>
        <div className="about-skill-grid">
          {SKILLS.map((skill, i) => (
            <div key={skill.title} className="about-skill-card" style={{ animationDelay: `${i * 0.06}s` }}>
              <span className="about-skill-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d={skill.icon}/>
                </svg>
              </span>
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 6px', color: 'var(--text-primary)' }}>
                {skill.title}
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 }}>
                {skill.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ============ 项目经历 ============ */}
      <section className="about-section">
        <h2 className="about-section-title">项目经历</h2>
        <div className="about-project-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <span style={{
              width: 10, height: 10, borderRadius: '50%', background: 'var(--accent)', display: 'inline-block', flexShrink: 0,
            }} />
            <h3 style={{ fontSize: 16, fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
              小元AI — 云边协同多智能体协作平台
            </h3>
          </div>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', margin: '0 0 14px', lineHeight: 1.7 }}>
            以对话为统一入口的多智能体平台：统筹 Agent 自动识别用户意图，委派数据分析、数据采集、自动化等专业子 Agent 执行任务。
            云端负责调度与展示，本地 Agent 负责真实环境执行（浏览器、代码、文件），分析结果直达交互式 3D 大屏。
          </p>
          <div className="about-tag-row">
            {['云边协同', '多智能体编排', '意图路由', 'Skill YAML 自动发现', 'Claude Code 桥接', 'RAG 知识库', 'SSE 流式对话'].map((tag) => (
              <span key={tag} className="about-tag">{tag}</span>
            ))}
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '14px 0 0' }}>
            技术栈：Python FastAPI · React + TypeScript · LangChain · Milvus · MySQL · Redis · Docker
          </p>
        </div>
      </section>

      {/* ============ 联系方式 ============ */}
      <section className="about-section about-last">
        <h2 className="about-section-title">联系方式</h2>
        <div className="about-contact-grid">
          {CONTACTS.map((c) => {
            const inner = (
              <>
                <span className="about-skill-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d={c.icon}/>
                  </svg>
                </span>
                <div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.label}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{c.value}</div>
                </div>
              </>
            )
            /* 有链接（邮箱/GitHub/Gitee）渲染 <a>，微信无链接渲染纯文本卡片 */
            return c.href ? (
              <a key={c.label} href={c.href} target="_blank" rel="noopener noreferrer" className="about-contact-card">
                {inner}
              </a>
            ) : (
              <div key={c.label} className="about-contact-card">{inner}</div>
            )
          })}
        </div>
      </section>

      {/* ============ Footer ============ */}
      <footer className="about-footer">
        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>小元AI</span>
        <span style={{ color: 'var(--text-secondary)' }}>数据分析师 · AI 应用开发者</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>© 2026 小元AI</span>
      </footer>

      <style>{`
        /* ============================
           关于我页 — 全局样式
           ============================ */
        .about-page {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
          background: var(--bg-primary);
          opacity: 0;
          transition: opacity 0.5s ease;
        }
        .about-page.visible { opacity: 1; }

        /* 页头 */
        .about-hero {
          background: linear-gradient(135deg, #1565c0 0%, #0d47a1 40%, #1a237e 100%);
          padding: 56px 24px;
          text-align: center;
        }
        [data-theme="dark"] .about-hero {
          background: linear-gradient(135deg, #0d2137 0%, #0a1628 40%, #0f1a2e 100%);
        }
        .about-hero-title {
          font-size: 32px;
          font-weight: 800;
          margin: 0 0 8px;
          color: #fff;
          letter-spacing: 2px;
          animation: fade-up 0.6s 0.1s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .about-hero-desc {
          font-size: 15px;
          color: #fff;
          opacity: 0.9;
          margin: 0 0 8px;
          letter-spacing: 2px;
          animation: fade-up 0.6s 0.2s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .about-hero-sub {
          font-size: 13px;
          color: #fff;
          opacity: 0.7;
          margin: 0;
          animation: fade-up 0.6s 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        @keyframes fade-up {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        /* 通用 Section */
        .about-section {
          max-width: 860px;
          margin: 0 auto;
          padding: 56px 24px 0;
          width: 100%;
          box-sizing: border-box;
        }
        .about-section-title {
          font-size: 22px;
          font-weight: 800;
          margin: 0 0 24px;
          color: var(--text-primary);
          text-align: center;
        }
        .about-last { padding-bottom: 56px; }

        /* 简介卡片 */
        .about-intro-card {
          padding: 28px 32px;
          border-radius: 14px;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
        }
        .about-intro-card p {
          font-size: 14px;
          color: var(--text-secondary);
          line-height: 1.8;
          margin: 0 0 12px;
        }
        .about-intro-card p:last-child { margin-bottom: 0; }
        .about-intro-card code {
          background: var(--bg-tertiary);
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 13px;
          color: var(--accent);
        }

        /* 技能 / 特性卡片网格 */
        .about-skill-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
          gap: 16px;
        }
        .about-skill-card {
          padding: 22px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
          transition: transform 0.15s, box-shadow 0.15s;
          animation: fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .about-skill-card:hover {
          transform: translateY(-3px);
          box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }
        [data-theme="dark"] .about-skill-card:hover {
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .about-skill-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 42px; height: 42px;
          border-radius: 10px;
          background: var(--accent-light);
          color: var(--accent);
          margin-bottom: 12px;
          flex-shrink: 0;
        }

        /* 项目卡片 */
        .about-project-card {
          padding: 28px 32px;
          border-radius: 14px;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
        }
        .about-tag-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .about-tag {
          font-size: 12px;
          color: var(--accent);
          background: var(--accent-light);
          padding: 4px 10px;
          border-radius: 12px;
        }

        /* 联系方式卡片 */
        .about-contact-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          gap: 16px;
        }
        .about-contact-card {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 20px 22px;
          border-radius: 12px;
          border: 1px solid var(--border);
          background: var(--bg-secondary);
          text-decoration: none;
          transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
        }
        .about-contact-card:hover {
          transform: translateY(-3px);
          border-color: var(--accent);
          box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        }
        [data-theme="dark"] .about-contact-card:hover {
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }

        /* Footer */
        .about-footer {
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
        @media (max-width: 800px) {
          .about-hero { padding: 40px 16px; }
          .about-hero-title { font-size: 26px; }
          .about-section { padding: 40px 16px 0; }
          .about-section-title { font-size: 20px; }
          .about-skill-grid,
          .about-contact-grid { grid-template-columns: 1fr; }
          .about-intro-card,
          .about-project-card { padding: 22px 20px; }
          .about-last { padding-bottom: 40px; }
          .about-footer { gap: 10px; }
        }

        /* 小屏手机：进一步收缩 */
        @media (max-width: 480px) {
          .about-hero { padding: 32px 12px; }
          .about-hero-title { font-size: 24px; }
          .about-hero-desc { font-size: 13px; letter-spacing: 1px; }
          .about-hero-sub { font-size: 12px; }
          .about-section { padding: 32px 12px 0; }
          .about-section-title { font-size: 18px; margin-bottom: 20px; }
          .about-contact-card { padding: 16px 18px; }
        }
      `}</style>
    </div>
  )
}
