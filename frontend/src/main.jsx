import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { HeartHandshake, LayoutDashboard, Users, CalendarDays, FileCheck2, ArrowRight, ArrowUpRight, ShieldCheck, Clock3, LogOut, Menu, X, Check, UserRound, MapPin, Mail, ChevronRight, Settings2 } from 'lucide-react';
import { api } from './api';
import './styles.css';

const steps = ['Crea tu cuenta', 'Completa tu perfil', 'Participa en una actividad'];

function App() {
  const [session, setSession] = useState(null);
  const [view, setView] = useState('home');
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [menu, setMenu] = useState(false);
  useEffect(() => { api('session/').then(data => { setSession(data); setView(data.user ? 'dashboard' : 'home'); setStatus('ready'); }).catch(() => setStatus('offline')); }, []);
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
        {session?.user ? <><span className="user-label">{session.user.first_name}</span><button className="text-button" onClick={() => navigate('dashboard')}>Mi espacio</button><button className="text-button" onClick={signOut}><LogOut size={16}/> Salir</button></> : <><button className="text-button" onClick={() => navigate('home')}>Nuestra comunidad</button><button className="text-button" onClick={() => navigate('login')}>Iniciar sesión</button><button className="button primary small" disabled={status !== 'ready'} onClick={() => navigate('register')}>Ser voluntario <ArrowUpRight size={16}/></button></>}
      </nav>
    </header>
    {status === 'offline' && <div className="connection" role="alert">No hay conexión con el backend. Inicia Django y recarga la página.</div>}
    {error && <div role="alert" className="error global-error">{error}</div>}
    <main id="main">
      {view === 'home' && <Landing brand={brand} ready={status === 'ready'} navigate={navigate}/>}
      {(view === 'login' || view === 'register') && <Auth mode={view} brand={brand} navigate={navigate} onLogin={user => { setSession(old => ({ ...old, user })); navigate('dashboard'); }}/>}
      {view === 'dashboard' && session?.user && <Dashboard user={session.user} setUser={user => setSession(old => ({ ...old, user }))}/>}
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
  </>;
}

function Auth({ mode, navigate, onLogin, brand }) {
  const register = mode === 'register';
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [success, setSuccess] = useState(''), [continueUrl, setContinueUrl] = useState('');
  useEffect(() => { setError(''); setSuccess(''); setContinueUrl(''); }, [mode]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form);
    if (register) { payload.adult = form.has('adult'); payload.privacy = form.has('privacy'); payload.whatsapp = form.has('whatsapp'); }
    try {
      const result = await api(register ? 'register/' : 'login/', { method: 'POST', body: JSON.stringify(payload) });
      if (register) setSuccess(result.detail); else onLogin(result.user);
    } catch (err) { setError(err.message); setContinueUrl(err.continueUrl || ''); }
    finally { setBusy(false); }
  }
  return <section className="auth-layout wrap"><aside className="auth-story"><span className="eyebrow">BIENVENIDO A {brand.toUpperCase()}</span><h1>{register ? 'Tu próxima gran contribución empieza aquí.' : 'Qué bueno tenerte de vuelta.'}</h1><p>Un espacio para conectar tu tiempo y tus habilidades con oportunidades de ayudar.</p><div className="story-mark"><HeartHandshake size={100} strokeWidth={1}/></div><div className="story-foot"><ShieldCheck size={20}/><span>Tu información se comparte únicamente según los permisos y necesidades de coordinación.</span></div></aside><div className="auth-form"><span className="eyebrow">PORTAL DEL VOLUNTARIO</span><h2>{register ? 'Crea tu cuenta' : 'Inicia sesión'}</h2><p>{register ? 'Nos alegra que quieras ser parte de la comunidad.' : 'Ingresa para continuar con tu participación.'}</p>{success ? <div role="status" className="success"><Check/><p>{success}</p><button className="button secondary" onClick={() => navigate('login')}>Ir a iniciar sesión</button></div> : <form onSubmit={submit} key={mode}>
      {register && <div className="form-row"><Field label="Nombre" name="first_name" autoComplete="given-name" maxLength={80}/><Field label="Apellido" name="last_name" autoComplete="family-name" maxLength={80}/></div>}
      <Field label="Correo electrónico" name="email" type="email" autoComplete="email" placeholder="tu@correo.cl" maxLength={254}/>
      <Field label="Contraseña" name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 12 : undefined} maxLength={256}/>
      {register ? <><small className="help">Usa al menos 12 caracteres. Evita datos personales y contraseñas comunes.</small><label className="checkbox"><input type="checkbox" name="adult" required/>Confirmo que tengo 18 años o más.</label><label className="checkbox"><input type="checkbox" name="privacy" required/>Acepto el tratamiento de mis datos para gestionar mi cuenta y participación. <span className="help">Entorno de desarrollo: el aviso institucional definitivo está pendiente. Usa datos ficticios.</span></label><label className="checkbox"><input type="checkbox" name="whatsapp"/>Quiero recibir invitaciones por WhatsApp mediante contacto del equipo. Es opcional.</label></> : <a className="forgot" href="/accounts/password/reset/">¿Olvidaste tu contraseña?</a>}
      {error && <div className="error" role="alert">{error}{continueUrl && <p><a href={continueUrl}>Continuar con acceso protegido</a></p>}</div>}
      <button className="button primary full" disabled={busy}>{busy ? 'Procesando…' : register ? 'Crear mi cuenta' : 'Ingresar a mi espacio'}<ArrowRight size={18}/></button>
    </form>}
    <p className="switch">{register ? '¿Ya tienes una cuenta?' : '¿Aún no eres parte?'} <button className="text-button" onClick={() => navigate(register ? 'login' : 'register')}>{register ? 'Inicia sesión' : 'Regístrate'}</button></p><div className="form-footer"><ShieldCheck size={15}/> Acceso administrativo con segundo factor en <a href="/accounts/login/">acceso protegido</a>.</div></div></section>;
}

function Field({ label, ...props }) {
  return <label className="field">{label}<input required {...props}/></label>;
}

function Dashboard({ user, setUser }) {
  const [tab, setTab] = useState('overview');
  const [profile, setProfile] = useState(null), [message, setMessage] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { api('profile/').then(setProfile).catch(err => setError(err.message)); }, []);
  async function save(event) {
    event.preventDefault(); setBusy(true); setMessage(''); setError('');
    try { const result = await api('profile/', { method: 'PATCH', body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))) }); setProfile(result); setUser(result); setMessage('Tu perfil se actualizó correctamente.'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div className="app-layout"><aside className="sidebar"><span className="eyebrow">MI VOLUNTARIADO</span><button className={tab === 'overview' ? 'nav-item active' : 'nav-item'} onClick={() => setTab('overview')}><LayoutDashboard size={18}/>Resumen</button><button className={tab === 'profile' ? 'nav-item active' : 'nav-item'} onClick={() => setTab('profile')}><UserRound size={18}/>Mi perfil</button><div className="sidebar-note"><HeartHandshake size={25}/><strong>Tu aporte importa</strong><p>Completa tus datos para que el equipo pueda conocerte.</p></div><a className="nav-item" href="/accounts/2fa/"><Settings2 size={18}/>Seguridad de cuenta</a></aside><section className="dashboard"><div className="breadcrumb">Mi espacio <ChevronRight size={14}/>{tab === 'overview' ? 'Resumen' : 'Mi perfil'}</div><div className="dashboard-heading"><div><span className="eyebrow">TU ESPACIO EN LA COMUNIDAD</span><h1>Hola, {user.first_name} <span className="wave">✦</span></h1><p>Todo empieza con las ganas de ayudar.</p></div><span className="pill"><Check size={14}/> Correo verificado</span></div>
      {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}
      {tab === 'profile' ? <section className="panel profile-panel"><h2>Tu información</h2><p>Mantén tus datos actualizados para facilitar la coordinación.</p>{profile && <form onSubmit={save}><div className="form-row"><Field label="Nombre" name="first_name" defaultValue={profile.first_name} maxLength={80}/><Field label="Apellido" name="last_name" defaultValue={profile.last_name} maxLength={80}/></div><label className="field">Teléfono<input name="phone" autoComplete="tel" placeholder="+56 9 1234 5678" defaultValue={profile.phone} maxLength={20}/></label><label className="field">Comuna<input name="commune" defaultValue={profile.commune} maxLength={80}/></label><button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar cambios'}<Check size={17}/></button></form>}</section> : <><div className="welcome-banner"><div><span className="eyebrow">EL PRIMER PASO YA LO DISTE</span><h2>Queremos conocerte un poco más.</h2><p>Agrega tu teléfono y comuna para facilitar el contacto del equipo.</p><button className="button primary" onClick={() => setTab('profile')}>Completar mi perfil <ArrowRight size={17}/></button></div><HeartHandshake className="banner-icon" size={105} strokeWidth={1}/></div><div className="dashboard-cards"><InfoCard icon={<UserRound/>} title="Tu perfil" value={profile?.phone && profile?.commune ? 'Datos de contacto completos' : 'Por completar'} text="Puedes actualizar tu información cuando lo necesites."/><InfoCard icon={<Mail/>} title="Tu cuenta" value="Correo verificado" text="Tu correo es el medio de acceso a la plataforma."/><InfoCard icon={<MapPin/>} title="Tu comunidad" value={profile?.commune || 'Agrega tu comuna'} text="Usaremos una ubicación aproximada para coordinar."/></div><section className="panel"><div className="panel-heading"><h2>Lo que viene</h2><span className="tag">En desarrollo</span></div><div className="upcoming"><CalendarDays size={32}/><div><h3>Estamos preparando las oportunidades</h3><p>La gestión de actividades, disponibilidad y documentos se incorporará en los próximos módulos.</p></div></div></section><div className="roadmap-note"><FileCheck2 size={18}/><p>Esta primera versión permite registro, verificación, acceso y edición de perfil. No muestra actividades ni métricas ficticias.</p></div></>}
    </section></div>;
}

function InfoCard({ icon, title, value, text }) { return <article className="panel info-card"><div className="info-label"><span>{title}</span>{icon}</div><h3>{value}</h3><p>{text}</p></article>; }

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);
