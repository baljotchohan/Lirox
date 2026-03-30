import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  MessageSquare, 
  Settings, 
  User, 
  ListChecks, 
  Search, 
  PlusCircle, 
  Key, 
  Cpu, 
  History, 
  Info, 
  Terminal, 
  Save, 
  CheckCircle2, 
  X, 
  ShieldAlert, 
  ArrowRight, 
  ArrowLeft,
  ChevronDown,
  Activity
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api';

const App = () => {
  const [page, setPage] = useState('chat');
  const [profile, setProfile] = useState({});
  const [isSetup, setIsSetup] = useState(true);
  const [loading, setLoading] = useState(true);

  // Fetch initial state
  useEffect(() => {
    const checkProfile = async () => {
      try {
        const res = await axios.get(`${API_BASE}/profile`);
        setProfile(res.data);
        // Better check for setup completion
        setIsSetup(!!res.data.user_name);
        if (!res.data.user_name) setPage('setup');
      } catch (e) {
        console.error("Failed to fetch profile", e);
      } finally {
        setLoading(false);
      }
    };
    checkProfile();
  }, []);

  if (loading) return <div style={{height:'100vh', display:'flex', alignItems:'center', justifyContent:'center'}}>Loading Lirox...</div>;

  return (
    <div className="app-container" style={{display:'flex', height:'100vh', overflow:'hidden'}}>
      {/* Sidebar */}
      <nav style={{
        width: '260px', 
        borderRight: '1px solid var(--border-color)', 
        background: 'white',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.5rem 1rem'
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
           <div style={{fontSize:'0.75rem', color:'var(--text-muted)', marginBottom:'0.25rem'}}>Agent Status</div>
           <div style={{display:'flex', alignItems:'center', gap:'0.5rem'}}>
              <div style={{width:'8px', height:'8px', borderRadius:'50%', background:'var(--success-color)'}}></div>
              <span style={{fontSize:'0.8125rem', fontWeight:'500'}}>{profile.agent_name || 'Atlas'} Online</span>
           </div>
        </div>
      </nav>

      {/* Main Content */}
      <main style={{flex:1, overflow:'hidden', position:'relative', background:'var(--bg-color)'}}>
        {page === 'chat' && <ChatPage profile={profile} />}
        {page === 'task' && <TaskPage profile={profile} />}
        {page === 'setup' && <SetupPage profile={profile} setProfile={setProfile} onComplete={() => setPage('chat')} />}
        {page === 'settings' && <SettingsPage />}
      </main>
    </div>
  );
};

const NavItem = ({ icon, label, active, onClick }) => (
  <button 
    onClick={onClick}
    style={{
      display:'flex', 
      alignItems:'center', 
      gap:'0.75rem', 
      padding:'0.75rem 1rem', 
      width:'100%',
      borderRadius:'var(--radius-md)',
      background: active ? 'rgba(37, 99, 235, 0.08)' : 'transparent',
      color: active ? 'var(--primary-color)' : 'var(--text-muted)',
      fontWeight: active ? '600' : '500'
    }}
  >
    {icon}
    <span>{label}</span>
  </button>
);

/* Components */

const ChatPage = ({ profile }) => {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: `Hello ${profile.user_name || 'there'}! I'm ${profile.agent_name || 'Lirox'}. How can I help you today?` }
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
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.response }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Error: Failed to connect to server. Check if Lirox is running." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{display:'flex', flexDirection:'column', height:'100%', padding:'1.5rem', maxWidth:'900px', margin:'0 auto'}}>
       <div style={{flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:'1.5rem', paddingBottom:'2rem'}}>
          {messages.map((m, i) => (
             <div key={i} className="fade-in" style={{
                display:'flex', 
                flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
                gap:'1rem',
                alignItems:'flex-start'
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
                   padding:'1rem 1.25rem', 
                   maxWidth:'80%', 
                   fontSize:'0.9375rem', 
                   lineHeight:'1.5',
                   background: m.role === 'user' ? 'var(--primary-color)' : 'white',
                   color: m.role === 'user' ? 'white' : 'var(--text-main)',
                   borderRadius: m.role === 'user' ? '1rem 0.25rem 1rem 1rem' : '0.25rem 1rem 1rem 1rem',
                   boxShadow: m.role === 'user' ? '0 10px 15px -3px rgba(37, 99, 235, 0.2)' : 'var(--shadow-sm)'
                }}>
                   {m.content}
                </div>
             </div>
          ))}
          {loading && <div style={{color:'var(--text-muted)', fontSize:'0.875rem', paddingLeft:'3rem'}}>Lirox is thinking...</div>}
       </div>

       <div style={{marginTop:'auto', paddingTop:'1.5rem'}}>
          <div style={{display:'flex', gap:'0.75rem', background:'white', padding:'0.75rem', borderRadius:'var(--radius-lg)', border:'1px solid var(--border-color)', boxShadow:'var(--shadow-md)'}}>
             <input 
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendMessage()}
                placeholder="Message Lirox..." 
                style={{flex:1, border:'none', padding:'0.5rem', fontSize:'0.9375rem'}}
             />
             <button onClick={sendMessage} className="btn btn-primary" style={{padding:'0 1.25rem'}}>
                <ArrowRight size={18}/>
             </button>
          </div>
          <div style={{textAlign:'center', color:'var(--text-muted)', fontSize:'0.75rem', marginTop:'0.75rem'}}>
             Lirox v0.3.1 • Powered by {profile.provider || 'Groq'}
          </div>
       </div>
    </div>
  );
};

const SetupPage = ({ profile, setProfile, onComplete }) => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({ ...profile });
  const [keys, setKeys] = useState({ gemini:'', groq:'', openai:'', openrouter:'', deepseek:'' });
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await axios.post(`${API_BASE}/profile`, formData);
      await axios.post(`${API_BASE}/keys`, keys);
      const res = await axios.get(`${API_BASE}/profile`);
      setProfile(res.data);
      onComplete();
    } catch (e) {
      alert("Failed to save. Ensure backend is running.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{display:'flex', alignItems:'center', justifyContent:'center', height:'100%', padding:'2rem'}}>
       <div className="card fade-in" style={{width:'100%', maxWidth:'500px', padding:'2.5rem'}}>
          <h2 style={{marginBottom:'1.5rem', display:'flex', alignItems:'center', gap:'0.75rem'}}>
             <div style={{width:'32px', height:'32px', borderRadius:'10px', background:'var(--primary-color)', color:'white', display:'flex', alignItems:'center', justifyContent:'center'}}>{step}</div>
             {step === 1 ? 'Configure Identity' : 'Add API Keys'}
          </h2>

          {step === 1 ? (
             <div style={{display:'flex', flexDirection:'column', gap:'1.25rem'}}>
                <InputGroup label="Agent Name" value={formData.agent_name} onChange={v => setFormData({...formData, agent_name:v})} placeholder="e.g. Atlas" />
                <InputGroup label="Your Name" value={formData.user_name} onChange={v => setFormData({...formData, user_name:v})} placeholder="e.g. Alex" />
                <InputGroup label="Your Niche" value={formData.niche} onChange={v => setFormData({...formData, niche:v})} placeholder="e.g. Developer, Founder..." />
                <button onClick={() => setStep(2)} className="btn btn-primary" style={{marginTop:'1rem', justifyContent:'center'}}>
                   Continue <ArrowRight size={18}/>
                </button>
             </div>
          ) : (
             <div style={{display:'flex', flexDirection:'column', gap:'1.25rem'}}>
                <InputGroup type="password" label="Groq Key (Recommended)" value={keys.groq} onChange={v => setKeys({...keys, groq:v})} placeholder="gsk_..." />
                <InputGroup type="password" label="Gemini Key" value={keys.gemini} onChange={v => setKeys({...keys, gemini:v})} placeholder="AI..." />
                <InputGroup type="password" label="OpenRouter Key" value={keys.openrouter} onChange={v => setKeys({...keys, openrouter:v})} placeholder="sk-or-..." />
                <div style={{display:'flex', gap:'1rem', marginTop:'1rem'}}>
                   <button onClick={() => setStep(1)} className="btn btn-outline" style={{flex:1, justifyContent:'center'}}>Back</button>
                   <button onClick={save} className="btn btn-primary" style={{flex:1, justifyContent:'center'}}>
                      {saving ? 'Saving...' : 'Complete Setup'}
                   </button>
                </div>
             </div>
          )}
       </div>
    </div>
  );
};

const TaskPage = () => {
  const [goal, setGoal] = useState('');
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState('');

  const createPlan = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setResult('');
    try {
      const res = await axios.post(`${API_BASE}/plan`, { goal });
      setPlan(res.data);
    } catch (e) {
      alert("Failed to create plan.");
    } finally {
      setLoading(false);
    }
  };

  const executePlan = async () => {
    setExecuting(true);
    try {
      const res = await axios.post(`${API_BASE}/execute-plan`);
      setResult(res.data.response);
    } catch (e) {
      setResult("Execution failed.");
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div style={{padding:'2rem', maxWidth:'1000px', margin:'0 auto', height:'100%', display:'flex', flexDirection:'column'}}>
       <h1 style={{fontSize:'1.5rem', marginBottom:'1.5rem'}}>Task Planning</h1>
       
       <div style={{display:'flex', gap:'0.75rem', marginBottom:'2rem'}}>
          <div className="card" style={{flex:1, display:'flex', alignItems:'center', padding:'0.75rem 1rem'}}>
             <Search size={18} style={{color:'var(--text-muted)', marginRight:'1rem'}} />
             <input 
                value={goal}
                onChange={e => setGoal(e.target.value)}
                placeholder="Describe what you want to accomplish..." 
                style={{flex:1, border:'none', fontSize:'1rem'}}
             />
          </div>
          <button onClick={createPlan} disabled={loading} className="btn btn-primary" style={{padding:'0 1.5rem'}}>
             {loading ? 'Thinking...' : 'Plan Task'}
          </button>
       </div>

       {plan && (
          <div className="fade-in" style={{flex:1, overflowY:'auto'}}>
             <div className="card" style={{padding:'2rem', marginBottom:'1.5rem'}}>
                <h3 style={{marginBottom:'1rem', color:'var(--primary-color)'}}>Plan: {plan.goal}</h3>
                <div style={{display:'flex', flexDirection:'column', gap:'1rem'}}>
                   {plan.steps.map((s, i) => (
                      <div key={i} style={{display:'flex', gap:'1rem', alignItems:'center', padding:'0.75rem', borderRadius:'var(--radius-md)', background:'var(--bg-color)'}}>
                         <div style={{width:'24px', height:'24px', borderRadius:'12px', border:'1px solid var(--border-color)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:'0.75rem', fontWeight:'700'}}>{i+1}</div>
                         <div style={{flex:1, fontSize:'0.9375rem'}}>{s.task}</div>
                         <div style={{fontSize:'0.75rem', background:'white', padding:'0.25rem 0.5rem', borderRadius:'4px', border:'1px solid var(--border-color)'}}>{s.tools.join(', ')}</div>
                      </div>
                   ))}
                </div>
                
                <div style={{marginTop:'2rem', display:'flex', gap:'1rem'}}>
                   <button onClick={executePlan} disabled={executing} className="btn btn-primary">
                      {executing ? <p>Executing...</p> : <p><Activity size={18}/> Execute Plan</p>}
                   </button>
                   <button onClick={() => setPlan(null)} className="btn btn-outline">Cancel</button>
                </div>
             </div>
             
             {result && (
                <div className="card" style={{padding:'2rem', background:'#f0fdf4', borderColor:'#bbf7d0'}}>
                   <h3 style={{marginBottom:'1rem', display:'flex', alignItems:'center', gap:'0.5rem'}}>
                      <CheckCircle2 size={20} color="var(--success-color)" /> Result Summary
                   </h3>
                   <div style={{whiteSpace:'pre-wrap', fontSize:'0.9375rem', lineHeight:'1.6'}}>{result}</div>
                </div>
             )}
          </div>
       )}
    </div>
  );
};

const SettingsPage = () => {
    const [settings, setSettings] = useState({ allow_terminal_tool: false, memory_limit: 20, default_provider: 'auto' });
    const [providers, setProviders] = useState({ available: [], all: [] });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const s = await axios.get(`${API_BASE}/settings`);
                const p = await axios.get(`${API_BASE}/providers`);
                setSettings(s.data);
                setProviders(p.data);
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        fetchSettings();
    }, []);

    const save = async (newSettings) => {
        setSettings(newSettings);
        try {
            await axios.post(`${API_BASE}/settings`, newSettings);
        } catch (e) {
            alert("Failed to save settings.");
        }
    };

    if (loading) return <div style={{padding:'2rem'}}>Loading settings...</div>;

    return (
        <div style={{padding:'2rem', maxWidth:'800px', margin:'0 auto'}}>
            <h1 style={{fontSize:'1.5rem', marginBottom:'2rem'}}>System Settings</h1>

            <div className="card" style={{padding:'1.5rem', display:'flex', flexDirection:'column', gap:'2rem'}}>
                <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <div>
                        <div style={{fontWeight:'600'}}>Terminal Tool Access</div>
                        <div style={{fontSize:'0.875rem', color:'var(--text-muted)'}}>Allow the agent to run local safe commands.</div>
                    </div>
                    <label className="switch" style={{position:'relative', display:'inline-block', width:'50px', height:'24px'}}>
                        <input 
                            type="checkbox" 
                            checked={settings.allow_terminal_tool} 
                            onChange={e => save({...settings, allow_terminal_tool: e.target.checked})}
                            style={{opacity:0, width:0, height:0}}
                        />
                        <span style={{
                            position:'absolute', cursor:'pointer', top:0, left:0, right:0, bottom:0, background: settings.allow_terminal_tool ? 'var(--primary-color)' : '#ccc', borderRadius:'34px', transition:'0.4s'
                        }}></span>
                    </label>
                </div>

                <div>
                    <div style={{fontWeight:'600', marginBottom:'1rem'}}>Default Provider</div>
                    <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(150px, 1fr))', gap:'0.75rem'}}>
                        {providers.all.map(p => (
                            <button 
                                key={p}
                                onClick={() => save({...settings, default_provider: p})}
                                className={settings.default_provider === p ? 'btn btn-primary' : 'btn btn-outline'}
                                style={{justifyContent:'center', opacity: providers.available.includes(p) ? 1 : 0.5}}
                            >
                                {p.charAt(0).toUpperCase() + p.slice(1)}
                                {!providers.available.includes(p) && <Key size={14} style={{marginLeft:'auto'}} />}
                            </button>
                        ))}
                    </div>
                </div>

                <div style={{paddingTop:'1rem', borderTop:'1px solid var(--border-color)'}}>
                    <button 
                        onClick={async () => {
                            if (window.confirm("Clear all conversation memory? Profile and keys will be kept.")) {
                                await axios.post(`${API_BASE}/memory/clear`);
                                alert("Memory cleared.");
                            }
                        }}
                        className="btn btn-outline" 
                        style={{color:'var(--error-color)', borderColor:'var(--error-color)'}}
                    >
                        Clear Conversation Memory
                    </button>
                </div>
            </div>
        </div>
    );
};

const InputGroup = ({ label, value, onChange, placeholder, type="text" }) => (
  <div style={{display:'flex', flexDirection:'column', gap:'0.5rem'}}>
    <label style={{fontSize:'0.875rem', fontWeight:'500', color:'var(--text-muted)'}}>{label}</label>
    <input 
      type={type}
      className="card"
      style={{padding:'0.75rem', width:'100%', fontSize:'0.9375rem'}}
      value={value || ''}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
    />
  </div>
);

export default App;
