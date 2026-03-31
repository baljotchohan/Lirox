import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  MessageSquare, Settings, User, ListChecks, Search, PlusCircle, 
  Key, Cpu, History, Info, Terminal, Save, CheckCircle2, X, 
  ShieldAlert, ArrowRight, ArrowLeft, ChevronDown, Activity, 
  RefreshCw, MousePointer2, AlertCircle, Sparkles
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

const App = () => {
  const [page, setPage] = useState('chat');
  const [profile, setProfile] = useState({});
  const [status, setStatus] = useState({ status: 'idle', pending_confirmation: false });
  const [loading, setLoading] = useState(true);

  // Initial Profile Fetch
  useEffect(() => {
    const init = async () => {
      try {
        const res = await axios.get(`${API_BASE}/profile`);
        setProfile(res.data);
        if (!res.data.user_name) setPage('setup');
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

  if (loading) return <div style={{height:'100vh', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'Inter, sans-serif'}}>Initializing Lirox v0.4...</div>;

  return (
    <div className="app-container" style={{display:'flex', height:'100vh', overflow:'hidden', fontFamily:'Inter, sans-serif'}}>
      {/* Sidebar */}
      <nav style={{
        width: '260px', borderRight: '1px solid var(--border-color)', background: 'white',
        display: 'flex', flexDirection: 'column', padding: '1.5rem 1rem'
      }}>
        <div style={{display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'2rem', padding:'0 0.5rem'}}>
          <div style={{width:'32px', height:'32px', background:'var(--primary-color)', borderRadius:'8px', display:'flex', alignItems:'center', justifyContent:'center', color:'white', fontWeight:'800'}}>L</div>
          <span style={{fontWeight:'700', fontSize:'1.125rem'}}>Lirox Agent</span>
        </div>

        <div style={{display:'flex', flexDirection:'column', gap:'0.25rem'}}>
          <NavItem icon={<MessageSquare size={18}/>} label="Chat" active={page === 'chat'} onClick={() => setPage('chat')} />
          <NavItem icon={<ListChecks size={18}/>} label="Tasks" active={page === 'task'} onClick={() => setPage('task')} />
          <NavItem icon={<User size={18}/>} label="Profile" active={page === 'setup'} onClick={() => setPage('setup')} />
          <NavItem icon={<Settings size={18}/>} label="Settings" active={page === 'settings'} onClick={() => setPage('settings')} />
        </div>

        <div style={{marginTop:'auto', padding:'1rem 0.5rem', borderTop:'1px solid var(--border-color)'}}>
           <div style={{fontSize:'0.75rem', color:'var(--text-muted)', marginBottom:'0.25rem'}}>System Status</div>
           <div style={{display:'flex', alignItems:'center', gap:'0.5rem'}}>
              <div style={{
                width:'8px', height:'8px', borderRadius:'50%', 
                background: status.status === 'idle' ? 'var(--success-color)' : 'var(--warning-color)',
                boxShadow: status.status !== 'idle' ? '0 0 8px var(--warning-color)' : 'none'
              }}></div>
              <span style={{fontSize:'0.8125rem', fontWeight:'600', textTransform:'capitalize'}}>
                {status.status.replace('_', ' ')}
              </span>
           </div>
           {status.pending_confirmation && (
             <div style={{marginTop:'0.5rem', fontSize:'0.75rem', color:'var(--warning-color)', display:'flex', alignItems:'center', gap:'0.25rem'}}>
               <ShieldAlert size={12}/> Confirmation Required
             </div>
           )}
        </div>
      </nav>

      {/* Main Content */}
      <main style={{flex:1, overflow:'hidden', position:'relative', background:'var(--bg-color)'}}>
        {page === 'chat' && <ChatPage profile={profile} status={status} />}
        {page === 'task' && <TaskPage profile={profile} status={status} />}
        {page === 'setup' && <SetupPage profile={profile} setProfile={setProfile} onComplete={() => setPage('chat')} />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  );
};

const NavItem = ({ icon, label, active, onClick }) => (
  <button onClick={onClick} style={{
    display:'flex', alignItems:'center', gap:'0.75rem', padding:'0.75rem 1rem', width:'100%', borderRadius:'var(--radius-md)',
    background: active ? 'rgba(37, 99, 235, 0.08)' : 'transparent',
    color: active ? 'var(--primary-color)' : 'var(--text-muted)',
    fontWeight: active ? '600' : '500', border:'none', cursor:'pointer', transition:'all 0.2s'
  }}>{icon} <span>{label}</span></button>
);

const ChatPage = ({ profile, status }) => {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: `Hello ${profile.user_name || 'there'}! I'm ${profile.agent_name || 'Lirox'}. I can handle chat or complex research tasks. Try asking me for some research!` }
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
          policy: data.policy
        }]);
      } else if (data.type === 'task_complete') {
        setMessages(prev => [...prev, { role: 'assistant', content: data.response, reflection: data.reflection }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Error: Failed to process request. Check if the server is alive." }]);
    } finally {
      setLoading(false);
    }
  };

  const confirmPlan = async (confirmed) => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/confirm-run`, { confirmed });
      setMessages(prev => [...prev, { role: 'system', content: confirmed ? "Execution started in background." : "Task cancelled." }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'system', content: "Failed to confirm task." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{display:'flex', flexDirection:'column', height:'100%', padding:'1.5rem', maxWidth:'900px', margin:'0 auto'}}>
       <div style={{flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:'1.5rem', paddingBottom:'2rem'}}>
          {messages.map((m, i) => (
             <div key={i} className="fade-in" style={{
                display:'flex', flexDirection: m.role === 'user' ? 'row-reverse' : 'row', gap:'1rem', alignItems:'flex-start'
             }}>
                <div style={{
                   width:'36px', height:'36px', borderRadius:'12px', flexShrink:0,
                   background: m.role === 'user' ? '#eef2ff' : 'white',
                   border: m.role === 'user' ? 'none' : '1px solid var(--border-color)',
                   display:'flex', alignItems:'center', justifyContent:'center', color: m.role === 'user' ? 'var(--primary-color)' : 'var(--text-muted)'
                }}>
                   {m.role === 'user' ? <User size={20}/> : <Cpu size={20}/>}
                </div>
                <div className="card" style={{
                   padding:'1rem 1.25rem', maxWidth:'80%', fontSize:'0.9375rem', lineHeight:'1.5',
                   background: m.role === 'user' ? 'var(--primary-color)' : m.type === 'confirmation' ? '#fffbeb' : 'white',
                   color: m.role === 'user' ? 'white' : 'var(--text-main)',
                   borderRadius: m.role === 'user' ? '1rem 0.25rem 1rem 1rem' : '0.25rem 1rem 1rem 1rem',
                   boxShadow: m.role === 'user' ? '0 10px 15px -3px rgba(37, 99, 235, 0.2)' : 'var(--shadow-sm)'
                }}>
                   {m.type === 'confirmation' ? (
                     <div>
                       <div style={{fontWeight:'700', marginBottom:'0.5rem', display:'flex', alignItems:'center', gap:'0.5rem'}}>
                         <ShieldAlert size={18} color="#d97706"/> Confirm Action
                       </div>
                       <p>{m.content}</p>
                       <div style={{marginTop:'1rem', padding:'0.75rem', background:'rgba(0,0,0,0.05)', borderRadius:'8px', fontSize:'0.8125rem'}}>
                         <strong>Policy Reason:</strong> {m.policy.reason}
                       </div>
                       <div style={{marginTop:'1rem', display:'flex', gap:'0.5rem'}}>
                         <button onClick={() => confirmPlan(true)} className="btn btn-primary" style={{padding:'0.5rem 1rem', fontSize:'0.8125rem'}}>Confirm</button>
                         <button onClick={() => confirmPlan(false)} className="btn btn-outline" style={{padding:'0.5rem 1rem', fontSize:'0.8125rem'}}>Cancel</button>
                       </div>
                     </div>
                   ) : (
                     <div>
                       {m.content}
                       {m.reflection && (
                          <div style={{marginTop:'1rem', paddingTop:'0.75rem', borderTop:'1px solid var(--border-color)', fontSize:'0.8125rem', color:'var(--text-muted)'}}>
                             <div style={{display:'flex', alignItems:'center', gap:'0.4rem', fontWeight:'600', color:'var(--primary-color)'}}>
                                <Sparkles size={14}/> Confidence: {Math.round(m.reflection.reflection.overall_confidence * 100)}%
                             </div>
                             <p>{m.reflection.reflection.suggestion}</p>
                          </div>
                       )}
                     </div>
                   )}
                </div>
             </div>
          ))}
          {loading && <div style={{color:'var(--text-muted)', fontSize:'0.875rem', paddingLeft:'3rem', display:'flex', alignItems:'center', gap:'0.5rem'}}>
            <Activity size={16} className="spin"/> Lirox is working...
          </div>}
       </div>

       <div style={{marginTop:'auto', paddingTop:'1.5rem'}}>
          <div style={{display:'flex', gap:'0.75rem', background:'white', padding:'0.75rem', borderRadius:'var(--radius-lg)', border:'1px solid var(--border-color)', boxShadow:'var(--shadow-md)'}}>
             <input 
                value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Message Lirox or ask for research..." style={{flex:1, border:'none', padding:'0.5rem', fontSize:'0.9375rem', outline:'none'}}
             />
             <button onClick={sendMessage} className="btn btn-primary" style={{padding:'0 1.25rem'}}>
                <ArrowRight size={18}/>
             </button>
          </div>
       </div>
    </div>
  );
};

const TaskPage = () => {
    const [goal, setGoal] = useState('');
    const [plan, setPlan] = useState(null);
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(false);
  
    const runTask = async () => {
      if (!goal.trim()) return;
      setLoading(true);
      try {
        const res = await axios.post(`${API_BASE}/chat`, { message: goal });
        if (res.data.type === 'task_pending') {
          setPlan({ ...res.data.plan, policy: res.data.policy });
        } else {
          setPlan(res.data.plan);
          setStatus(res.data);
        }
      } catch (e) {
        alert("Failed to create task.");
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
      <div style={{padding:'2rem', maxWidth:'1000px', margin:'0 auto', height:'100%', display:'flex', flexDirection:'column'}}>
         <h1 style={{fontSize:'1.5rem', marginBottom:'0.5rem', fontWeight:'800'}}>Autonomous Research</h1>
         <p style={{color:'var(--text-muted)', marginBottom:'2rem'}}>Lirox can autonomously research topics and perform complex multi-step actions.</p>
         
         <div style={{display:'flex', gap:'0.75rem', marginBottom:'2rem'}}>
            <div className="card" style={{flex:1, display:'flex', alignItems:'center', padding:'0.75rem 1rem'}}>
               <Search size={18} style={{color:'var(--text-muted)', marginRight:'1rem'}} />
               <input value={goal} onChange={e => setGoal(e.target.value)} placeholder="What should Lirox research today?" style={{flex:1, border:'none', fontSize:'1rem', outline:'none'}} />
            </div>
            <button onClick={runTask} disabled={loading} className="btn btn-primary" style={{padding:'0 1.5rem', gap:'0.5rem'}}>
               {loading ? <RefreshCw size={18} className="spin"/> : <Sparkles size={18}/>}
               {loading ? 'Thinking...' : 'Start Job'}
            </button>
         </div>
  
         {plan && (
            <div className="fade-in card" style={{padding:'2rem', background:'white'}}>
               <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'1.5rem'}}>
                 <div>
                   <h3 style={{fontSize:'1.25rem', marginBottom:'0.25rem'}}>{plan.goal}</h3>
                   <div style={{fontSize:'0.875rem', color:'var(--text-muted)'}}>{plan.steps.length} Steps Planned</div>
                 </div>
                 {plan.policy && (
                   <div style={{padding:'0.5rem 1rem', background:'#fffbeb', color:'#d97706', borderRadius:'8px', fontSize:'0.75rem', fontWeight:'600', display:'flex', alignItems:'center', gap:'0.4rem', border:'1px solid #fde68a'}}>
                     <ShieldAlert size={14}/> Confirmation Required
                   </div>
                 )}
               </div>

               <div style={{display:'flex', flexDirection:'column', gap:'1rem', marginBottom:'2rem'}}>
                  {plan.steps.map((s, i) => (
                     <div key={i} style={{display:'flex', gap:'1rem', alignItems:'center', padding:'1rem', borderRadius:'12px', background:'var(--bg-color)', border:'1px solid var(--border-color)'}}>
                        <div style={{width:'28px', height:'28px', borderRadius:'50%', background:'white', border:'1px solid var(--border-color)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'0.8125rem', fontWeight:'700'}}>{i+1}</div>
                        <div style={{flex:1, fontSize:'0.9375rem'}}>{s.task}</div>
                        <div style={{fontSize:'0.7rem', fontWeight:'700', textTransform:'uppercase', letterSpacing:'0.05em', background:'white', padding:'0.25rem 0.6rem', borderRadius:'6px', border:'1px solid var(--border-color)', color:'var(--text-muted)'}}>{s.tools[0]}</div>
                     </div>
                  ))}
               </div>

               {plan.policy ? (
                 <div style={{background:'var(--bg-color)', padding:'1.5rem', borderRadius:'12px', border:'1px dashed var(--border-color)'}}>
                   <div style={{display:'flex', gap:'1rem'}}>
                     <button onClick={() => confirm(true)} className="btn btn-primary" style={{padding:'0.75rem 2rem'}}>Confirm Execution</button>
                     <button onClick={() => confirm(false)} className="btn btn-outline" style={{padding:'0.75rem 2rem'}}>Reject Plan</button>
                   </div>
                   <p style={{marginTop:'1rem', fontSize:'0.8125rem', color:'var(--text-muted)'}}>REASON: {plan.policy.reason}</p>
                 </div>
               ) : (
                 <div style={{display:'flex', alignItems:'center', gap:'0.75rem', color:'var(--success-color)', fontWeight:'600'}}>
                   <CheckCircle2 size={20}/> Auto-executed (Low Risk)
                 </div>
               )}
            </div>
         )}
      </div>
    );
};

const SettingsPage = () => {
    const [settings, setSettings] = useState({ allow_terminal_tool: false, auto_execute_max_steps: 5, default_provider: 'auto' });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetch = async () => {
            try {
                const res = await axios.get(`${API_BASE}/settings`);
                setSettings(res.data);
            } finally { setLoading(false); }
        };
        fetch();
    }, []);

    const save = async (s) => {
        setSettings(s);
        await axios.post(`${API_BASE}/settings`, s);
    };

    if (loading) return <div style={{padding:'2rem'}}>Loading settings...</div>;

    return (
        <div style={{padding:'2rem', maxWidth:'800px', margin:'0 auto'}}>
            <h1 style={{fontSize:'1.5rem', marginBottom:'2rem', fontWeight:'800'}}>Settings</h1>

            <div className="card" style={{padding:'2rem', display:'flex', flexDirection:'column', gap:'2.5rem'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <div>
                        <div style={{fontWeight:'700'}}>Silent Auto-Execution</div>
                        <div style={{fontSize:'0.875rem', color:'var(--text-muted)'}}>Automatically run research tasks below the threshold without asking.</div>
                    </div>
                </div>

                <div>
                    <div style={{display:'flex', justifyContent:'space-between', marginBottom:'0.75rem'}}>
                        <span style={{fontWeight:'600', fontSize:'0.875rem'}}>Max Auto Steps</span>
                        <span style={{color:'var(--primary-color)', fontWeight:'700'}}>{settings.auto_execute_max_steps} steps</span>
                    </div>
                    <input 
                      type="range" min="1" max="10" value={settings.auto_execute_max_steps} 
                      onChange={e => save({...settings, auto_execute_max_steps: parseInt(e.target.value)})}
                      style={{width:'100%', height:'6px', borderRadius:'10px', appearance:'none', background:'var(--border-color)', outline:'none'}}
                    />
                </div>

                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', paddingTop:'1.5rem', borderTop:'1px solid var(--border-color)'}}>
                    <div>
                        <div style={{fontWeight:'700'}}>Terminal Protection</div>
                        <div style={{fontSize:'0.875rem', color:'var(--text-muted)'}}>Always require confirmation for shell commands.</div>
                    </div>
                    <div style={{background:'var(--bg-color)', color:'var(--primary-color)', padding:'0.4rem 0.8rem', borderRadius:'8px', fontSize:'0.75rem', fontWeight:'700', border:'1px solid var(--border-color)'}}>ALWAYS ON</div>
                </div>

                <div style={{paddingTop:'1rem'}}>
                    <button 
                        onClick={async () => {
                            if (window.confirm("Hard reset conversation memory?")) {
                                await axios.post(`${API_BASE}/memory/clear`);
                                alert("Memory cleared.");
                            }
                        }}
                        className="btn btn-outline" style={{color:'var(--error-color)', borderColor:'var(--error-color)'}}
                    >Clear Persistence</button>
                </div>
            </div>
        </div>
    );
};

const SetupPage = ({ profile, setProfile, onComplete }) => {
    // ... setup page remains largely the same but with v0.4 branding
    return <div style={{padding:'2rem', textAlign:'center'}}>
        <h2>Welcome to Lirox v0.4</h2>
        <p>Complete your profile to get started with the premium AI experience.</p>
        <button onClick={onComplete} className="btn btn-primary">Start Onboarding</button>
    </div>;
}

export default App;
