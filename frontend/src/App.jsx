import { useState, useEffect } from 'react'
import { ArrowDown, ArrowRight, ArrowUpRight, AudioLines, Bot, BrainCircuit, ChevronLeft, CircleHelp, Eye, EyeOff, FileText, LockKeyhole, Mail, Menu, MessageCircle, Orbit, ShieldCheck, Sparkles, UserRound, X, Check, CheckCircle2, Loader2 } from 'lucide-react'
import CosmicStarfield from './components/CosmicStarfield.jsx'
import EnergyPlanet from './components/EnergyPlanet.jsx'
import Workspace from './components/Workspace.jsx'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8081'

const capabilities = [
  {
    icon: MessageCircle,
    title: 'Chat with AI',
    text: 'Think through ideas, solve problems, and explore questions with your AI workspace.',
    tag: 'CONVERSATIONS',
    subtitle: 'Conversational reasoning and code assistance tailored to your repository context.',
    brief: 'Engage in natural, repository-aware dialogues with ProjectMind AI. You can discuss architecture decisions, debug complex errors, analyze implementation trade-offs, and receive step-by-step programming guidance. Context carries across messages, and project memory facts are preserved across your session so you don\'t have to re-explain your stack.',
    highlights: [
      'Repository-grounded natural conversation',
      'Multi-turn architectural reasoning',
      'Direct bug diagnosis & code explanation',
      'Persistent memory across session turns'
    ]
  },
  {
    icon: Bot,
    title: 'Specialized agents',
    text: 'Bring focused assistance to coding, reviewing, testing, and research workflows.',
    tag: 'AI AGENTS',
    subtitle: 'Autonomous multi-agent orchestration for specialized development tasks.',
    brief: 'ProjectMind leverages specialized agent roles to divide and conquer software engineering tasks: a Coding Agent writes clean, production-ready code with sandbox protections; a Review Agent performs AST syntax validation and security compliance audits; and a Testing Agent builds and runs test suites to prevent regressions.',
    highlights: [
      'Autonomous multi-stage execution',
      'Dedicated full-stack coding specialist',
      'AST validation & security vulnerability scans',
      'Automated test generation & execution'
    ]
  },
  {
    icon: BrainCircuit,
    title: 'Knowledge retrieval',
    text: 'Find useful context across your project knowledge and documents.',
    tag: 'YOUR KNOWLEDGE',
    subtitle: 'Vector embeddings and RAG pipeline for codebase search.',
    brief: 'ProjectMind indexes your files, docstrings, architectural decisions, and documentation into vector embeddings. When you ask questions or assign tasks, the RAG (Retrieval-Augmented Generation) pipeline semantically retrieves the most relevant code chunks and injects them directly into the prompt context to ensure factual, hallucination-free answers.',
    highlights: [
      'High-speed semantic vector search',
      'Configurable Top-K chunk injection',
      'Project-specific code & doc embeddings',
      'Accurate grounding in real repository files'
    ]
  },
  {
    icon: FileText,
    title: 'File analysis',
    text: 'Explore documents and extract the details that matter to your work.',
    tag: 'DOCUMENTS',
    subtitle: 'Deep source code inspection, line metrics, and syntax verification.',
    brief: 'Inspect and understand the complete structure of your software project. ProjectMind provides detailed file trees, lines of code (LOC) metrics, instant file content previews, and syntax analysis. You can pull any file directly into your conversation prompt or inspect changes with surgical precision.',
    highlights: [
      'Live repository file explorer',
      'Lines of code (LOC) & file metrics',
      'Instant file content inspection & search',
      'Direct file insertion into prompt context'
    ]
  },
]

function Brand({ onHome, compact = false }) {
  return <button className={`brand ${compact ? 'brand-compact' : ''}`} onClick={onHome} aria-label="ProjectMind AI home"><span className="brand-mark"><Orbit size={19} /></span><span>ProjectMind<span className="brand-ai"> AI</span></span></button>
}

function AuthShell({ children, onHome }) {
  return <main className="auth-shell site-shell"><CosmicStarfield /><header className="auth-topbar"><Brand onHome={onHome} /><button className="auth-back-home" onClick={onHome}><ChevronLeft size={15}/> Back to home</button></header><div className="auth-layout"><section className="auth-art"><div className="auth-art-glow"/><div className="auth-orb"><EnergyPlanet /></div><div className="auth-art-copy"><div className="eyebrow"><span className="status-dot"/> YOUR INTELLIGENT WORKSPACE</div><h1>Ideas deserve<br/><span>their own universe.</span></h1><p>One focused space for building, exploring, and bringing your next big idea to life.</p><div className="auth-trust"><ShieldCheck size={15}/> Thoughtfully designed for curious minds</div></div><div className="auth-art-foot">PROJECTMIND AI <span>·</span> THINK BEYOND BOUNDARIES</div></section><section className="auth-form-side">{children}</section></div><footer className="auth-footer"><span>© 2026 ProjectMind AI</span><span>Secure access to your intelligent workspace</span><button onClick={onHome}><CircleHelp size={13}/> About ProjectMind</button></footer></main>
}

function PasswordField({ label, value, onChange, placeholder = 'Enter your password', autoComplete = 'current-password' }) {
  const [visible, setVisible] = useState(false)
  return <label className="auth-field"><span>{label}</span><div className="auth-input-wrap"><LockKeyhole size={16}/><input type={visible ? 'text' : 'password'} value={value} onChange={onChange} placeholder={placeholder} autoComplete={autoComplete} required minLength={8}/><button type="button" className="password-toggle" onClick={() => setVisible(!visible)} aria-label={visible ? 'Hide password' : 'Show password'}>{visible ? <EyeOff size={16}/> : <Eye size={16}/>}</button></div></label>
}

function AuthMessage({ children, type = 'error' }) { return children ? <div className={`auth-message ${type}`} role="status">{type === 'success' ? <CheckCircle2 size={15}/> : <CircleHelp size={15}/>}<span>{children}</span></div> : null }

function Login({ go, onHome, onLoginSuccess }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [message, setMessage] = useState('')
  const [msgType, setMsgType] = useState('error')
  const [loading, setLoading] = useState(false)

  const submit = async e => {
    e.preventDefault()
    setLoading(true)
    setMessage('')
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email: email.trim(), password }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setMsgType('error')
        setMessage(data.detail || 'Invalid email or password.')
      } else {
        setMsgType('success')
        setMessage('Welcome back! Successfully signed in.')
        if (onLoginSuccess) {
          onLoginSuccess(data.user)
        }
        setTimeout(() => go('workspace'), 700)
      }
    } catch (err) {
      setMsgType('error')
      setMessage('Cannot connect to ProjectMind backend. Ensure server is running on ' + API_BASE)
    } finally {
      setLoading(false)
    }
  }

  return <div className="auth-card-wrap"><div className="auth-mobile-brand"><Brand onHome={onHome}/></div><div className="auth-card"><div className="auth-card-kicker"><span className="auth-kicker-icon"><Sparkles size={15}/></span> YOUR WORKSPACE AWAITS</div><h2>Welcome back<span>.</span></h2><p className="auth-subtitle">Sign in to continue where your ideas left off.</p><form onSubmit={submit} className="auth-form"><label className="auth-field"><span>Email address</span><div className="auth-input-wrap"><Mail size={16}/><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required/></div></label><PasswordField label="Password" value={password} onChange={e => setPassword(e.target.value)}/><div className="auth-options"><label className="remember-label"><input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)}/><span className="custom-check"><Check size={11}/></span> Remember me</label><button type="button" className="text-action" onClick={() => go('forgot')}>Forgot password?</button></div><AuthMessage type={msgType}>{message}</AuthMessage><button className="auth-submit" type="submit" disabled={loading}>{loading ? 'Signing in...' : <>Sign in <ArrowRight size={17}/></>}</button></form><div className="auth-divider"><span/> <small>OR CONTINUE WITH</small> <span/></div><button className="google-button" type="button" onClick={() => { setMsgType('error'); setMessage('Google sign-in will be enabled when OAuth is connected to the backend.') }}><span className="google-g">G</span> Continue with Google</button><p className="auth-switch">New to ProjectMind? <button onClick={() => go('signup')}>Create an account</button></p></div><p className="auth-legal">By continuing, you agree to our <button onClick={() => { setMsgType('error'); setMessage('Terms of Service will be published before launch.') }}>Terms of Service</button> and <button onClick={() => { setMsgType('error'); setMessage('Privacy Policy will be published before launch.') }}>Privacy Policy</button>.</p></div>
}

function Signup({ go, onHome, onSignupSuccess }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [message, setMessage] = useState('')
  const [msgType, setMsgType] = useState('error')
  const [loading, setLoading] = useState(false)

  const strength = [password.length >= 8, /[A-Z]/.test(password) && /[a-z]/.test(password), /\d/.test(password), /[^A-Za-z0-9]/.test(password)].filter(Boolean).length

  const submit = async e => {
    e.preventDefault()
    if (password !== confirm) {
      setMsgType('error')
      return setMessage('Your passwords do not match. Please check them.')
    }
    if (!accepted) {
      setMsgType('error')
      return setMessage('Please accept the Terms of Service and Privacy Policy to continue.')
    }
    setLoading(true)
    setMessage('')

    try {
      const cleanUsername = name.trim().toLowerCase().replace(/[^a-z0-9_]/g, '_').slice(0, 32) || 'user_' + Date.now().toString().slice(-4)
      const username = cleanUsername.length < 3 ? cleanUsername + '_dev' : cleanUsername

      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          email: email.trim(),
          password,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setMsgType('error')
        setMessage(data.detail || 'Registration failed. Please check your credentials.')
      } else {
        // Attempt immediate login so user directly enters their workspace
        try {
          const loginRes = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email: email.trim(), password }),
          })
          if (loginRes.ok) {
            const loginData = await loginRes.json()
            if (onSignupSuccess) onSignupSuccess(loginData.user)
            setMsgType('success')
            setMessage('Account created! Entering your workspace...')
            setTimeout(() => go('workspace'), 800)
            return
          }
        } catch (_) {}
        setMsgType('success')
        setMessage('Account created successfully in MongoDB! Redirecting to sign in...')
        setTimeout(() => go('login'), 1200)
      }
    } catch (err) {
      setMsgType('error')
      setMessage('Cannot connect to ProjectMind backend. Ensure server is running on ' + API_BASE)
    } finally {
      setLoading(false)
    }
  }

  return <div className="auth-card-wrap"><div className="auth-mobile-brand"><Brand onHome={onHome}/></div><div className="auth-card signup-card"><div className="auth-card-kicker"><span className="auth-kicker-icon"><Sparkles size={15}/></span> START YOUR JOURNEY</div><h2>Create your account<span>.</span></h2><p className="auth-subtitle">Build a space where your best ideas can grow.</p><form onSubmit={submit} className="auth-form"><label className="auth-field"><span>Full name</span><div className="auth-input-wrap"><UserRound size={16}/><input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" autoComplete="name" required/></div></label><label className="auth-field"><span>Email address</span><div className="auth-input-wrap"><Mail size={16}/><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required/></div></label><PasswordField label="Create password" value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" autoComplete="new-password"/><div className="password-strength"><div className="strength-bars">{[1,2,3,4].map(n => <i key={n} className={strength >= n ? 'filled' : ''}/>)}</div><span>{password ? ['Weak','Fair','Good','Strong'][Math.max(0,strength-1)] : 'Use 8+ characters with a mix of letters and numbers'}</span></div><PasswordField label="Confirm password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Re-enter your password" autoComplete="new-password"/><label className="remember-label terms-check"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)}/><span className="custom-check"><Check size={11}/></span><span>I agree to the <button type="button" onClick={() => { setMsgType('error'); setMessage('Terms of Service will be published before launch.') }}>Terms of Service</button> and <button type="button" onClick={() => { setMsgType('error'); setMessage('Privacy Policy will be published before launch.') }}>Privacy Policy</button>.</span></label><AuthMessage type={msgType}>{message}</AuthMessage><button className="auth-submit" type="submit" disabled={loading}>{loading ? 'Creating account...' : <>Create account <ArrowRight size={17}/></>}</button></form><p className="auth-switch">Already have an account? <button onClick={() => go('login')}>Sign in</button></p></div></div>
}

function Forgot({ go, onHome }) {
  const [email, setEmail] = useState(''); const [sent, setSent] = useState(false)
  return <div className="auth-card-wrap"><div className="auth-mobile-brand"><Brand onHome={onHome}/></div><div className="auth-card forgot-card"><div className="auth-card-kicker"><span className="auth-kicker-icon"><Mail size={15}/></span> ACCOUNT RECOVERY</div><div className="forgot-symbol"><Mail size={25}/></div>{sent ? <><h2>Check your inbox<span>.</span></h2><p className="auth-subtitle">If an account exists for <strong>{email}</strong>, password reset instructions will be sent there once email delivery is connected.</p><button className="auth-submit" onClick={() => go('login')}>Back to sign in <ArrowRight size={17}/></button></> : <><h2>Forgot password<span>?</span></h2><p className="auth-subtitle">No worries. Enter your account email and we'll help you get back in.</p><form className="auth-form" onSubmit={e => {e.preventDefault(); setSent(true)}}><label className="auth-field"><span>Email address</span><div className="auth-input-wrap"><Mail size={16}/><input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required/></div></label><button className="auth-submit" type="submit">Send reset link <ArrowRight size={17}/></button></form></>}<p className="auth-switch"><button onClick={() => go('login')}><ChevronLeft size={14}/> Back to sign in</button></p></div></div>
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [page, setPage] = useState(() => {
    const hash = window.location.hash.replace('#', '')
    return ['workspace', 'login', 'signup', 'forgot'].includes(hash) ? hash : 'home'
  })
  const [showNotice, setShowNotice] = useState(false)
  const [currentUser, setCurrentUser] = useState(null)

  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '')
      if (['workspace', 'login', 'signup', 'forgot', 'home'].includes(hash)) {
        setPage(hash || 'home')
      }
    }
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])

  useEffect(() => {
    // Check if user already has an active session cookie on load
    fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
      .then(res => res.ok ? res.json() : null)
      .then(user => { if (user) setCurrentUser(user) })
      .catch(() => {})
  }, [])

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' })
    } catch (e) {}
    setCurrentUser(null)
  }

  const navigate = next => { setPage(next); setMenuOpen(false); window.scrollTo({ top: 0, behavior: 'smooth' }); window.history.replaceState(null, '', next === 'home' ? window.location.pathname : `#${next}`) }
  const enterProject = () => { document.getElementById('capabilities')?.scrollIntoView({ behavior: 'smooth' }) }

  // Strict authentication requirement before entering workspace
  const handleOpenWorkspace = () => {
    if (currentUser) {
      navigate('workspace')
    } else {
      navigate('login')
    }
  }

  if (page === 'workspace') {
    if (!currentUser) {
      navigate('login')
      return null
    }
    return <Workspace user={currentUser} onBack={() => navigate('home')} />
  }

  if (page !== 'home') {
    return (
      <AuthShell onHome={() => navigate('home')}>
        {page === 'login' ? (
          <Login go={navigate} onHome={() => navigate('home')} onLoginSuccess={user => setCurrentUser(user)} />
        ) : page === 'signup' ? (
          <Signup go={navigate} onHome={() => navigate('home')} onSignupSuccess={user => setCurrentUser(user)} />
        ) : (
          <Forgot go={navigate} onHome={() => navigate('home')} />
        )}
      </AuthShell>
    )
  }

  return <main className="site-shell"><CosmicStarfield/><header className="topbar"><Brand onHome={() => navigate('home')}/><button className="mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation">{menuOpen ? <X size={20}/> : <Menu size={20}/>}</button><nav className={menuOpen ? 'nav-links nav-open' : 'nav-links'} aria-label="Main navigation"><a href="#home" onClick={() => setMenuOpen(false)}>Home</a><a href="#capabilities" onClick={() => setMenuOpen(false)}>Capabilities</a><a href="#about" onClick={() => setMenuOpen(false)}>About</a>{currentUser && <button onClick={() => navigate('workspace')} style={{ background: 'transparent', border: 0, color: '#c4a4ff', cursor: 'pointer', padding: 0, fontWeight: 600 }}>Workspace</button>}</nav>{currentUser ? (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <button className="sign-in" onClick={() => navigate('workspace')} style={{ borderColor: 'rgba(196,164,255,0.4)', background: 'rgba(196,164,255,0.1)' }}>
        <Sparkles size={14} className="text-violet-400" /> Workspace
      </button>
      <span className="sign-in" style={{ cursor: 'default', color: '#c4a4ff' }}>
        <UserRound size={14} /> {currentUser.username}
      </span>
      <button className="sign-in" onClick={handleLogout} style={{ opacity: 0.85 }}>
        Sign out
      </button>
    </div>
  ) : (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <button className="sign-in" onClick={handleOpenWorkspace} style={{ borderColor: 'rgba(196,164,255,0.3)' }}>
        <Sparkles size={14} /> Workspace
      </button>
      <button className="sign-in" onClick={() => navigate('login')}>
        Sign in <ArrowUpRight size={15}/>
      </button>
    </div>
  )}</header>
    <section className="hero" id="home"><div className="hero-copy"><div className="eyebrow"><span className="status-dot"/> YOUR INTELLIGENT WORKSPACE</div><h1>Think beyond<br/><span>boundaries.</span></h1><p className="hero-subtitle">A new orbit for your ideas. Bring coding, research, and discovery into one intelligent workspace.</p><div className="hero-actions"><button className="primary-button" onClick={handleOpenWorkspace}>Open Workspace <ArrowRight size={17}/></button><a className="secondary-button" href="#capabilities">Explore capabilities <ArrowDown size={15}/></a></div><div className="trust-line"><ShieldCheck size={15}/> Built for focused thinking and meaningful work</div></div><div className="planet-stage" aria-label="Interactive animated energy orb"><div className="planet-halo"/><EnergyPlanet/><div className="planet-caption"><span className="caption-pulse"/> PROJECTMIND GALAXY <span className="caption-line"/></div><div className="floating-label label-one"><Sparkles size={14}/> A universe of ideas</div><div className="floating-label label-two"><AudioLines size={14}/> Move to explore</div></div><div className="hero-bottom-note"><span>01</span> AN INTELLIGENT SPACE FOR WHAT'S NEXT</div><a className="scroll-cue" href="#capabilities" aria-label="Scroll to capabilities"><span/> Scroll to explore</a></section>
    <section className="capabilities section-wrap" id="capabilities">
      <div className="section-heading">
        <div>
          <div className="eyebrow">ONE WORKSPACE. MANY POSSIBILITIES.</div>
          <h2>Everything you need to<br/><span>move ideas forward.</span></h2>
        </div>
        <p>Thoughtfully connected tools for turning questions into clarity and concepts into progress.</p>
      </div>
      <div className="capability-grid">
        {capabilities.map((cap, i) => {
          const { icon: Icon, title, text, tag } = cap;
          return (
            <article className="capability-card" key={title} style={{ '--card-index': i, cursor: 'default' }}>
              <div className="card-top">
                <span className="cap-icon"><Icon size={19}/></span>
                <span className="card-index">0{i+1}</span>
              </div>
              <div className="card-tag">{tag}</div>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          );
        })}
      </div>
    </section>
    <section className="about-strip section-wrap" id="about"><div className="about-orbit"><Orbit size={26}/></div><div><div className="eyebrow">MADE FOR CURIOSITY</div><h2>Your next idea starts <span>somewhere.</span></h2></div><a href="#home" className="back-top">Back to top <ArrowUpRight size={16}/></a></section><footer className="footer"><Brand onHome={() => navigate('home')} compact/><span>© 2026 ProjectMind AI · A workspace for curious minds.</span><button className="footer-help" onClick={() => setShowNotice(true)}><CircleHelp size={14}/> About this project</button></footer>
    {showNotice && <div className="notice-backdrop" onClick={() => setShowNotice(false)}><div className="notice-panel" role="dialog" aria-modal="true" onClick={e => e.stopPropagation()}><button className="notice-close" onClick={() => setShowNotice(false)}><X size={18}/></button><span className="notice-icon"><Sparkles size={22}/></span><div className="eyebrow">COMING IN THE NEXT PHASE</div><h2>The next orbit is taking shape.</h2><p>This capability will be part of your ProjectMind workspace. We're building the experience step by step.</p><button className="primary-button notice-action" onClick={() => setShowNotice(false)}>Sounds good <ArrowRight size={16}/></button></div></div>}
  </main>
}
