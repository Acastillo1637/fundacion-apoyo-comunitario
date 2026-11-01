import { useEffect, useState } from 'react';
import { ArrowLeft, Check, HeartHandshake, Send } from 'lucide-react';
import { api } from '../api';

export default function PublicRequest({ navigate, requester }) {
  const [options, setOptions] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [type, setType] = useState('person');
  const [submissionId] = useState(() => crypto.randomUUID());
  useEffect(() => { api('activities/public-options/').then(setOptions).catch(err => setError(err.message)); }, []);

  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = Object.fromEntries(form);
    body.submission_id = submissionId;
    body.skills = form.getAll('skills').map(Number);
    body.quantity = Number(form.get('quantity'));
    body.privacy = form.has('privacy');
    setBusy(true); setError('');
    try { setMessage((await api(requester ? 'requester/requests/' : 'activities/requests/', { method: 'POST', body: JSON.stringify(body) })).detail); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <section className="wrap request-page">
    <button className="text-button" onClick={() => navigate('home')}><ArrowLeft size={16}/> {requester ? 'Volver a mis solicitudes' : 'Volver al inicio'}</button>
    {!requester && <div className="notice"><p>¿Representas a una empresa o institución? Crea una cuenta de solicitante para guardar tus datos y seguir tus solicitudes.</p><button className="button secondary" onClick={() => navigate('register-requester')}>Crear cuenta de solicitante</button></div>}
    <div className="request-header"><span className="eyebrow">JUNTOS PODEMOS HACER MÁS</span><h1>Solicita apoyo de voluntariado</h1><p>Cuéntanos tu necesidad. El equipo revisará los antecedentes y evaluará cómo ayudar; enviar el formulario no garantiza la aprobación.</p></div>
    <div className="panel public-request-panel">
      {error && <p role="alert" className="error">{error}</p>}
      {message ? <div role="status" className="success"><Check size={26}/><h2>Recibimos tu solicitud</h2><p>{message}</p>{!requester && options?.console_email && <p><strong>Entorno de desarrollo:</strong> el mensaje aparece en la terminal de Django, no llega a Gmail. Copia el enlace completo, incluido lo que viene después de <code>#confirm-request=</code>.</p>}<button className="button secondary" onClick={() => navigate('home')}>{requester ? 'Ver mis solicitudes' : 'Volver al inicio'}</button></div> : !options ? <p role="status">Cargando formulario…</p> : <form onSubmit={submit}><fieldset className="form-fieldset" disabled={busy}>
        {requester ? <div className="notice">Solicitas como <strong>{requester.organization || `${requester.first_name} ${requester.last_name}`}</strong>. Usaremos los datos de tu perfil y tu correo verificado.</div> : <>
        <h2><HeartHandshake size={22}/> ¿Quién solicita el apoyo?</h2>
        <div className="form-row"><label className="field">Tipo de solicitante<select name="requester_type" value={type} onChange={event => setType(event.target.value)}><option value="person">Persona natural</option><option value="company">Empresa</option><option value="institution">Institución</option></select></label><label className="field">Nombre de contacto<input name="contact_name" autoComplete="name" maxLength={120} required/></label></div>
        <label className="field">Organización {type === 'person' ? '(opcional)' : ''}<input name="organization" maxLength={150} required={type !== 'person'}/></label>
        <div className="form-row"><label className="field">Correo electrónico<input type="email" name="email" autoComplete="email" maxLength={254} required/></label><label className="field">Teléfono<input name="phone" type="tel" autoComplete="tel" maxLength={20} required/></label></div>
        </>}
        <h2 className="form-section-title">¿Qué necesitas?</h2>
        <label className="field">Descripción de la necesidad<textarea name="description" minLength={20} maxLength={3000} rows={5} required/></label>
        <p className="help">No incluyas nombres, documentos ni información sensible de beneficiarios.</p>
        <fieldset className="catalog-section"><legend>Habilidades necesarias (opcional)</legend><div className="request-skills">{options.skills.map(skill => <label className="checkbox" key={skill.id}><input type="checkbox" name="skills" value={skill.id}/>{skill.name}</label>)}</div>{options.skills.length === 0 && <p className="help">El catálogo todavía no tiene habilidades publicadas.</p>}</fieldset>
        <div className="form-row"><label className="field">Cantidad de voluntarios<input name="quantity" type="number" min={1} max={500} required/></label><label className="field">Fecha<input type="date" name="date" required/></label></div>
        <div className="form-row"><label className="field">Hora de inicio<input type="time" name="start_time" step={60} required/></label><label className="field">Hora de término<input type="time" name="end_time" step={60} required/></label></div>
        <p className="help">Horarios de Santiago de Chile. Inicio y término dentro del mismo día.</p>
        <label className="field">Dirección de la actividad<input name="address" maxLength={250} required/></label>
        <label className="field">Comuna<input name="commune" maxLength={80} required/></label>
        <label className="field">Observaciones (opcional)<textarea name="observations" maxLength={1500} rows={3}/></label>
        <div className="honeypot" aria-hidden="true"><label>Deja este campo vacío<input name="website" tabIndex={-1} autoComplete="off"/></label></div>
        <label className="checkbox"><input name="privacy" type="checkbox" required/>Acepto que la fundación use estos datos para evaluar y coordinar mi solicitud.</label>
        <p className="help">Versión de desarrollo: usa datos ficticios. El aviso institucional definitivo está pendiente.</p>
        {!requester && options.console_email && <div className="notice"><p>En desarrollo, el enlace para confirmar el correo se imprime en la terminal donde ejecutas Django.</p></div>}
        <button className="button primary" disabled={busy}>{busy ? 'Enviando…' : 'Enviar solicitud'}<Send size={17}/></button>
      </fieldset></form>}
    </div>
  </section>;
}

export function RequestVerification({ ready, navigate }) {
  const [token] = useState(() => window.location.hash.startsWith('#confirm-request=') ? window.location.hash.slice('#confirm-request='.length) : '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function confirm() {
    setBusy(true); setError('');
    try {
      setMessage((await api('activities/request-verification/', { method: 'POST', body: JSON.stringify({ token }) })).detail);
      history.replaceState(null, '', window.location.pathname + window.location.search);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="wrap request-page"><div className="panel verification-panel"><h1>Confirma tu solicitud</h1><p>Confirma tu correo para que la fundación pueda evaluar la necesidad. Este paso no aprueba la actividad.</p>{error && <p className="error" role="alert">{error}</p>}{message ? <p className="success" role="status">{message}</p> : <button className="button primary" disabled={!ready || busy || !token} onClick={confirm}>{busy ? 'Confirmando…' : 'Confirmar mi correo'}</button>}<p><button className="text-button" onClick={() => navigate('home')}>Volver al inicio</button></p></div></section>;
}
