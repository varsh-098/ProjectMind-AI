import React, { useState, useEffect, useRef } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Brain,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  ExternalLink,
  Eye,
  FileCode,
  FileText,
  FolderGit2,
  Gauge,
  HelpCircle,
  Layers,
  Loader2,
  MessageCircle,
  Orbit,
  Play,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
  User,
  Wrench,
  X,
  AlertTriangle
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8081'

// Built-in core agent metadata
const PRIMARY_AGENTS = [
  {
    id: 'supervisor',
    name: 'Supervisor',
    role: 'Autonomous Multi-Agent Orchestrator',
    badge: 'AUTONOMOUS',
    color: '#a78bfa',
    icon: Sparkles,
    desc: 'Intelligently classifies tasks, routes to memory or specialized agents, and runs multi-agent pipelines.',
  },
  {
    id: 'coding',
    name: 'Coding Agent',
    role: 'Full-Stack Software Engineer',
    badge: 'CORE AGENT',
    color: '#60a5fa',
    icon: Code2,
    desc: 'Implements features, resolves bugs, refactors code, and performs surgical file edits with sandbox safety.',
  },
  {
    id: 'review',
    name: 'Review Agent',
    role: 'Senior Code Reviewer & Security Auditor',
    badge: 'CORE AGENT',
    color: '#34d399',
    icon: ShieldCheck,
    desc: 'Performs AST syntax validation, security compliance audits, and architectural code reviews.',
  },
  {
    id: 'testing',
    name: 'Testing Agent',
    role: 'Test Automation Specialist',
    badge: 'CORE AGENT',
    color: '#f472b6',
    icon: Terminal,
    desc: 'Executes unittest test suites, detects regressions, and verifies behavioral correctness.',
  },
  {
    id: 'chat',
    name: 'Standard Chat',
    role: 'Direct Conversational LLM',
    badge: 'DIRECT LLM',
    color: '#38bdf8',
    icon: MessageCircle,
    desc: 'Fast, direct conversational reasoning without multi-turn tool loops.',
  },
]

// Preset task starters for quick demonstration
const QUICK_PROMPTS = [
  { label: 'Project Architecture', prompt: 'Summarize the architecture, tech stack, and key modules of ProjectMind AI.', agent: 'supervisor' },
  { label: 'Run Unit Tests', prompt: 'Run the unit test suite and report pass rate and test status.', agent: 'supervisor' },
  { label: 'Security Audit', prompt: 'Audit authentication security, session handling, and CORS configuration in backend.', agent: 'supervisor' },
  { label: 'Inspect Memory', prompt: 'What persistent architectural facts and ADRs are stored in project memory?', agent: 'supervisor' },
]

// Simple safe Markdown formatter for messages
function FormattedContent({ content }) {
  if (!content) return null

  // Process code blocks with triple backticks
  const parts = []
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g
  let lastIndex = 0
  let match

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: content.substring(lastIndex, match.index) })
    }
    parts.push({ type: 'code', lang: match[1] || 'code', value: match[2].trim() })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < content.length) {
    parts.push({ type: 'text', value: content.substring(lastIndex) })
  }

  return (
    <div className="formatted-markdown">
      {parts.map((p, idx) => {
        if (p.type === 'code') {
          return <CodeBlock key={idx} lang={p.lang} code={p.value} />
        }
        return (
          <div key={idx} className="markdown-prose">
            {p.value.split('\n\n').map((para, pIdx) => {
              // Line-based list rendering
              if (para.startsWith('- ') || para.startsWith('* ')) {
                const items = para.split('\n').filter(Boolean)
                return (
                  <ul key={pIdx}>
                    {items.map((item, iIdx) => (
                      <li key={iIdx}>{item.replace(/^[-*]\s+/, '')}</li>
                    ))}
                  </ul>
                )
              }
              if (/^\d+\.\s/.test(para)) {
                const items = para.split('\n').filter(Boolean)
                return (
                  <ol key={pIdx}>
                    {items.map((item, iIdx) => (
                      <li key={iIdx}>{item.replace(/^\d+\.\s+/, '')}</li>
                    ))}
                  </ol>
                )
              }
              if (para.startsWith('### ')) {
                return <h4 key={pIdx}>{para.replace('### ', '')}</h4>
              }
              if (para.startsWith('## ')) {
                return <h3 key={pIdx}>{para.replace('## ', '')}</h3>
              }
              if (para.startsWith('# ')) {
                return <h2 key={pIdx}>{para.replace('# ', '')}</h2>
              }
              return <p key={pIdx}>{para}</p>
            })}
          </div>
        )
      })}
    </div>
  )
}

function CodeBlock({ lang, code }) {
  const [copied, setCopied] = useState(false)
  const copyCode = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="code-block-container">
      <div className="code-block-header">
        <span className="code-lang-tag">{lang || 'text'}</span>
        <button className="code-copy-btn" onClick={copyCode} title="Copy code">
          {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="code-block-pre">
        <code>{code}</code>
      </pre>
    </div>
  )
}

// Collapsible ReAct Trace Item
function ReActStepItem({ step, index }) {
  const [open, setOpen] = useState(false)
  const isTool = step.type === 'tool_execution'

  return (
    <div className={`trace-step-item ${open ? 'is-open' : ''}`}>
      <button className="trace-step-header" onClick={() => setOpen(!open)}>
        <span className="trace-step-turn">Turn {step.turn || index + 1}</span>
        <span className="trace-step-tool">
          <Terminal size={12} /> {step.tool || 'Action'}
        </span>
        <span className="trace-step-chevron">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>

      {open && (
        <div className="trace-step-body">
          {step.arguments && (
            <div className="trace-param-group">
              <span className="trace-param-title">Arguments:</span>
              <pre className="trace-param-pre">{JSON.stringify(step.arguments, null, 2)}</pre>
            </div>
          )}
          {step.result && (
            <div className="trace-param-group">
              <span className="trace-param-title">Observation / Result:</span>
              <pre className="trace-param-pre">
                {typeof step.result === 'object' ? JSON.stringify(step.result, null, 2) : String(step.result)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Workspace({ user, onBack }) {
  const [activeAgent, setActiveAgent] = useState('supervisor')
  const [allAgents, setAllAgents] = useState(PRIMARY_AGENTS)
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      agent: 'ProjectMind AI',
      content: `Welcome to **ProjectMind AI** Interactive Workspace.

I am your intelligent development assistant. You can ask me questions about the codebase, instruct me to build features, conduct security reviews, inspect memory facts, or run tests.

### Functional Capabilities:
- **Project Intelligence:** Natural conversational assistance grounded in your actual project code and memory.
- **Repository Tools:** Access project files, architecture facts, and benchmark scorecards directly from the left sidebar.
- **Automated Execution:** Instant code synthesis, test verification, and automated reviews.

How can I assist your workflow today?`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [topKRag, setTopKRag] = useState(2)

  // Drawer states
  const [activeDrawer, setActiveDrawer] = useState(null) // 'files' | 'memory' | 'scorecard' | null
  const [projectFiles, setProjectFiles] = useState([])
  const [projectSummary, setProjectSummary] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileSearch, setFileSearch] = useState('')
  const [fileLoading, setFileLoading] = useState(false)

  const [memoryStats, setMemoryStats] = useState(null)
  const [memoryFacts, setMemoryFacts] = useState([])
  const [memoryQuery, setMemoryQuery] = useState('')

  const [scorecardMd, setScorecardMd] = useState('')
  const [scorecardLoading, setScorecardLoading] = useState(false)

  const messagesEndRef = useRef(null)

  // Fetch agents and project summary on mount
  useEffect(() => {
    fetchAgents()
    fetchProjectSummary()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const fetchAgents = async () => {
    try {
      const res = await fetch(`${API_BASE}/agents?include_templates=true`)
      if (res.ok) {
        const data = await res.json()
        // Map templates/custom agents
        const mapped = data.map(a => {
          const matched = PRIMARY_AGENTS.find(p => p.id === a.name)
          if (matched) return matched
          return {
            id: a.name,
            name: a.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
            role: a.role || 'Custom Agent',
            badge: a.is_template ? 'TEMPLATE' : 'CUSTOM',
            color: '#a78bfa',
            icon: Bot,
            desc: a.description || 'Custom agent registered in ProjectMind builder.',
          }
        })
        // Merge primary agents with newly discovered agents
        const seen = new Set()
        const merged = []
        for (const a of [...PRIMARY_AGENTS, ...mapped]) {
          if (!seen.has(a.id)) {
            seen.add(a.id)
            merged.push(a)
          }
        }
        setAllAgents(merged)
      }
    } catch (e) {
      // Backend not reached, keep fallback primary agents
    }
  }

  const fetchProjectSummary = async () => {
    try {
      const [sumRes, filesRes] = await Promise.all([
        fetch(`${API_BASE}/project/summary`),
        fetch(`${API_BASE}/project/files`),
      ])
      if (sumRes.ok) setProjectSummary(await sumRes.json())
      if (filesRes.ok) setProjectFiles(await filesRes.json())
    } catch (e) {}
  }

  const openDrawer = async drawerType => {
    setActiveDrawer(drawerType)
    if (drawerType === 'files' && projectFiles.length === 0) {
      fetchProjectSummary()
    } else if (drawerType === 'memory') {
      try {
        const [statsRes, factsRes] = await Promise.all([
          fetch(`${API_BASE}/memory`),
          fetch(`${API_BASE}/memory/facts`),
        ])
        if (statsRes.ok) setMemoryStats(await statsRes.json())
        if (factsRes.ok) setMemoryFacts(await factsRes.json())
      } catch (e) {}
    } else if (drawerType === 'scorecard') {
      loadScorecard()
    }
  }

  const loadScorecard = async () => {
    setScorecardLoading(true)
    try {
      const res = await fetch(`${API_BASE}/eval/scorecard`)
      if (res.ok) {
        const text = await res.text()
        setScorecardMd(text)
      } else {
        setScorecardMd('')
      }
    } catch (e) {
      setScorecardMd('')
    } finally {
      setScorecardLoading(false)
    }
  }

  const triggerEvaluation = async () => {
    setScorecardLoading(true)
    try {
      const res = await fetch(`${API_BASE}/eval/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suite: 'all', mock: true }),
      })
      if (res.ok) {
        loadScorecard()
      }
    } catch (e) {
    } finally {
      setScorecardLoading(false)
    }
  }

  const readFileContent = async filePath => {
    setFileLoading(true)
    try {
      const res = await fetch(`${API_BASE}/project/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath, start_line: 1, end_line: 300, with_line_numbers: true }),
      })
      if (res.ok) {
        const data = await res.json()
        setSelectedFile(data)
      }
    } catch (e) {
    } finally {
      setFileLoading(false)
    }
  }

  // Handle message submission
  const handleSend = async (overridePrompt = null, overrideAgent = null) => {
    const promptToSend = (overridePrompt || input).trim()
    const agentToUse = overrideAgent || activeAgent
    if (!promptToSend || loading) return

    setInput('')
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const userMsg = {
      id: 'user_' + Date.now(),
      role: 'user',
      content: promptToSend,
      timestamp,
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      let assistantMsg = null

      if (agentToUse === 'chat') {
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: promptToSend }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}: ${res.statusText}`)
        assistantMsg = {
          id: 'asst_' + Date.now(),
          role: 'assistant',
          agent: 'Chat',
          content: data.response,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      } else if (agentToUse === 'supervisor') {
        const recentHistory = messages.slice(-6).map(m => ({
          role: m.role,
          content: m.content,
          agent: m.agent,
        }))
        const res = await fetch(`${API_BASE}/agents/supervisor`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task: promptToSend, history: recentHistory }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}: ${res.statusText}`)

        // Format supervisor response
        let contentText = data.summary || 'Task orchestrated successfully.'
        if (data.results) {
          if (data.results.memory && data.results.memory.matches) {
            contentText += `\n\n**Retrieved Memory Facts (${data.results.memory.matches.length}):**\n`
            data.results.memory.matches.forEach((m, i) => {
              const val = m.value || m.content || JSON.stringify(m)
              contentText += `- **${m.key || 'Fact ' + (i + 1)}**: ${val}\n`
            })
          }
          if (data.results.coding && data.results.coding.final_response) {
            contentText += `\n\n### Coding Agent Output:\n${data.results.coding.final_response}`
          }
          if (data.results.review && data.results.review.final_response) {
            contentText += `\n\n### Review Agent Output:\n${data.results.review.final_response}`
          }
          if (data.results.testing && data.results.testing.final_response) {
            contentText += `\n\n### Testing Agent Output:\n${data.results.testing.final_response}`
          }
        }

        assistantMsg = {
          id: 'asst_' + Date.now(),
          role: 'assistant',
          agent: 'ProjectMind AI',
          routing_plan: data.routing_plan,
          stages_executed: data.stages_executed,
          content: contentText,
          success: data.success,
          isError: data.success === false,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      } else {
        // Individual specialized agent run with conversational context
        let contextualTask = promptToSend
        const lowerPrompt = promptToSend.toLowerCase().trim()
        const isReferential = ['it', 'this', 'that', 'the code', 'the above'].some(w => lowerPrompt.includes(w)) || lowerPrompt.split(' ').length <= 3
        if (isReferential && messages.length > 0) {
          const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant')
          if (lastAssistant && lastAssistant.content) {
            contextualTask = `${promptToSend}\n\nContext from previous turn:\n${lastAssistant.content.slice(0, 2000)}`
          }
        }
        const res = await fetch(`${API_BASE}/agents/${agentToUse}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task: contextualTask, top_k_rag: topKRag }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}: ${res.statusText}`)

        const currentAgentMeta = allAgents.find(a => a.id === agentToUse)
        assistantMsg = {
          id: 'asst_' + Date.now(),
          role: 'assistant',
          agent: currentAgentMeta?.name || data.agent || agentToUse,
          steps: data.steps || [],
          turns_executed: data.turns_executed,
          content: data.final_response || 'Task completed.',
          success: data.success,
          isError: data.success === false,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      }

      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      const isNetworkErr = err.message.toLowerCase().includes('failed to fetch')
      setMessages(prev => [
        ...prev,
        {
          id: 'err_' + Date.now(),
          role: 'assistant',
          agent: 'System',
          isError: true,
          content: isNetworkErr
            ? `⚠️ **Backend Offline / Connection Refused:**\n\nCould not reach the server at \`${API_BASE}\`. Please ensure the backend is running with:\n\`\`\`powershell\npython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload\n\`\`\``
            : `⚠️ **Execution Error:** ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const selectedAgentMeta = allAgents.find(a => a.id === activeAgent) || PRIMARY_AGENTS[0]
  const filteredFiles = projectFiles.filter(f =>
    f.path.toLowerCase().includes(fileSearch.toLowerCase())
  )

  return (
    <div className="workspace-root">
      {/* Top Bar */}
      <header className="workspace-topbar">
        <div className="workspace-topbar-left">
          <button className="workspace-back-btn" onClick={onBack} title="Return to Landing Page">
            <ArrowLeft size={16} />
            <span>Home</span>
          </button>
          <div className="workspace-brand-pill">
            <Orbit size={16} className="text-violet-400" />
            <span className="font-semibold">ProjectMind</span>
            <span className="workspace-brand-badge">WORKSPACE</span>
          </div>
        </div>

        <div className="workspace-topbar-center">
          <div className="workspace-security-badge" title="Host execution isolated within sandbox guardrails">
            <ShieldCheck size={14} className="text-emerald-400" />
            <span>Host Sandbox Active</span>
          </div>
          {projectSummary && (
            <div className="workspace-stats-pill">
              <span>{projectSummary.total_files} files</span>
              <span className="pill-dot">·</span>
              <span>{(projectSummary.total_lines_of_code ?? projectSummary.total_lines ?? 0).toLocaleString()} LOC</span>
            </div>
          )}
        </div>

        <div className="workspace-topbar-right">
          {/* Quick Drawer Toggles */}
          <button
            className={`workspace-drawer-btn ${activeDrawer === 'files' ? 'active' : ''}`}
            onClick={() => openDrawer(activeDrawer === 'files' ? null : 'files')}
          >
            <FolderGit2 size={15} />
            <span>Files</span>
          </button>
          <button
            className={`workspace-drawer-btn ${activeDrawer === 'memory' ? 'active' : ''}`}
            onClick={() => openDrawer(activeDrawer === 'memory' ? null : 'memory')}
          >
            <Brain size={15} />
            <span>Memory</span>
          </button>
          <button
            className={`workspace-drawer-btn ${activeDrawer === 'scorecard' ? 'active' : ''}`}
            onClick={() => openDrawer(activeDrawer === 'scorecard' ? null : 'scorecard')}
          >
            <Gauge size={15} />
            <span>Scorecard</span>
          </button>

          {user && (
            <div className="workspace-user-chip">
              <User size={13} />
              <span>{user.username}</span>
            </div>
          )}
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="workspace-layout">
        {/* Left Functional Tools Sidebar */}
        <aside className="workspace-sidebar">
          <div className="sidebar-section-title">
            <span>PROJECT TOOLS</span>
            <span className="sidebar-count">3 available</span>
          </div>

          <div className="agent-selector-list">
            <button
              className={`agent-selector-card ${activeDrawer === 'files' ? 'selected' : ''}`}
              onClick={() => openDrawer(activeDrawer === 'files' ? null : 'files')}
              title="Explore project code & files"
            >
              <div className="agent-card-icon" style={{ color: '#a78bfa' }}>
                <FolderGit2 size={18} />
              </div>
              <div className="agent-card-text">
                <div className="agent-card-header">
                  <span className="agent-card-name">Files</span>
                  <span className="agent-card-badge">
                    {projectSummary ? `${projectSummary.total_files} files` : 'EXPLORER'}
                  </span>
                </div>
                <p className="agent-card-role">Source code & directory explorer</p>
              </div>
            </button>

            <button
              className={`agent-selector-card ${activeDrawer === 'memory' ? 'selected' : ''}`}
              onClick={() => openDrawer(activeDrawer === 'memory' ? null : 'memory')}
              title="Inspect architecture decisions & persistent facts"
            >
              <div className="agent-card-icon" style={{ color: '#38bdf8' }}>
                <Brain size={18} />
              </div>
              <div className="agent-card-text">
                <div className="agent-card-header">
                  <span className="agent-card-name">Memory</span>
                  <span className="agent-card-badge">
                    {memoryFacts.length ? `${memoryFacts.length} facts` : 'KNOWLEDGE'}
                  </span>
                </div>
                <p className="agent-card-role">Persistent architecture facts & ADRs</p>
              </div>
            </button>

            <button
              className={`agent-selector-card ${activeDrawer === 'scorecard' ? 'selected' : ''}`}
              onClick={() => openDrawer(activeDrawer === 'scorecard' ? null : 'scorecard')}
              title="View benchmark evaluation scorecards"
            >
              <div className="agent-card-icon" style={{ color: '#f472b6' }}>
                <Gauge size={18} />
              </div>
              <div className="agent-card-text">
                <div className="agent-card-header">
                  <span className="agent-card-name">Scorecard</span>
                  <span className="agent-card-badge">BENCHMARKS</span>
                </div>
                <p className="agent-card-role">Evaluation metrics & benchmark suite</p>
              </div>
            </button>
          </div>

          <div className="sidebar-footer-box">
            <div className="sidebar-footer-title">
              <Sparkles size={14} className="text-violet-400" />
              <span>Context & RAG</span>
            </div>
            <p className="sidebar-footer-desc">
              Automatic RAG vector context chunks injected per query:
            </p>
            <div className="rag-chunk-selector">
              {[1, 2, 5].map(k => (
                <button
                  key={k}
                  className={`rag-chunk-btn ${topKRag === k ? 'active' : ''}`}
                  onClick={() => setTopKRag(k)}
                >
                  Top {k}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Center Chat & Execution Canvas */}
        <main className="workspace-chat-canvas">
          {/* Active Mode Banner */}
          <div className="chat-canvas-header">
            <div className="active-agent-info">
              <div className="active-agent-avatar" style={{ color: '#a78bfa' }}>
                <Orbit size={20} className="text-violet-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="active-agent-heading">ProjectMind Assistant</h3>
                  <span className="active-agent-tag">INTELLIGENT WORKSPACE</span>
                </div>
                <p className="active-agent-sub">
                  Context-aware assistant for codebase comprehension, feature implementation, and automated testing.
                </p>
              </div>
            </div>

            <button
              className="clear-chat-btn"
              onClick={() =>
                setMessages([
                  {
                    id: 'init_' + Date.now(),
                    role: 'assistant',
                    agent: 'ProjectMind AI',
                    content: 'Session cleared. Ready for your instructions.',
                    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                  },
                ])
              }
              title="Reset conversation"
            >
              <RotateCcw size={14} />
              <span>Clear</span>
            </button>
          </div>


          {/* Messages Stream */}
          <div className="messages-stream">
            {messages.map(msg => {
              const isUser = msg.role === 'user'
              return (
                <div key={msg.id} className={`message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
                  <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'} ${msg.isError ? 'error-bubble' : ''}`}>
                    {/* Header */}
                    <div className="message-header">
                      <span className="message-author">
                        {isUser ? (
                          <>
                            <User size={13} /> {user?.username || 'You'}
                          </>
                        ) : (
                          <>
                            <Bot size={13} /> {msg.agent || 'ProjectMind AI'}
                          </>
                        )}
                      </span>
                      <span className="message-timestamp">{msg.timestamp}</span>
                    </div>

                    {/* Routing plan banner if supervisor */}
                    {msg.routing_plan && (
                      <div className="routing-plan-banner">
                        <div className="routing-badge">
                          <Sparkles size={13} />
                          <span>Dynamic Routing: {msg.routing_plan.intent}</span>
                        </div>
                        {msg.routing_plan.pipeline && (
                          <div className="routing-pipeline">
                            Pipeline: {msg.routing_plan.pipeline.join(' ➔ ')}
                          </div>
                        )}
                        {msg.routing_plan.reasoning && (
                          <p className="routing-reasoning">{msg.routing_plan.reasoning}</p>
                        )}
                      </div>
                    )}

                    {/* Collapsible ReAct Trace Steps if present */}
                    {msg.steps && msg.steps.length > 0 && (
                      <div className="react-trace-container">
                        <div className="trace-summary-header">
                          <Terminal size={14} className="text-violet-400" />
                          <span>ReAct Execution Trace ({msg.steps.length} turns executed)</span>
                        </div>
                        <div className="trace-steps-list">
                          {msg.steps.map((st, sIdx) => (
                            <ReActStepItem key={sIdx} step={st} index={sIdx} />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Message Body */}
                    <div className="message-content">
                      <FormattedContent content={msg.content} />
                    </div>
                  </div>
                </div>
              )
            })}

            {loading && (
              <div className="message-row assistant-row">
                <div className="message-bubble assistant-bubble loading-bubble">
                  <div className="loading-state">
                    <Loader2 size={18} className="animate-spin text-violet-400" />
                    <span>ProjectMind analyzing context and executing task...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Prompt Console */}
          <div className="prompt-console-wrapper">
            <form
              className="prompt-console"
              onSubmit={e => {
                e.preventDefault()
                handleSend()
              }}
            >
              <textarea
                className="prompt-input"
                rows={2}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                placeholder="Ask ProjectMind or type task instructions... (Enter to send, Shift+Enter for newline)"
              />

              <div className="prompt-actions">
                <span className="prompt-agent-tag">
                  Target: <strong>ProjectMind AI</strong>
                </span>

                <button
                  type="submit"
                  className="prompt-send-btn"
                  disabled={loading || !input.trim()}
                  title="Execute Prompt"
                >
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                  <span>{loading ? 'Processing' : 'Run'}</span>
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>

      {/* Right Slide-Over Drawer */}
      {activeDrawer && (
        <div className="workspace-drawer-backdrop" onClick={() => setActiveDrawer(null)}>
          <aside className="workspace-drawer-panel" onClick={e => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-title">
                {activeDrawer === 'files' && (
                  <>
                    <FolderGit2 size={18} className="text-violet-400" />
                    <span>Project File Explorer</span>
                  </>
                )}
                {activeDrawer === 'memory' && (
                  <>
                    <Brain size={18} className="text-cyan-400" />
                    <span>Project Memory & ADRs</span>
                  </>
                )}
                {activeDrawer === 'scorecard' && (
                  <>
                    <Gauge size={18} className="text-pink-400" />
                    <span>Evaluation Scorecard</span>
                  </>
                )}
              </div>
              <button className="drawer-close-btn" onClick={() => setActiveDrawer(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="drawer-content">
              {/* FILES DRAWER */}
              {activeDrawer === 'files' && (
                <div className="files-drawer-view">
                  <div className="drawer-search-wrap">
                    <Search size={14} />
                    <input
                      type="text"
                      placeholder="Filter files by name or path..."
                      value={fileSearch}
                      onChange={e => setFileSearch(e.target.value)}
                    />
                  </div>

                  {selectedFile ? (
                    <div className="file-preview-card">
                      <div className="file-preview-header">
                        <span className="font-mono text-xs text-violet-300">{selectedFile.path}</span>
                        <div className="flex gap-2">
                          <button
                            className="file-action-btn"
                            onClick={() => {
                              setInput(prev => `${prev ? prev + '\n' : ''}Please analyze file \`${selectedFile.path}\`:`)
                              setActiveDrawer(null)
                            }}
                          >
                            Use in Prompt
                          </button>
                          <button className="file-action-btn" onClick={() => setSelectedFile(null)}>
                            Close
                          </button>
                        </div>
                      </div>
                      <pre className="file-preview-pre">
                        <code>{selectedFile.content}</code>
                      </pre>
                    </div>
                  ) : (
                    <div className="file-list-view">
                      <div className="file-list-meta">
                        Showing {filteredFiles.length} of {projectFiles.length} files
                      </div>
                      <div className="file-scroll-list">
                        {filteredFiles.map(file => (
                          <div
                            key={file.path}
                            className="file-item-row"
                            onClick={() => readFileContent(file.path)}
                          >
                            <FileCode size={14} className="text-muted" />
                            <span className="file-item-name">{file.path}</span>
                            <span className="file-item-size">
                              {file.size_bytes ? `${Math.round(file.size_bytes / 1024)} KB` : ''}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* MEMORY DRAWER */}
              {activeDrawer === 'memory' && (
                <div className="memory-drawer-view">
                  {memoryStats && (
                    <div className="memory-stats-grid">
                      <div className="memory-stat-card">
                        <span className="memory-stat-val">{memoryStats.total_facts}</span>
                        <span className="memory-stat-lbl">Memory Facts</span>
                      </div>
                      <div className="memory-stat-card">
                        <span className="memory-stat-val">{memoryStats.total_decisions}</span>
                        <span className="memory-stat-lbl">Architectural Decisions</span>
                      </div>
                    </div>
                  )}

                  <div className="drawer-subtitle">PERSISTENT KNOWLEDGE BASE</div>
                  <div className="memory-facts-list">
                    {memoryFacts.map((fact, idx) => (
                      <div key={idx} className="memory-fact-card">
                        <div className="memory-fact-header">
                          <span className="memory-fact-key">{fact.key}</span>
                          <span className="memory-fact-category">{fact.category}</span>
                        </div>
                        <p className="memory-fact-value">{fact.value}</p>
                        {fact.tags && (
                          <div className="memory-fact-tags">
                            {fact.tags.map((t, tIdx) => (
                              <span key={tIdx} className="fact-tag">
                                #{t}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SCORECARD DRAWER */}
              {activeDrawer === 'scorecard' && (
                <div className="scorecard-drawer-view">
                  <div className="scorecard-actions">
                    <button
                      className="primary-button run-bench-btn"
                      onClick={triggerEvaluation}
                      disabled={scorecardLoading}
                    >
                      {scorecardLoading ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          <span>Running Benchmark Suite...</span>
                        </>
                      ) : (
                        <>
                          <Play size={14} />
                          <span>Run Benchmark Suite (10 Tasks)</span>
                        </>
                      )}
                    </button>
                  </div>

                  {scorecardMd ? (
                    <div className="scorecard-markdown-wrap">
                      <FormattedContent content={scorecardMd} />
                    </div>
                  ) : (
                    <div className="scorecard-empty">
                      <Gauge size={32} className="text-violet-400 mb-2" />
                      <h4>No Benchmark Run In This Session</h4>
                      <p>
                        Click "Run Benchmark Suite" above to execute the Phase 25 Evaluation Harness
                        across code generation, refactoring, and security tasks.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}

