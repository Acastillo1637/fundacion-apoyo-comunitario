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

const steps = ['Crea tu cuenta', 'Completa tu perfil', 'Participa en una actividad'];

function App() {
  const [session, setSession] = useState(null);
  const [view, setView] = useState(() => window.location.hash.startsWith('#confirm-request=') ? 'verify-request' : 'home');
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [menu, setMenu] = useState(false);
  useEffect(() => { api('session/').then(data => { setSession(data); setView(window.location.hash.startsWith('#confirm-request=') ? 'verify-request' : data.user ? 'dashboard' : 'home'); setStatus('ready'); }).catch(() => setStatus('offline')); }, []);
  const brand = session?.foundation_name || 'Fundación Apoyo Comunitario';
  const navigate = next => { setView(next); setMenu(false); setError(''); window.scrollTo(0, 0); };
  async function signOut() {
    try { await api('logout/', { method: 'POST' }); const data = await api('session/'); setSession(data); navigate('home'); }
    catch { setError('No se pudo cerrar la sesión. Vuelve a intentarlo.'); }
  }
  return <>
    <a className="skip" href="#main">Saltar al contenido</a>
    <header className="header">
      <button className="brand" onClick={() => navigate(session?.user ? 'dashboard' : 'home')}><span className="brand-icon"><HeartHandshake size={25}/></span><span>{brand}<small>RED DE VOLUNTARIADO</small></span></button>
      <button className="mobile-menu icon-btn" aria-label={menu ? 'Cerrar menú' : 'Abrir menú'} aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? <X/> : <Menu/>}</button>
      <nav aria-label="Navegación principal" className={menu ? 'top-nav open' : 'top-nav'}>
        <button className="text-button" disabled={status !== 'ready'} onClick={() => navigate('request')}>Solicitar apoyo</button>
        {session?.user ? <><span className="user-label">{session.user.first_name}</span><button className="text-button" onClick={() => navigate('dashboard')}>Mi espacio</button><button className="text-button" onClick={signOut}><LogOut size={16}/> Salir</button></> : <><button className="text-button" onClick={() => navigate('home')}>Nuestra comunidad</button><button className="text-button" onClick={() => navigate('login')}>Iniciar sesión</button><button className="button primary small" disabled={status !== 'ready'} onClick={() => navigate('register')}>Ser voluntario <ArrowUpRight size={16}/></button></>}
      </nav>
    </header>
    {status === 'offline' && <div className="connection" role="alert">No hay conexión con el backend. Inicia Django y recarga la página.</div>}
    {error && <div role="alert" className="error global-error">{error}</div>}
    <main id="main">
      {view === 'home' && <Landing brand={brand} ready={status === 'ready'} navigate={navigate}/>}
      {['login', 'register', 'register-requester'].includes(view) && <Auth key={view} mode={view === 'login' ? 'login' : 'register'} initialType={view === 'register-requester' ? 'requester' : 'volunteer'} brand={brand} navigate={navigate} onLogin={user => { setSession(old => ({ ...old, user })); navigate('dashboard'); }}/>}
      {view === 'dashboard' && session?.user && <Dashboard user={session.user} setUser={user => setSession(old => ({ ...old, user }))}/>}
      {view === 'request' && (session?.user?.available_portals?.includes('requester') ? <Dashboard initialPortal="requester" initialTab="new-request" user={session.user} setUser={user => setSession(old => ({ ...old, user }))}/> : <PublicRequest navigate={navigate}/>)}
      {view === 'verify-request' && <RequestVerification ready={status === 'ready'} navigate={navigate}/>}
    </main>
    <footer><span>© {new Date().getFullYear()} {brand}</span><span>Personas que se unen. Comunidades que crecen.</span></footer>
  </>;
}

function Landing({ ready, navigate }) {
  return <>
    <section className="hero wrap">
      <div className="hero-copy"><span className="eyebrow"><span className="dot"/> UNA COMUNIDAD CON PROPÓSITO</span><h1>Tu tiempo puede<br/>cambiar <span>una vida.</span></h1><p>Conecta tus habilidades con las personas que más las necesitan. Construyamos juntos una comunidad más solidaria.</p><div className="actions"><button className="button primary" disabled={!ready} onClick={() => navigate('register')}>Quiero ser voluntario <ArrowRight size={18}/></button><a className="button secondary" href="#como-funciona">Cómo participar</a></div><div className="hero-note"><ShieldCheck size={18}/><span>Tú decides cuándo y cómo ayudar.</span></div></div>
      <div className="hero-art" aria-label="Ilustración de una comunidad que conecta sus habilidades"><div className="art-grid"/><span className="art-caption">CADA PERSONA CUENTA</span><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="community-core"><HeartHandshake size={72} strokeWidth={1.3}/></div><div className="skill-bubble bubble-one"><HeartHandshake size={20}/><span>Compromiso<br/><strong>que conecta</strong></span></div><div className="skill-bubble bubble-two"><Users size={20}/><span>Un espacio<br/><strong>para todos</strong></span></div><span className="person person-a">✦</span><span className="person person-b">+</span><span className="person person-c">✦</span><div className="art-bottom"><span className="dot"/> HABILIDADES + TIEMPO + PROPÓSITO</div></div>
    </section>
    <section className="values-strip"><div className="wrap values"><div><Users/><span><strong>Una comunidad cercana</strong>Personas con ganas de aportar</span></div><div><Clock3/><span><strong>A tu ritmo</strong>Disponibilidad que tú eliges</span></div><div><ShieldCheck/><span><strong>Participación responsable</strong>Requisitos revisados por el equipo</span></div></div></section>
    <section id="como-funciona" className="wrap how"><div className="section-heading"><div><span className="eyebrow">DAR EL PRIMER PASO ES SENCILLO</span><h2>Hay muchas formas de ayudar.<br/>Encuentra la tuya.</h2></div><p>Organizamos la coordinación para que puedas enfocarte en lo que importa: aportar.</p></div><div className="step-grid">{steps.map((step, i) => <article className="step" key={step}><span className="step-number">0{i + 1}</span><h3>{step}</h3><p>{['Regístrate con tu correo y verifica tu cuenta para comenzar.', 'Cuéntanos tus habilidades y cuándo puedes participar.', 'El equipo revisará los requisitos y coordinará tu participación contigo.'][i]}</p></article>)}</div></section>
    <section className="wrap"><div className="cta"><div><span className="eyebrow">EL CAMBIO EMPIEZA CONTIGO</span><h2>Lo que sabes hacer puede hacer la diferencia.</h2></div><button className="button light" disabled={!ready} onClick={() => navigate('register')}>Sumarme a la comunidad <ArrowRight size={18}/></button></div></section>
    <section className="wrap public-events-section"><PublicEvents/></section>
  </>;
}

function Auth({ mode, navigate, onLogin, brand, initialType }) {
  const register = mode === 'register';
  const [mfaRequired, setMfaRequired] = useState(false);
  const [accountType, setAccountType] = useState(initialType || 'volunteer');
  const [requesterType, setRequesterType] = useState('person');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [success, setSuccess] = useState('');
  useEffect(() => { setError(''); setSuccess(''); }, [mode]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form);
    if (register) { payload.adult = form.has('adult'); payload.privacy = form.has('privacy'); payload.whatsapp = form.has('whatsapp'); payload.authorized_representative = form.has('authorized_representative'); }
    try {
      const result = await api(register ? 'register/' : 'login/', { method: 'POST', body: JSON.stringify(payload) });
      if (register) setSuccess(result.detail); else onLogin(result.user);
    } catch (err) { setError(err.message); setMfaRequired(Boolean(err.mfaRequired)); }
    finally { setBusy(false); }
  }
  return <section className="auth-layout wrap"><aside className="auth-story"><span className="eyebrow">BIENVENIDO A {brand.toUpperCase()}</span><h1>{register ? 'Tu próxima gran contribución empieza aquí.' : 'Qué bueno tenerte de vuelta.'}</h1><p>Un espacio para conectar tu tiempo y tus habilidades con oportunidades de ayudar.</p><div className="story-mark"><HeartHandshake size={100} strokeWidth={1}/></div><div className="story-foot"><ShieldCheck size={20}/><span>Tu información se comparte únicamente según los permisos y necesidades de coordinación.</span></div></aside><div className="auth-form"><span className="eyebrow">PORTAL DE LA COMUNIDAD</span><h2>{register ? 'Crea tu cuenta' : 'Inicia sesión'}</h2><p>{register ? 'Nos alegra que quieras ser parte de la comunidad.' : 'Ingresa para continuar con tu participación.'}</p>{success ? <div role="status" className="success"><Check/><p>{success}</p><button className="button secondary" onClick={() => navigate('login')}>Ir a iniciar sesión</button></div> : <form onSubmit={submit} key={mode}>
      {register && <><label className="field">¿Cómo quieres participar?<select name="account_type" value={accountType} onChange={event => setAccountType(event.target.value)}><option value="volunteer">Voluntario: quiero ayudar</option><option value="requester">Solicitante: necesito apoyo para mí o una entidad</option></select></label><div className="form-row"><Field label="Nombre del contacto" name="first_name" autoComplete="given-name" maxLength={80}/><Field label="Apellido" name="last_name" autoComplete="family-name" maxLength={80}/></div>
        {accountType === 'requester' && <><label className="field">Tipo de solicitante<select name="requester_type" value={requesterType} onChange={event => setRequesterType(event.target.value)}><option value="person">Persona natural</option><option value="company">Empresa</option><option value="institution">Institución</option></select></label>{requesterType !== 'person' && <><Field label="Nombre de la empresa o institución" name="organization" maxLength={150}/><label className="checkbox"><input type="checkbox" name="authorized_representative" required/>Estoy autorizado para representar a esta entidad.</label></>}<Field label="Teléfono de contacto" name="phone" type="tel" maxLength={20}/><label className="field">Comuna<input name="commune" maxLength={80}/></label></>}
      </>}
      <Field label="Correo electrónico" name="email" type="email" autoComplete="email" placeholder="tu@correo.cl" maxLength={254}/>
      <Field label="Contraseña" name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 12 : undefined} maxLength={256}/>
      {!register && mfaRequired && <Field label="Código de autenticación o recuperación" name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={20}/>}
      {register ? <><small className="help">Usa al menos 12 caracteres. Evita datos personales y contraseñas comunes.</small><label className="checkbox"><input type="checkbox" name="adult" required/>Confirmo que tengo 18 años o más.</label><label className="checkbox"><input type="checkbox" name="privacy" required/>Acepto el tratamiento de mis datos para gestionar mi cuenta y participación. <span className="help">Entorno de desarrollo: el aviso institucional definitivo está pendiente. Usa datos ficticios.</span></label>{accountType === 'volunteer' && <label className="checkbox"><input type="checkbox" name="whatsapp"/>Quiero recibir invitaciones por WhatsApp mediante contacto del equipo. Es opcional.</label>}</> : <a className="forgot" href="/accounts/password/reset/">¿Olvidaste tu contraseña?</a>}
      {error && <div className="error" role="alert">{error}</div>}
      <button className="button primary full" disabled={busy}>{busy ? 'Procesando…' : register ? 'Crear mi cuenta' : 'Ingresar a mi espacio'}<ArrowRight size={18}/></button>
    </form>}
    <p className="switch">{register ? '¿Ya tienes una cuenta?' : '¿Aún no eres parte?'} <button className="text-button" onClick={() => navigate(register ? 'login' : 'register')}>{register ? 'Inicia sesión' : 'Regístrate'}</button></p><div className="form-footer"><ShieldCheck size={15}/> Un solo acceso para todos los perfiles. Si activaste segundo factor, ingresa tu código aquí.</div></div></section>;
}

function Field({ label, ...props }) {
  return <label className="field">{label}<input required {...props}/></label>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
