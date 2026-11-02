import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { HeartHandshake, Users, ArrowRight, ArrowUpRight, ShieldCheck, Clock3, LogOut, Menu, X, Check } from 'lucide-react';
import { api } from './api';
import Dashboard from './volunteers/Dashboard';
import PublicRequest, { RequestVerification } from './activities/PublicRequest';
import PublicEvents from './activities/PublicEvents';
import './styles.css';
import './volunteers/styles.css';
import './activities/styles.css';
import './design/stitch.css';
import Auth from './design/Auth';
import Landing from './design/Landing';

const steps = ['Crea tu cuenta', 'Completa tu perfil', 'Participa en una actividad'];

function App() {
  const [session, setSession] = useState(null);
  const [view, setView] = useState(() => window.location.hash.startsWith('#confirm-request=') ? 'verify-request' : 'home');
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [menu, setMenu] = useState(false);
  useEffect(() => { api('session/').then(data => { setSession(data); setView(window.location.hash.startsWith('#confirm-request=') ? 'verify-request' : data.user ? 'dashboard' : 'home'); setStatus('ready'); }).catch(() => setStatus('offline')); }, []);
  const workspace = (view === 'dashboard' && Boolean(session?.user)) || (view === 'request' && session?.user?.available_portals?.includes('requester'));
  const brand = session?.foundation_name || 'Fundación Apoyo Comunitario';
  const navigate = next => { setView(next); setMenu(false); setError(''); window.scrollTo(0, 0); };
  async function signOut() {
    try { await api('logout/', { method: 'POST' }); const data = await api('session/'); setSession(data); navigate('home'); }
    catch { setError('No se pudo cerrar la sesión. Vuelve a intentarlo.'); }
  }
  return <>
    <a className="skip" href="#main">Saltar al contenido</a>
    <header className={`header ${workspace ? 'workspace-public-header' : ''}`}>
      <button className="brand" onClick={() => navigate(session?.user ? 'dashboard' : 'home')}><span className="brand-icon"><HeartHandshake size={25}/></span><span>{brand}<small>RED DE VOLUNTARIADO</small></span></button>
      <button className="mobile-menu icon-btn" aria-label={menu ? 'Cerrar menú' : 'Abrir menú'} aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? <X/> : <Menu/>}</button>
      <nav aria-label="Navegación principal" className={menu ? 'top-nav open' : 'top-nav'}>
        <button className="text-button" disabled={status !== 'ready'} onClick={() => navigate('request')}>Solicitar apoyo</button>
        {session?.user ? <><span className="user-label">{session.user.first_name}</span><button className="text-button" onClick={() => navigate('dashboard')}>Mi espacio</button><button className="text-button" onClick={signOut}><LogOut size={16}/> Salir</button></> : <><button className="text-button" onClick={() => navigate('home')}>Nuestra comunidad</button><button className="text-button" onClick={() => navigate('login')}>Iniciar sesión</button><button className="button primary small" disabled={status !== 'ready'} onClick={() => navigate('register')}>Ser voluntario <ArrowUpRight size={16}/></button></>}
      </nav>
    </header>
    {status === 'offline' && <div className="connection" role="alert">No hay conexión con el backend. Inicia Django y recarga la página.</div>}
    {error && <div role="alert" className="error global-error">{error}</div>}
    <main id="main" className={workspace ? 'workspace-main' : 'public-main'}>
      {view === 'home' && <Landing brand={brand} ready={status === 'ready'} navigate={navigate}/>}
      {['login', 'register', 'register-requester'].includes(view) && <Auth key={view} mode={view === 'login' ? 'login' : 'register'} initialType={view === 'register-requester' ? 'requester' : 'volunteer'} brand={brand} navigate={navigate} onLogin={user => { setSession(old => ({ ...old, user })); navigate('dashboard'); }}/>}
      {view === 'dashboard' && session?.user && <Dashboard key={session.user.id} foundation={brand} onPublic={() => navigate('home')} onSignOut={signOut} user={session.user} setUser={user => setSession(old => ({ ...old, user }))}/>}
      {view === 'request' && (session?.user?.available_portals?.includes('requester') ? <Dashboard key={session.user.id} foundation={brand} onPublic={() => navigate('home')} onSignOut={signOut} initialPortal="requester" initialTab="new-request" user={session.user} setUser={user => setSession(old => ({ ...old, user }))}/> : <PublicRequest navigate={navigate}/>)}
      {view === 'verify-request' && <RequestVerification ready={status === 'ready'} navigate={navigate}/>}
    </main>
    <footer className={workspace ? 'workspace-footer' : 'public-footer'}><span>© {new Date().getFullYear()} {brand}</span><span>Personas que se unen. Comunidades que crecen.</span></footer>
  </>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
