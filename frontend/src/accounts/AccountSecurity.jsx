import { useEffect, useState } from 'react';
import { api } from '../api';
import { KeyRound, Mail, ShieldCheck } from 'lucide-react';

export default function AccountSecurity({ onUserChanged, confirmationToken, clearConfirmationURL }) {
  const [state,setState]=useState(null),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const [setup,setSetup]=useState(null),[codes,setCodes]=useState(null),[token,setToken]=useState(confirmationToken || '');
  useEffect(()=>{let active=true;api('security/',{cache:'no-store'}).then(value=>{if(active)setState(value);}).catch(err=>{if(active)setError(err.message);});return()=>{active=false;};},[]);
  useEffect(()=>{if(confirmationToken){setToken(confirmationToken);clearConfirmationURL?.();}},[confirmationToken]);
  async function submit(event,action){
    event.preventDefault();const form=event.currentTarget;
    const values=Object.fromEntries(new FormData(form));
    if(action==='password'){
      if(values.new_password!==values.password_confirm){setError('Las contraseñas nuevas deben coincidir.');return;}
      delete values.password_confirm;
    }
    if(['totp_disable','recovery_generate'].includes(action)&&!window.confirm(action==='totp_disable'?'¿Desactivar 2FA y retirar sus códigos de recuperación? Se cerrarán otras sesiones.':'¿Generar códigos nuevos? Los anteriores dejarán de funcionar.'))return;
    setBusy(true);setError('');setMessage('');setCodes(null);
    try{
      const result=await api('security/action/',{method:'POST',body:JSON.stringify({action,...values,...(action==='email_confirm'?{token}: {})})});
      if(result.state)setState(result.state);if(result.user)onUserChanged?.(result.user);
      setMessage(result.detail || 'Operación completada.');
      if(result.secret)setSetup({secret:result.secret,qr:result.qr});
      if(result.codes)setCodes(result.codes);
      if(['totp_activate','totp_disable','totp_cancel','password','email_confirm'].includes(action))setSetup(null);
      if(action==='email_confirm')setToken('');
      form.reset();
    }catch(err){setError(err.message);}finally{setBusy(false);}
  }
  const credentials=<><label className="field">Contraseña actual<input name="current_password" type="password" autoComplete="current-password" maxLength={256} required/></label>{state?.mfa_enabled&&<label className="field">Código 2FA o de recuperación<input name="mfa_code" autoComplete="one-time-code" maxLength={20} required/></label>}</>;
  function form(action,children){return <form onSubmit={event=>submit(event,action)}><fieldset className="form-fieldset" disabled={busy}>{children}</fieldset></form>;}
  return <div className="account-security stack">{error&&<p className="error" role="alert">{error}</p>}{message&&<p className="success" role="status">{message}</p>}
    {!state&&!error&&<section className="panel" role="status">Cargando el estado de seguridad de tu cuenta…</section>}
    {state&&<><section className="panel"><h2><ShieldCheck/>Estado de seguridad</h2><p>Correo: <strong>{state.email}</strong> · {state.email_verified?'Propiedad comprobada':'Sin comprobación de propiedad'}</p><p>Segundo factor: <strong>{state.totp_enabled?'Aplicación activa':'Sin aplicación configurada'}</strong> · Códigos disponibles: {state.recovery_remaining}</p><p>Las operaciones sensibles requieren tu contraseña y, si tienes 2FA, un código nuevo. No compartas las claves ni los códigos.</p></section>
    {token&&<section className="panel"><h2>Confirmar correo de cuenta</h2><p>El enlace no cambia tu correo automáticamente. Confirma con las credenciales de esta cuenta.</p>{form('email_confirm',<>{credentials}<button className="button primary">Confirmar el correo del enlace</button></>)}</section>}
    <div className="security-grid"><section className="panel"><h2><KeyRound/>Cambiar contraseña</h2>{form('password',<>{credentials}<label className="field">Contraseña nueva<input name="new_password" type="password" autoComplete="new-password" minLength={12} maxLength={256} required/></label><label className="field">Repite la contraseña nueva<input name="password_confirm" type="password" autoComplete="new-password" minLength={12} maxLength={256} required/></label><button className="button primary">Actualizar contraseña</button></>)}</section>
    <section className="panel"><h2><Mail/>Cambiar o comprobar correo</h2><p>Se envía un enlace al buzón indicado. Tu cuenta conserva el correo actual hasta la confirmación.</p>{state.pending_email&&<p className="notice">Solicitud pendiente: {state.pending_email}</p>}{form('email_request',<><label className="field">Correo que quieres usar<input name="new_email" type="email" defaultValue={state.email} maxLength={254} required/></label>{credentials}<button className="button primary">Solicitar enlace de confirmación</button></>)}</section></div>
    <section className="panel"><h2><ShieldCheck/>Aplicación de autenticación (2FA)</h2>{!state.email_verified&&<p className="notice">El acceso normal no requiere verificar correo. Para activar 2FA, primero comprueba tu buzón desde la opción anterior: así se protege la recuperación de la cuenta.</p>}
    {!state.totp_enabled&&!setup&&form('totp_setup',<>{credentials}<button className="button primary" disabled={!state.email_verified}>Configurar aplicación 2FA</button></>)}
    {setup&&<div className="totp-setup"><img src={setup.qr} alt="QR privado para configurar tu aplicación de autenticación" width={220} height={220}/><p>Clave de configuración manual, solo para tu aplicación:</p><code className="security-secret">{setup.secret}</code><p>La configuración vence en cinco minutos. No guardes este QR en dispositivos compartidos.</p>{form('totp_activate',<>{credentials}<label className="field">Código de la aplicación nueva<input name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={8} required/></label><button className="button primary">Activar 2FA</button></>)}{form('totp_cancel',<button className="button secondary">Descartar configuración</button>)}</div>}
    {state.totp_enabled&&form('totp_disable',<>{credentials}<button className="button secondary">Desactivar 2FA</button></>)}
    </section>
    {state.totp_enabled&&<section className="panel"><h2>Códigos de recuperación</h2><p>Cada código sirve una vez. La lista solo se muestra cuando la solicitas y tras comprobar tus credenciales.</p>{form('recovery_view',<>{credentials}<button className="button secondary">Mostrar códigos disponibles</button></>)}{form('recovery_generate',<>{credentials}<button className="button secondary">Generar códigos nuevos</button></>)}
      {codes&&<section className="recovery-codes"><p>Guárdalos ahora en un lugar seguro. No volverán a mostrarse.</p><ul>{codes.map(code=><li key={code}><code>{code}</code></li>)}</ul><button className="button secondary" onClick={()=>setCodes(null)}>Ocultar códigos</button></section>}
    </section>}</>}
  </div>;
}
