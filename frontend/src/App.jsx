import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { api, clearPrivateData } from './api';
import Dashboard from './volunteers/Dashboard';
import PublicRequest, { RequestVerification } from './activities/PublicRequest';
import Auth from './design/Auth';
import Landing from './design/Landing';
import { FoundationLogo, slogan } from './design/Brand';
import { PrivacyNotice } from './accounts/PrivacyRequests';
import AccountMenu from './accounts/AccountMenu';
import { normalizePath, publicPaths, resolveWorkspace, safeReturnTo, sectionURL } from './routing';

export function SessionScreen({ offline=false, signingOut=false, retry }) {
  return <main className="session-screen" role={offline?'alert':'status'} aria-live="polite"><FoundationLogo large/><h1>Fundación Apoyo Comunitario</h1><p>{slogan}</p><p>{offline?'No hay conexión con el servidor. Tu sección se conserva en la URL.':signingOut?'Cerrando tu sesión…':'Comprobando tu sesión…'}</p>{offline&&<button className="button primary" onClick={retry}>Reintentar conexión</button>}</main>;
}

export default function App() {
  const location=useLocation(), routerNavigate=useNavigate();
  const [session,setSession]=useState(null),[status,setStatus]=useState('loading'),[retry,setRetry]=useState(0);
  const [error,setError]=useState(''),[menu,setMenu]=useState(false);
  useEffect(()=>{
    let active=true;
    setStatus('loading');
    api('session/').then(data=>{if(active){setSession(data);setStatus('ready');}}).catch(()=>{if(active)setStatus('offline');});
    return()=>{active=false;};
  },[retry]);
  useEffect(()=>{setMenu(false);setError('');},[location.key]);
  useEffect(()=>{
    const restored=event=>{if(event.persisted){clearPrivateData();setSession(null);setStatus('loading');setRetry(value=>value+1);}};
    // Clear private DOM before the browser can freeze this document in BFCache.
    const leaving=()=>flushSync(()=>{clearPrivateData();setSession(null);setStatus('loading');});
    window.addEventListener('pageshow',restored);window.addEventListener('pagehide',leaving);
    return()=>{window.removeEventListener('pageshow',restored);window.removeEventListener('pagehide',leaving);};
  },[]);
  function navigate(next){
    const path=publicPaths[next] || next;
    routerNavigate(path,{state:next==='login-registered'?{registered:true}:null});
    setMenu(false);setError('');window.scrollTo(0,0);
  }
  async function signOut(){
    setStatus('logging-out');setError('');
    try{
      await api('logout/',{method:'POST'});
      clearPrivateData();setSession(old=>({...old,user:null}));setStatus('ready');
      routerNavigate('/iniciar-sesion',{replace:true,state:null});
    }catch(err){setStatus('ready');setError('No se pudo cerrar la sesión en el servidor. Vuelve a intentarlo.');}
  }
  if(status!=='ready')return <SessionScreen offline={status==='offline'} signingOut={status==='logging-out'} retry={()=>setRetry(value=>value+1)}/>;
  const pathname=normalizePath(location.pathname), user=session?.user;
  const route=resolveWorkspace(user,pathname,location.search);
  const publicView=Object.entries(publicPaths).find(([,path])=>path===pathname)?.[0];
  if(pathname!==location.pathname)return <Navigate replace to={pathname+location.search+location.hash} state={location.state}/>;
  if(location.hash.startsWith('#confirm-request=')&&pathname!=='/confirmar-solicitud')return <Navigate replace to={'/confirmar-solicitud'+location.hash}/>;
  if(route&&!user)return <Navigate replace to="/iniciar-sesion" state={{from:pathname+location.search}}/>;
  if(user&&['login','register','register-requester'].includes(publicView))return <Navigate replace to={safeReturnTo(user,location.state?.from)}/>;
  if(user?.available_portals?.includes('requester')&&publicView==='request')return <Navigate replace to="/nueva-solicitud"/>;
  const workspace=Boolean(route?.allowed), brand=session?.foundation_name || 'Fundación Apoyo Comunitario';
  const onUserChanged=updated=>setSession(old=>({...old,user:updated}));
  return <><a className="skip" href="#main">Saltar al contenido</a>
    {!workspace&&<header className="header"><button className="brand" onClick={()=>navigate('home')}><FoundationLogo/><span>{brand}<small>{slogan}</small></span></button>
      <button className="mobile-menu icon-btn" aria-label={menu?'Cerrar menú':'Abrir menú'} aria-expanded={menu} onClick={()=>setMenu(!menu)}>{menu?<X/>:<Menu/>}</button>
      <nav aria-label="Navegación principal" className={menu?'top-nav open':'top-nav'}><button className="text-button" onClick={()=>navigate('request')}>Solicitar apoyo</button>
        {user?<><button className="text-button" onClick={()=>navigate('/dashboard')}>Mi espacio</button><AccountMenu user={user} role={(user.roles||[]).join(' · ') || 'Cuenta'} onProfile={()=>navigate('/mi-cuenta')} onSecurity={()=>navigate('/seguridad')} onSignOut={signOut}/></>:<><button className="text-button" onClick={()=>navigate('home')}>Nuestra comunidad</button><button className="text-button" onClick={()=>navigate('login')}>Iniciar sesión</button><button className="button primary small" onClick={()=>navigate('register')}>Ser voluntario<ArrowUpRight size={16}/></button></>}
      </nav></header>}
    {error&&<p className="error global-error" role="alert">{error}</p>}
    <main id="main" className={workspace?'workspace-main':'public-main'}>
      {route&&!route.allowed&&<section className="wrap panel"><h1>Acceso no autorizado</h1><p>Tu cuenta no tiene permisos para esta sección o espacio.</p><button className="button primary" onClick={()=>navigate('/dashboard')}>Ir a mi dashboard</button></section>}
      {workspace&&<Dashboard key={user.id} user={user} setUser={onUserChanged} foundation={brand} onPublic={()=>navigate('home')} onSignOut={signOut}
        route={route} onRoute={(tab,portal,eventId)=>navigate(sectionURL(tab,portal,eventId))}
        confirmationToken={pathname==='/seguridad/verificar-correo'?new URLSearchParams(location.search).get('token'):null}
        clearConfirmationURL={()=>routerNavigate(sectionURL('security',route.portal),{replace:true})}/>}
      {publicView==='home'&&<Landing brand={brand} ready navigate={navigate}/>}
      {publicView==='privacy'&&<PrivacyNotice retentionNotice={session?.retention_notice} development={session?.development}/>}
      {['login','register','register-requester'].includes(publicView)&&!user&&<Auth key={publicView} mode={publicView==='login'?'login':'register'} notice={location.state?.registered?'Cuenta creada correctamente. Ya puedes iniciar sesión.':''}
        initialType={publicView==='register-requester'?'requester':'volunteer'} brand={brand} navigate={navigate}
        onLogin={updated=>{onUserChanged(updated);routerNavigate(safeReturnTo(updated,location.state?.from),{replace:true,state:null});}}/>}
      {publicView==='request'&&<PublicRequest navigate={navigate}/>}
      {publicView==='verify-request'&&<RequestVerification ready navigate={navigate}/>}
      {!route&&!publicView&&<section className="wrap panel"><h1>Página no encontrada</h1><p>Revisa la dirección o utiliza el menú para continuar.</p><button className="button primary" onClick={()=>navigate(user?'/dashboard':'home')}>Volver</button></section>}
    </main>
    <footer className={workspace?'workspace-footer':'public-footer'}><span>© {new Date().getFullYear()} {brand}</span><span>{slogan}</span></footer>
  </>;
}
