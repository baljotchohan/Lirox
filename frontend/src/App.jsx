import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  MessageSquare, Settings, User, ListChecks, Search, PlusCircle, 
  Key, Cpu, History, Info, Terminal, Save, CheckCircle2, X, 
  ShieldAlert, ArrowRight, ArrowLeft, ChevronDown, Activity, 
  RefreshCw, MousePointer2, AlertCircle, Sparkles, ExternalLink,
  Briefcase, GraduationCap, Globe
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

const App = () => {
  const [page, setPage] = useState('chat');
  const [profile, setProfile] = useState({});
  const [status, setStatus] = useState({ status: 'idle', pending_confirmation: false });
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState({ available: [], all: [] });

  // Initial Profile + Provider Fetch
  useEffect(() => {
    const init = async () => {
      try {
        const [profRes, provRes] = await Promise.all([
          axios.get(`${API_BASE}/profile`),
          axios.get(`${API_BASE}/providers`)
        ]);
        setProfile(profRes.data);
        setProviders(provRes.data);
        if (!profRes.data.user_name) setPage('setup');
      } catch (e) {
        console.error("Failed to fetch profile", e);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  // Status Polling
  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const res = await axios.get(`${API_BASE}/status`);
        setStatus(res.data);
      } catch (e) {
        console.error("Status check failed", e);
      }
    }, 2000);
    return () => clearInterval(poll);
  }, []);

  if (loading) return (
    <div style={{height:'100vh', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', background:'#f8fafc'}}>
      <RefreshCw size={48} className="spin" color="#3b82f6" />
      <div style={{marginTop:'1.5rem', fontWeight:'600', color:'#64748b', fontSize:'1.1rem'}}>Initializing Lirox Agent v0.4...</div>
    </div>
  );

  return (
    <div className="app-container" style={{display:'flex', height:'100vh', overflow:'hidden', background:'#f8fafc'}}>
      {/* Sidebar */}
      <nav style={{
        width: '280px', borderRight: '1px solid #e2e8f0', background: 'white',
        display: 'flex', flexDirection: 'column', padding: '2rem 1.25rem',
        boxShadow: '4px 0 24px rgba(0,0,0,0.02)'
      }}>
        <div style={{display:'flex', alignItems:'center', gap:'1rem', marginBottom:'3rem', padding:'0 0.5rem'}}>
          <div style={{
            width:'40px', height:'40px', background:'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', 
            borderRadius:'12px', display:'flex', alignItems:'center', justifyContent:'center', 
            color:'white', fontWeight:'900', fontSize:'1.25rem', boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)'
          }}>L</div>
          <div style={{display:'flex', flexDirection:'column'}}>
            <span style={{fontWeight:'800', fontSize:'1.1rem', color:'#0f172a', letterSpacing:'-0.02em'}}>LIROX</span>
            <span style={{fontSize:'0.7rem', fontWeight:'700', color:'#3b82f6', letterSpacing:'0.05em', marginTop:'-2px'}}>v0.4 PREMIUM</span>
          </div>
        </div>

        {/* No-key warning banner */}
        {providers.available.length === 0 && (
          <div style={{background:'#fff7ed', border:'1px solid #fed7aa', borderRadius:'12px', padding:'0.875rem 1rem', marginBottom:'1rem', cursor:'pointer'}} onClick={() => setPage('settings')}>
            <div style={{fontWeight:'800', color:'#c2410c', fontSize:'0.8rem', marginBottom:'0.25rem', display:'flex', alignItems:'center', gap:'0.4rem'}}>
              <Key size={14}/> No API Keys
            </div>
            <div style={{fontSize:'0.75rem', color:'#9a3412', lineHeight:'1.4'}}>Add a key in Settings to activate the agent.</div>
          </div>
        )}

        <div style={{display:'flex', flexDirection:'column', gap:'0.5rem'}}>
          <NavItem icon={<MessageSquare size={20}/>} label="Chat Console" active={page === 'chat'} onClick={() => setPage('chat')} />
          <NavItem icon={<ListChecks size={20}/>} label="Autonomous Tasks" active={page === 'task'} onClick={() => setPage('task')} />
          <NavItem icon={<User size={20}/>} label="Agent Profile" active={page === 'setup'} onClick={() => setPage('setup')} />
          <NavItem icon={<Settings size={20}/>} label="System Settings" active={page === 'settings'} onClick={() => setPage('settings')} />
        </div>

        <div style={{marginTop:'auto', padding:'1.5rem 1rem', background:'#f8fafc', borderRadius:'16px', border:'1px solid #e2e8f0'}}>
           <div style={{fontSize:'0.75rem', fontWeight:'800', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:'0.75rem'}}>Agent Status</div>
           <div style={{display:'flex', alignItems:'center', gap:'0.75rem'}}>
              <div style={{
                width:'10px', height:'10px', borderRadius:'50%', 
                background: status.status === 'idle' ? '#10b981' : '#f59e0b',
                boxShadow: status.status !== 'idle' ? '0 0 12px #f59e0b' : '0 0 8px rgba(16, 185, 129, 0.3)',
                transition: 'all 0.3s'
              }}></div>
              <span style={{fontSize:'0.875rem', fontWeight:'700', color:'#1e293b', textTransform:'capitalize'}}>
                {status.status.replace('_', ' ')}
              </span>
           </div>
           {status.status === 'thinking' && (
             <div style={{marginTop:'0.5rem', fontSize:'0.75rem', color:'#3b82f6', display:'flex', alignItems:'center', gap:'0.4rem'}}>
               <RefreshCw size={12} className="spin"/> Synthesizing thought...
             </div>
           )}
           {status.pending_confirmation && (
             <div style={{marginTop:'0.75rem', fontSize:'0.75rem', color:'#d97706', background:'#fffbeb', padding:'0.4rem 0.6rem', borderRadius:'6px', display:'flex', alignItems:'center', gap:'0.4rem', border:'1px solid #fef3c7'}}>
               <ShieldAlert size={14}/> Action Required
             </div>
           )}
           {providers.available.length > 0 && (
             <div style={{marginTop:'0.75rem', fontSize:'0.7rem', color:'#64748b', fontWeight:'600'}}>
               {providers.available.length} provider{providers.available.length > 1 ? 's' : ''} active
             </div>
           )}
        </div>
      </nav>

      {/* Main Content */}
      <main style={{flex:1, overflow:'hidden', position:'relative', background:'#f8fafc'}}>
        {page === 'chat' && <ChatPage profile={profile} status={status} />}
        {page === 'task' && <TaskPage profile={profile} status={status} />}
        {page === 'setup' && <SetupPage profile={profile} setProfile={setProfile} onComplete={() => setPage('chat')} />}
        {page === 'settings' && <SettingsPage providers={providers} setProviders={setProviders} />}
      </main>
    </div>
  );
};

const NavItem = ({ icon, label, active, onClick }) => (
  <button onClick={onClick} style={{
    display:'flex', alignItems:'center', gap:'1rem', padding:'0.875rem 1.25rem', width:'100%', borderRadius:'14px',
    background: active ? 'white' : 'transparent',
    color: active ? '#3b82f6' : '#64748b',
    fontWeight: active ? '700' : '600', border: active ? '1px solid #e2e8f0' : 'none', 
    boxShadow: active ? '0 4px 6px -1px rgba(0,0,0,0.05)' : 'none',
    cursor:'pointer', transition:'all 0.2s', fontSize:'0.9375rem'
  }}>{icon} <span>{label}</span></button>
);

const ThinkingTrace = ({ thought }) => (
  <div style={{
    marginTop:'1rem', padding:'1.25rem', background:'white', 
    borderRadius:'16px', border:'1px solid #e2e8f0',
    fontSize:'0.9rem', color:'#475569', lineHeight:'1.7',
    boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
  }}>
    <div style={{display:'flex', alignItems:'center', gap:'0.6rem', marginBottom:'1rem', fontWeight:'800', color:'#3b82f6', fontSize:'0.75rem', textTransform:'uppercase', letterSpacing:'0.05em'}}>
      <Activity size={16} className="spin" style={{opacity:0.8}}/> Internal Reasoning Path
    </div>
    <div style={{whiteSpace:'pre-wrap', fontStyle:'italic', opacity:0.85, background:'#fcfcfc', padding:'0.75rem', borderRadius:'8px', border:'1px dashed #e2e8f0'}}>{thought}</div>
  </div>
);

const SourcesGrid = ({ sources }) => (
  <div style={{marginTop:'1.5rem'}}>
    <div style={{fontSize:'0.75rem', fontWeight:'800', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:'1rem', display:'flex', alignItems:'center', gap:'0.5rem'}}>
      <Globe size={14}/> Verified Research Sources
    </div>
    <div style={{display:'flex', flexWrap:'wrap', gap:'0.75rem'}}>
      {sources.map((s, i) => (
        <a key={i} href={s.url} target="_blank" rel="noreferrer" className="source-link" style={{
          display:'flex', alignItems:'center', gap:'0.6rem', padding:'0.6rem 1rem', background:'white', 
          border:'1px solid #e2e8f0', borderRadius:'12px', textDecoration:'none', color:'inherit',
          transition:'all 0.2s', fontSize:'0.8rem', boxShadow:'0 1px 2px rgba(0,0,0,0.05)'
        }}>
          <img src={s.icon} alt="" style={{width:'16px', height:'16px', borderRadius:'3px'}} />
          <span style={{fontWeight:'700', color:'#1e293b', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', maxWidth:'120px'}}>{s.domain}</span>
          <ExternalLink size={12} style={{opacity:0.3}}/>
        </a>
      ))}
    </div>
    <style>{`
      .source-link:hover { border-color: #3b82f6; background: #eff6ff; transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    `}</style>
  </div>
);

const ChatPage = ({ profile, status: globalStatus }) => {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: `Greetings, ${profile.user_name || 'User'}. I am ${profile.agent_name || 'Lirox'}, your autonomous systems bridge. I'm equipped with deep research and terminal capabilities. How can I assist you today?` }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE}/chat`, { message: input });
      const data = res.data;
      
      if (data.type === 'task_pending') {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          type: 'confirmation',
          content: data.message,
          plan: data.plan,
          policy: data.policy,
          thought: data.thought
        }]);
      } else if (data.type === 'task_complete') {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.response, 
          reflection: data.reflection,
          thought: data.thought,
          sources: data.sources
        }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Error: Systems unreachable. Verify endpoint connectivity." }]);
    } finally {
      setLoading(false);
    }
  };

  const confirmPlan = async (confirmed) => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/confirm-run`, { confirmed });
      setMessages(prev => [...prev, { role: 'system', content: confirmed ? "Deployment Sequence Initiated." : "Sequence Aborted." }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'system', content: "Protocol error during confirmation." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{display:'flex', flexDirection:'column', height:'100%', padding:'2rem', maxWidth:'1100px', margin:'0 auto'}}>
       <div style={{flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:'2.5rem', paddingBottom:'2rem', paddingRight:'1rem'}}>
          {messages.map((m, i) => (
             <div key={i} className="fade-in" style={{
                display:'flex', flexDirection: m.role === 'user' ? 'row-reverse' : 'row', gap:'1.5rem', alignItems:'flex-start'
             }}>
                <div style={{
                   width:'48px', height:'48px', borderRadius:'16px', flexShrink:0,
                   background: m.role === 'user' ? '#3b82f6' : 'white',
                   border: m.role === 'user' ? 'none' : '1px solid #e2e8f0',
                   display:'flex', alignItems:'center', justifyContent:'center', color: m.role === 'user' ? 'white' : '#64748b',
                   boxShadow: m.role === 'user' ? '0 8px 16px rgba(37, 99, 235, 0.25)' : '0 4px 6px rgba(0,0,0,0.02)'
                }}>
                   {m.role === 'user' ? <User size={24}/> : <Cpu size={24}/>}
                </div>
                <div style={{ maxWidth:'82%', display:'flex', flexDirection:'column', gap:'0.75rem' }}>
                    <div className="card" style={{
                    padding:'1.5rem 2.25rem', fontSize:'1.05rem', lineHeight:'1.8',
                    background: m.role === 'user' ? 'white' : m.type === 'confirmation' ? '#fffbeb' : 'white',
                    color: '#1e293b',
                    borderRadius: m.role === 'user' ? '24px 24px 4px 24px' : '24px 24px 24px 4px',
                    boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.05)',
                    border: '1px solid #e2e8f0'
                    }}>
                    {m.type === 'confirmation' ? (
                        <div>
                        <div style={{fontWeight:'800', marginBottom:'1rem', display:'flex', alignItems:'center', gap:'0.6rem', color:'#d97706'}}>
                            <ShieldAlert size={22}/> Security Gateway
                        </div>
                        <p style={{fontSize:'1.1rem'}}>{m.content}</p>
                        {m.thought && <ThinkingTrace thought={m.thought} />}
                        <div style={{marginTop:'1.5rem', padding:'1.25rem', background:'rgba(217, 119, 6, 0.05)', borderRadius:'14px', fontSize:'0.9rem', border:'1px dashed rgba(217, 119, 6, 0.2)'}}>
                            <strong style={{color:'#d97706', fontSize:'0.8rem', textTransform:'uppercase', letterSpacing:'0.05em', display:'block', marginBottom:'0.4rem'}}>Risk Analysis</strong>
                            {m.policy.reason}
                        </div>
                        <div style={{marginTop:'2rem', display:'flex', gap:'1rem'}}>
                            <button onClick={() => confirmPlan(true)} className="btn btn-primary" style={{padding:'0.875rem 2.5rem', fontSize:'1rem'}}>Execute Protocol</button>
                            <button onClick={() => confirmPlan(false)} className="btn btn-outline" style={{padding:'0.875rem 2.5rem', fontSize:'1rem'}}>Decline</button>
                        </div>
                        </div>
                    ) : (
                        <div style={{whiteSpace:'pre-wrap'}}>
                        {m.content}
                        {m.thought && (
                          <div style={{marginTop:'1rem', opacity:0.9}}>
                             <ThinkingTrace thought={m.thought} />
                          </div>
                        )}
                        {m.sources && m.sources.length > 0 && <SourcesGrid sources={m.sources} />}
                        {m.reflection && (
                            <div style={{marginTop:'2rem', paddingTop:'1.5rem', borderTop:'1px solid #f1f5f9', fontSize:'0.95rem', color:'#475569'}}>
                                <div style={{display:'flex', alignItems:'center', gap:'0.6rem', fontWeight:'800', color:'#3b82f6', marginBottom:'0.75rem', fontSize:'0.8rem', textTransform:'uppercase', letterSpacing:'0.05em'}}>
                                    <Sparkles size={18}/> Logic Reflection
                                </div>
                                <p style={{lineHeight:'1.7', color:'#334155'}}>{m.reflection.reflection.suggestion}</p>
                                <div style={{marginTop:'1rem', fontWeight:'800', fontSize:'0.75rem', background:'#eff6ff', display:'inline-flex', alignItems:'center', gap:'0.4rem', padding:'0.4rem 0.75rem', borderRadius:'8px', color:'#3b82f6', border:'1px solid #dbeafe'}}>
                                    SYSTEM CONFIDENCE: {Math.round(m.reflection.reflection.overall_confidence * 100)}%
                                </div>
                            </div>
                        )}
                        </div>
                    )}
                    </div>
                </div>
             </div>
          ))}
          {loading && (
            <div style={{display:'flex', gap:'1.75rem', alignItems:'flex-start', padding:'1rem'}}>
                <div style={{width:'48px', height:'48px', borderRadius:'16px', background:'white', display:'flex', alignItems:'center', justifyContent:'center', border:'1px solid #e2e8f0', boxShadow:'0 4px 6px rgba(0,0,0,0.02)'}}>
                    <RefreshCw size={24} className="spin" color="#3b82f6"/>
                </div>
                <div style={{paddingTop:'0.5rem'}}>
                    {globalStatus.status === 'thinking' && (
                      <div className="fade-in">
                        <div style={{fontSize:'1.1rem', fontWeight:'800', color:'#1e293b'}}>Synthesizing Response...</div>
                        <div style={{fontSize:'0.9rem', color:'#64748b', marginTop:'0.25rem'}}>{globalStatus.thought?.split('\n')[0] || 'Analyzing request context'}</div>
                      </div>
                    )}
                    {globalStatus.status === 'planning' && <div style={{fontSize:'1.1rem', fontWeight:'800', color:'#1e293b'}}>Architecting Solution...</div>}
                    {globalStatus.status === 'executing' && <div style={{fontSize:'1.1rem', fontWeight:'800', color:'#3b82f6'}}>Engaging Autonomous Channels...</div>}
                    {!globalStatus.status || globalStatus.status === 'idle' && <div style={{fontSize:'1.1rem', fontWeight:'800', color:'#64748b'}}>Awaiting Processing...</div>}
                </div>
            </div>
          )}
       </div>

       <div style={{marginTop:'auto', paddingTop:'2rem', borderTop:'1px solid #e2e8f0'}}>
          <div style={{display:'flex', gap:'1rem', background:'white', padding:'1.25rem', borderRadius:'24px', border:'1px solid #e2e8f0', boxShadow:'0 20px 25px -5px rgba(0, 0, 0, 0.05)'}}>
             <input 
                value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Enter a task, research query, or message..." style={{flex:1, border:'none', padding:'0.5rem', fontSize:'1.1rem', outline:'none', background:'transparent', color:'#1e293b'}}
             />
             <button onClick={sendMessage} className="btn btn-primary" style={{padding:'0 1.75rem', borderRadius:'18px', height:'54px'}}>
                <ArrowRight size={22}/>
             </button>
          </div>
          <div style={{textAlign:'center', marginTop:'1rem', fontSize:'0.75rem', color:'#94a3b8', fontWeight:'600', letterSpacing:'0.02em'}}>
            LIROX AUTONOMOUS RESEARCH AGENT v0.4.1 — ENABLED
          </div>
       </div>
    </div>
  );
};

const TaskPage = ({ profile, status: globalStatus }) => {
    const [goal, setGoal] = useState('');
    const [plan, setPlan] = useState(null);
    const [taskResult, setTaskResult] = useState(null);
    const [loading, setLoading] = useState(false);
  
    const runTask = async () => {
      if (!goal.trim()) return;
      setLoading(true);
      setTaskResult(null);
      try {
        const res = await axios.post(`${API_BASE}/chat`, { message: goal });
        if (res.data.type === 'task_pending') {
          setPlan({ ...res.data.plan, policy: res.data.policy, thought: res.data.thought });
        } else {
          setPlan(res.data.plan);
          setTaskResult(res.data);
        }
      } catch (e) {
        alert("Communications error during task dispatch.");
      } finally {
        setLoading(false);
      }
    };

    const confirm = async (confirmed) => {
        setLoading(true);
        try {
            await axios.post(`${API_BASE}/confirm-run`, { confirmed });
            setPlan(null);
        } finally {
            setLoading(false);
        }
    }
  
    return (
      <div style={{padding:'3rem', maxWidth:'1100px', margin:'0 auto', height:'100%', display:'flex', flexDirection:'column', overflowY:'auto'}}>
         <div className="fade-in">
           <div style={{display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'0.75rem'}}>
             <div style={{width:'36px', height:'3px', background:'#3b82f6', borderRadius:'4px'}}></div>
             <span style={{fontSize:'0.85rem', fontWeight:'900', color:'#3b82f6', textTransform:'uppercase', letterSpacing:'0.1em'}}>Autonomous Engine</span>
           </div>
           <h1 style={{fontSize:'2.5rem', marginBottom:'0.75rem', fontWeight:'900', background:'linear-gradient(135deg, #0f172a 0%, #3b82f6 100%)', WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', letterSpacing:'-0.03em'}}>Neural Research</h1>
           <p style={{color:'#64748b', marginBottom:'3rem', fontSize:'1.2rem', lineHeight:'1.6', maxWidth:'600px'}}>Deploy Lirox on deep research missions. It will independently browse, verify, and synthesize complex multi-source inquiries.</p>
         </div>
         
         <div style={{display:'flex', gap:'1.25rem', marginBottom:'3.5rem'}}>
            <div className="card" style={{flex:1, display:'flex', alignItems:'center', padding:'1.25rem 1.75rem', boxShadow:'0 15px 30px -5px rgba(0,0,0,0.05)', border:'1px solid #e2e8f0', borderRadius:'22px'}}>
               <Search size={24} style={{color:'#94a3b8', marginRight:'1.5rem'}} />
               <input value={goal} onChange={e => setGoal(e.target.value)} placeholder="Enter a research objective or mission parameter..." style={{flex:1, border:'none', fontSize:'1.15rem', outline:'none', background:'transparent', color:'#1e293b'}} />
            </div>
            <button onClick={runTask} disabled={loading || globalStatus.status !== 'idle'} className="btn btn-primary" style={{padding:'0 2.5rem', height:'70px', borderRadius:'22px', fontSize:'1.1rem', fontWeight:'800', boxShadow:'0 12px 24px -6px rgba(37, 99, 235, 0.3)'}}>
               {loading || globalStatus.status !== 'idle' ? <RefreshCw size={22} className="spin"/> : <Sparkles size={22}/>}
               {loading || globalStatus.status !== 'idle' ? 'Processing...' : 'Engage Agent'}
            </button>
         </div>
  
         {(plan || globalStatus.status !== 'idle' || taskResult) && (
            <div className="fade-in card" style={{padding:'3rem', background:'white', boxShadow:'0 25px 50px -12px rgba(0, 0, 0, 0.08)', border:'1px solid #e2e8f0', borderRadius:'32px'}}>
               <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'2.5rem'}}>
                 <div>
                   <div style={{fontSize:'0.75rem', fontWeight:'900', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:'0.5rem'}}>Active Objective</div>
                   <h3 style={{fontSize:'1.85rem', marginBottom:'0.75rem', fontWeight:'900', color:'#0f172a', letterSpacing:'-0.02em'}}>{plan?.goal || goal || 'Mission Operations'}</h3>
                   <div style={{fontSize:'1rem', color:'#64748b', display:'flex', alignItems:'center', gap:'0.75rem', fontWeight:'600'}}>
                     <span style={{
                       width:'12px', height:'12px', borderRadius:'50%', 
                       background:globalStatus.status === 'idle' ? '#10b981' : '#3b82f6',
                       boxShadow: globalStatus.status !== 'idle' ? '0 0 15px rgba(59, 130, 246, 0.6)' : 'none'
                     }}></span>
                     {globalStatus.status === 'thinking' ? 'Synthesizing Strategic Path' : globalStatus.status === 'executing' ? 'Engaging Autonomous Tools' : 'Mission Accomplished'}
                   </div>
                 </div>
                 {plan?.policy && (
                   <div style={{padding:'0.75rem 1.75rem', background:'#fffbeb', color:'#d97706', borderRadius:'16px', fontSize:'0.9rem', fontWeight:'800', display:'flex', alignItems:'center', gap:'0.7rem', border:'1px solid #fef3c7', boxShadow:'0 4px 6px -1px rgba(217, 119, 6, 0.1)'}}>
                     <ShieldAlert size={20}/> Gateway Block: Confirmation Required
                   </div>
                 )}
               </div>

               {globalStatus.status === 'thinking' && globalStatus.thought && (
                 <div style={{marginBottom:'2.5rem'}}>
                   <ThinkingTrace thought={globalStatus.thought} />
                 </div>
               )}
               
               {plan && (
                <div style={{display:'flex', flexDirection:'column', gap:'1.25rem', marginBottom:'3rem', marginTop:'2rem'}}>
                    <h4 style={{fontSize:'0.85rem', fontWeight:'900', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'0.75rem', display:'flex', alignItems:'center', gap:'0.5rem'}}>
                      <ListChecks size={16}/> Operational Strategic Plan
                    </h4>
                    {plan.steps.map((s, i) => (
                        <div key={i} style={{display:'flex', gap:'1.5rem', alignItems:'center', padding:'1.5rem', borderRadius:'22px', background:'#f8fafc', border:'1px solid #f1f5f9', transition:'all 0.3s'}}>
                            <div style={{width:'38px', height:'38px', borderRadius:'14px', background:'white', border:'1px solid #e2e8f0', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'1rem', fontWeight:'900', boxShadow:'0 4px 6px rgba(0,0,0,0.03)', color:'#0f172a'}}>{i+1}</div>
                            <div style={{flex:1, fontSize:'1.1rem', color:'#1e293b', fontWeight:'700'}}>{s.task}</div>
                            <div style={{fontSize:'0.75rem', fontWeight:'900', textTransform:'uppercase', letterSpacing:'0.1em', background:'#3b82f6', padding:'0.5rem 1rem', borderRadius:'10px', color:'white', boxShadow:'0 4px 10px rgba(59, 130, 246, 0.2)'}}>{s.tools[0]}</div>
                        </div>
                    ))}
                </div>
               )}

               {taskResult?.sources && (
                 <div style={{marginBottom:'3rem'}}>
                   <h4 style={{fontSize:'0.85rem', fontWeight:'900', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:'1.25rem', display:'flex', alignItems:'center', gap:'0.5rem'}}>
                      <Globe size={16}/> Neural Citations
                   </h4>
                   <SourcesGrid sources={taskResult.sources} />
                 </div>
               )}

               {plan?.policy && (
                  <div style={{background:'#f8fafc', padding:'2.5rem', borderRadius:'28px', border:'3px dashed #e2e8f0', marginTop:'2.5rem', textAlign:'center'}}>
                    <h4 style={{marginBottom:'1rem', fontSize:'1.35rem', fontWeight:'900', color:'#0f172a'}}>Gateway Permission Request</h4>
                    <p style={{color:'#64748b', marginBottom:'2rem', maxWidth:'500px', margin:'0 auto 2rem auto'}}>The following steps exceed autonomous safety thresholds and require operator override.</p>
                    <div style={{display:'flex', gap:'1.5rem', justifyContent:'center'}}>
                      <button onClick={() => confirm(true)} className="btn btn-primary" style={{padding:'1.1rem 4rem', fontSize:'1.1rem', borderRadius:'16px'}}>Authorize Execution</button>
                      <button onClick={() => confirm(false)} className="btn btn-outline" style={{padding:'1.1rem 4rem', fontSize:'1.1rem', borderRadius:'16px'}}>Reject & Terminate</button>
                    </div>
                    <div style={{marginTop:'2rem', fontSize:'0.95rem', color:'#475569', display:'inline-flex', alignItems:'center', justifyContent:'center', gap:'0.75rem', background:'white', padding:'0.75rem 1.5rem', borderRadius:'14px', border:'1px solid #e2e8f0'}}>
                      <Info size={18} color="#3b82f6"/> <strong>Risk Reasoning:</strong> {plan.policy.reason}
                    </div>
                  </div>
               )}

               {taskResult && !plan?.policy && (
                  <div className="fade-in" style={{marginTop:'3.5rem', borderTop:'2px solid #f8fafc', paddingTop:'2.5rem'}}>
                      <div style={{display:'flex', alignItems:'center', gap:'1rem', marginBottom:'2rem'}}>
                        <div style={{width:'48px', height:'48px', borderRadius:'16px', background:'linear-gradient(135deg, #10b981 0%, #059669 100%)', display:'flex', alignItems:'center', justifyContent:'center', color:'white', boxShadow:'0 10px 15px -3px rgba(16, 185, 129, 0.3)'}}>
                          <CheckCircle2 size={26}/>
                        </div>
                        <h4 style={{fontSize:'1.6rem', fontWeight:'900', color:'#0f172a', letterSpacing:'-0.02em'}}>Research Synthesis Result</h4>
                      </div>
                      <div className="card" style={{
                        background:'#ffffff', padding:'2.5rem', borderRadius:'24px', whiteSpace:'pre-wrap', 
                        fontSize:'1.1rem', lineHeight:'1.9', color:'#334155', border:'1px solid #e2e8f0',
                        boxShadow:'inset 0 2px 4px 0 rgba(0, 0, 0, 0.02)'
                      }}>
                          {taskResult.response}
                      </div>
                      <div style={{marginTop:'1.5rem', display:'flex', justifyContent:'flex-end'}}>
                        <button onClick={() => window.print()} className="btn btn-outline" style={{padding:'0.6rem 1.25rem', gap:'0.5rem', fontSize:'0.85rem', fontWeight:'700'}}>
                          <Save size={16}/> Export Mission Report
                        </button>
                      </div>
                  </div>
               )}
            </div>
         )}
         <div style={{height:'6rem'}}></div>
      </div>
    );
};

const SettingsPage = ({ providers: initialProviders, setProviders }) => {
    const [settings, setSettings] = useState({ allow_terminal_tool: false, auto_execute_max_steps: 5, default_provider: 'auto' });
    const [loading, setLoading] = useState(true);
    const [providers, setLocalProviders] = useState(initialProviders || { available: [], all: [] });
    const [keys, setKeys] = useState({ gemini: '', groq: '', openai: '', openrouter: '', deepseek: '', nvidia: '' });
    const [keySaving, setKeySaving] = useState(false);
    const [keySaved, setKeySaved] = useState(null);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [sRes, pRes] = await Promise.all([
                    axios.get(`${API_BASE}/settings`),
                    axios.get(`${API_BASE}/providers`)
                ]);
                setSettings(sRes.data);
                setLocalProviders(pRes.data);
                if (setProviders) setProviders(pRes.data);
            } finally { setLoading(false); }
        };
        fetchAll();
    }, []);

    const save = async (s) => {
        setSettings(s);
        await axios.post(`${API_BASE}/settings`, s);
    };

    const saveKey = async (provider) => {
        const val = keys[provider];
        if (!val.trim()) return;
        setKeySaving(true);
        try {
            await axios.post(`${API_BASE}/keys`, { [provider]: val.trim() });
            setKeySaved(provider);
            setKeys(k => ({ ...k, [provider]: '' }));
            // Refresh providers list
            const pRes = await axios.get(`${API_BASE}/providers`);
            setLocalProviders(pRes.data);
            if (setProviders) setProviders(pRes.data);
            setTimeout(() => setKeySaved(null), 3000);
        } catch(e) {
            alert('Failed to save key: ' + (e.response?.data?.detail || e.message));
        } finally {
            setKeySaving(false);
        }
    };

    if (loading) return <div style={{padding:'3rem', textAlign:'center', color:'#64748b'}}>Syncing system parameters...</div>;

    const providerDefs = [
      { key: 'gemini',      label: 'Gemini',      hint: 'aistudio.google.com  — FREE' },
      { key: 'groq',        label: 'Groq',        hint: 'console.groq.com     — FREE' },
      { key: 'openrouter',  label: 'OpenRouter',  hint: 'openrouter.ai        — FREE models' },
      { key: 'openai',      label: 'OpenAI',      hint: 'platform.openai.com  — Paid' },
      { key: 'deepseek',    label: 'DeepSeek',    hint: 'platform.deepseek.com — Cheap' },
      { key: 'nvidia',      label: 'NVIDIA NIM',  hint: 'build.nvidia.com     — FREE' },
    ];

    return (
        <div style={{padding:'3rem', maxWidth:'900px', margin:'0 auto', overflowY:'auto', height:'100%'}}>
            <h1 style={{fontSize:'2rem', marginBottom:'2.5rem', fontWeight:'900', color:'#0f172a'}}>System Configuration</h1>

            {/* API Keys Section */}
            <div className="card" style={{padding:'2.5rem', borderRadius:'24px', marginBottom:'2rem', boxShadow:'0 4px 6px -1px rgba(0,0,0,0.05)'}}>
                <div style={{display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'0.5rem'}}>
                  <Key size={20} color="#3b82f6"/>
                  <div style={{fontWeight:'900', fontSize:'1.15rem', color:'#0f172a'}}>API Keys</div>
                </div>
                <div style={{color:'#64748b', fontSize:'0.95rem', marginBottom:'2rem'}}>
                  {providers.available.length === 0
                    ? '⚠ No providers configured. Add at least one key to activate the agent.'
                    : `${providers.available.length} of ${providers.all.length} providers active: ${providers.available.join(', ')}`
                  }
                </div>
                <div style={{display:'flex', flexDirection:'column', gap:'1.25rem'}}>
                  {providerDefs.map(({ key, label, hint }) => {
                    const isActive = providers.available.includes(key);
                    return (
                      <div key={key} style={{display:'flex', gap:'1rem', alignItems:'center'}}>
                        <div style={{width:'130px', flexShrink:0}}>
                          <div style={{fontWeight:'700', fontSize:'0.9rem', color:'#1e293b'}}>{label}</div>
                          <div style={{fontSize:'0.75rem', color: isActive ? '#10b981' : '#94a3b8', fontWeight:'600'}}>
                            {isActive ? '✓ Active' : hint}
                          </div>
                        </div>
                        <input
                          type="password"
                          placeholder={isActive ? 'Enter new key to update…' : 'Paste API key here…'}
                          value={keys[key]}
                          onChange={e => setKeys(k => ({ ...k, [key]: e.target.value }))}
                          onKeyDown={e => e.key === 'Enter' && saveKey(key)}
                          style={{
                            flex:1, padding:'0.75rem 1rem', border:isActive ? '2px solid #d1fae5' : '2px solid #f1f5f9',
                            borderRadius:'12px', fontSize:'0.95rem', color:'#1e293b', background: isActive ? '#f0fdf4' : '#f8fafc',
                            outline:'none', fontFamily:'inherit'
                          }}
                        />
                        <button
                          id={`save-key-${key}`}
                          onClick={() => saveKey(key)}
                          disabled={keySaving || !keys[key].trim()}
                          style={{
                            padding:'0.75rem 1.25rem', borderRadius:'12px', fontWeight:'800', fontSize:'0.85rem',
                            background: keySaved === key ? '#10b981' : '#3b82f6',
                            color:'white', border:'none', cursor:'pointer', transition:'all 0.2s',
                            opacity: (!keys[key].trim() || keySaving) ? 0.5 : 1, whiteSpace:'nowrap'
                          }}
                        >
                          {keySaved === key ? '✓ Saved' : 'Save'}
                        </button>
                      </div>
                    );
                  })}
                </div>
            </div>

            {/* Autonomy + Safety Settings */}
            <div className="card" style={{padding:'3rem', display:'flex', flexDirection:'column', gap:'3rem', borderRadius:'24px', boxShadow:'0 4px 6px -1px rgba(0,0,0,0.05)'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <div style={{maxWidth:'70%'}}>
                        <div style={{fontWeight:'800', fontSize:'1.1rem', marginBottom:'0.4rem', color:'#1e293b'}}>Autonomous Threshold</div>
                        <div style={{fontSize:'0.95rem', color:'#64748b'}}>Define the maximum step count Lirox can execute without operator validation. High values increase autonomy but decrease human oversight.</div>
                    </div>
                </div>

                <div>
                    <div style={{display:'flex', justifyContent:'space-between', marginBottom:'1.25rem'}}>
                        <span style={{fontWeight:'700', fontSize:'0.9rem', color:'#1e293b', textTransform:'uppercase', letterSpacing:'0.05em'}}>Autonomy Multiplier</span>
                        <span style={{color:'#3b82f6', fontWeight:'900', fontSize:'1.1rem'}}>{settings.auto_execute_max_steps} STEPS</span>
                    </div>
                    <input 
                      type="range" min="1" max="10" value={settings.auto_execute_max_steps} 
                      onChange={e => save({...settings, auto_execute_max_steps: parseInt(e.target.value)})}
                      style={{width:'100%', height:'8px', borderRadius:'10px', appearance:'none', background:'#e2e8f0', outline:'none', cursor:'pointer'}}
                    />
                    <div style={{display:'flex', justifyContent:'space-between', marginTop:'0.75rem', fontSize:'0.75rem', color:'#94a3b8', fontWeight:'700'}}>
                      <span>CAUTIOUS (1)</span>
                      <span>AGGRESSIVE (10)</span>
                    </div>
                </div>

                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', paddingTop:'2rem', borderTop:'1px solid #f1f5f9'}}>
                    <div>
                        <div style={{fontWeight:'800', fontSize:'1.1rem', marginBottom:'0.4rem', color:'#1e293b'}}>Terminal Shield</div>
                        <div style={{fontSize:'0.95rem', color:'#64748b'}}>Protective firewall for shell command execution. Terminal bypass is currently restricted for mission-critical safety.</div>
                    </div>
                    <div style={{background:'#eff6ff', color:'#3b82f6', padding:'0.6rem 1rem', borderRadius:'10px', fontSize:'0.8rem', fontWeight:'900', border:'1px solid #dbeafe', letterSpacing:'0.05em'}}>HEAVILY PROTECTED</div>
                </div>

                <div style={{paddingTop:'1.5rem', display:'flex', gap:'1.5rem', alignItems:'center'}}>
                    <button 
                        id="purge-memory-btn"
                        onClick={async () => {
                            if (window.confirm("Perform a deep neural reset? All conversation states will be cleared.")) {
                                await axios.post(`${API_BASE}/memory/clear`);
                                alert("Neural pathways cleared.");
                            }
                        }}
                        className="btn btn-outline" style={{padding:'0.875rem 1.75rem', color:'#ef4444', borderColor:'#fee2e2', background:'#fef2f2'}}
                    >Purge Neural Memory</button>
                    <span style={{fontSize:'0.85rem', color:'#94a3b8', fontWeight:'500'}}>Last system sync: Recent</span>
                </div>
            </div>
        </div>
    );
};

const SetupPage = ({ profile, setProfile, onComplete }) => {
    const [step, setStep] = useState(1);
    const [formData, setFormData] = useState({ ...profile });

    const next = () => setStep(s => s + 1);
    const back = () => setStep(s => s - 1);
    const finish = async () => {
        try {
            const res = await axios.post(`${API_BASE}/profile`, formData);
            setProfile(res.data);
            onComplete();
        } catch (e) { alert("Failed to synchronize profile data."); }
    };

    return (
        <div style={{display:'flex', alignItems:'center', justifyContent:'center', height:'100%', padding:'2rem', background:'linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%)'}}>
            <div className="card fade-in" style={{width:'100%', maxWidth:'550px', padding:'4rem', borderRadius:'40px', boxShadow:'0 30px 60px -12px rgba(0, 0, 0, 0.1)', border:'1px solid #e2e8f0', background:'white'}}>
                {step === 1 && (
                    <div className="fade-in">
                        <div style={{background:'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', width:'80px', height:'80px', borderRadius:'24px', display:'flex', alignItems:'center', justifyContent:'center', color:'white', marginBottom:'2.5rem', boxShadow:'0 10px 20px rgba(37, 99, 235, 0.3)'}}>
                           <Sparkles size={40}/>
                        </div>
                        <h2 style={{fontSize:'2.25rem', marginBottom:'1rem', fontWeight:'900', color:'#0f172a', letterSpacing:'-0.03em'}}>Agent Genesis</h2>
                        <p style={{color:'#64748b', marginBottom:'3rem', fontSize:'1.1rem', lineHeight:'1.6'}}>Initialize your autonomous employee. Provide identity parameters to begin the integration.</p>
                        
                        <div style={{display:'flex', flexDirection:'column', gap:'1.75rem'}}>
                            <div className="input-group">
                                <label style={{display:'block', fontSize:'0.85rem', fontWeight:'800', marginBottom:'0.75rem', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.05em'}}>Neural Signature (Name)</label>
                                <input className="input-field" value={formData.agent_name || ''} onChange={e => setFormData({...formData, agent_name: e.target.value})} placeholder="e.g. Lirox, Nova, Kaily" />
                            </div>
                            <div className="input-group">
                                <label style={{display:'block', fontSize:'0.85rem', fontWeight:'800', marginBottom:'0.75rem', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.05em'}}>Operator Designation</label>
                                <input className="input-field" value={formData.user_name || ''} onChange={e => setFormData({...formData, user_name: e.target.value})} placeholder="What should Lirox call you?" />
                            </div>
                        </div>
                        <button onClick={next} className="btn btn-primary" style={{width:'100%', marginTop:'3.5rem', height:'4.5rem', borderRadius:'18px', fontSize:'1.15rem', fontWeight:'800'}}>Initiate Initialization <ArrowRight size={22} style={{marginLeft:'0.5rem'}}/></button>
                    </div>
                )}

                {step === 2 && (
                    <div className="fade-in">
                        <div style={{display:'flex', gap:'0.5rem', marginBottom:'2.5rem'}}>
                          <div style={{width:'20px', height:'4px', background:'#3b82f6', borderRadius:'2px'}}></div>
                          <div style={{width:'20px', height:'4px', background:'#3b82f6', borderRadius:'2px'}}></div>
                        </div>
                        <h2 style={{fontSize:'2rem', marginBottom:'1rem', fontWeight:'900', color:'#0f172a', letterSpacing:'-0.02em'}}>Functional Niche</h2>
                        <p style={{color:'#64748b', marginBottom:'3.5rem', fontSize:'1.1rem', lineHeight:'1.6'}}>Fine-tune Lirox's operational focus and communicative personality.</p>
                        
                        <div style={{display:'flex', flexDirection:'column', gap:'1.75rem'}}>
                            <div className="input-group">
                                <label style={{display:'block', fontSize:'0.85rem', fontWeight:'800', marginBottom:'0.75rem', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.05em'}}>Primary Domain</label>
                                <select className="input-field" value={formData.niche || 'Software Engineering'} onChange={e => setFormData({...formData, niche: e.target.value})}>
                                    <option>Software Engineering</option>
                                    <option>Market Analysis</option>
                                    <option>Academic Research</option>
                                    <option>Content Strategy</option>
                                    <option>Data Science</option>
                                </select>
                            </div>
                            <div className="input-group">
                                <label style={{display:'block', fontSize:'0.85rem', fontWeight:'800', marginBottom:'0.75rem', color:'#94a3b8', textTransform:'uppercase', letterSpacing:'0.05em'}}>Personality Archetype</label>
                                <select className="input-field" value={formData.tone || 'Professional'} onChange={e => setFormData({...formData, tone: e.target.value})}>
                                    <option>Professional & Analytical</option>
                                    <option>Casual & Creative</option>
                                    <option>Concise & Direct</option>
                                    <option>Supportive & Detailed</option>
                                </select>
                            </div>
                        </div>
                        <div style={{display:'flex', gap:'1.25rem', marginTop:'3.5rem'}}>
                            <button onClick={back} className="btn btn-outline" style={{flex:1, height:'4.5rem', borderRadius:'18px'}}><ArrowLeft size={22}/> Back</button>
                            <button onClick={finish} className="btn btn-primary" style={{flex:2, height:'4.5rem', borderRadius:'18px'}}>Confirm Genesis <CheckCircle2 size={22} style={{marginLeft:'0.5rem'}}/></button>
                        </div>
                    </div>
                )}
            </div>
            
            <style>{`
                .input-field {
                    width: 100%;
                    padding: 1.15rem 1.5rem;
                    border: 2px solid #f1f5f9;
                    border-radius: 18px;
                    font-size: 1.1rem;
                    color: #1e293b;
                    background: #f8fafc;
                    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                    font-family: inherit;
                    cursor: pointer;
                }
                .input-field:focus {
                    border-color: #3b82f6;
                    background: white;
                    outline: none;
                    box-shadow: 0 0 0 5px rgba(59, 130, 246, 0.1);
                }
                select.input-field {
                    appearance: none;
                }
            `}</style>
        </div>
    );
};

export default App;
