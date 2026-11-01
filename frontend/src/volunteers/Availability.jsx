import { useEffect, useState } from 'react';
import { CalendarDays, Check, Clock3, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '../api';

const days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

export default function Availability() {
  const [schedule, setSchedule] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [exceptionDate, setExceptionDate] = useState('');

  async function load() {
    setBusy(true);
    setError('');
    setMessage('');
    try { setSchedule(await api('volunteer/availability/')); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);

  function changeSlot(index, field, value) {
    setMessage('');
    setSchedule(current => ({
      ...current,
      slots: current.slots.map((slot, position) => position === index ? { ...slot, [field]: value } : slot),
    }));
  }

  function addException() {
    if (!exceptionDate) return;
    if (schedule.unavailable_dates.includes(exceptionDate)) {
      setError('Esa fecha ya está registrada.');
      return;
    }
    setError('');
    setMessage('');
    setSchedule(current => ({ ...current, unavailable_dates: [...current.unavailable_dates, exceptionDate].sort() }));
    setExceptionDate('');
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await api('volunteer/availability/', {
        method: 'PUT',
        body: JSON.stringify({ revision: schedule.revision, slots: schedule.slots, unavailable_dates: schedule.unavailable_dates }),
      });
      setSchedule(result);
      setMessage('Tu disponibilidad se guardó correctamente.');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <section className="panel availability-panel" aria-busy={busy}>
    <div className="panel-heading"><h2>Tu disponibilidad</h2><button className="text-button" type="button" disabled={busy} onClick={load}><RefreshCw size={15}/> Recargar</button></div>
    <p className="section-description">Indica los días y horarios en los que puedes participar. Guardar una franja no confirma tu asistencia a ninguna actividad.</p>
    <div className="notice"><Clock3 size={19}/><p>Horarios de Santiago de Chile ({schedule?.timezone || 'America/Santiago'}). Cada franja debe comenzar y terminar dentro del mismo día. Tú evalúas si puedes llegar a la actividad.</p></div>
    {busy && !schedule && <p role="status">Cargando tu disponibilidad…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status" className="success">{message}</p>}
    {schedule && <form onSubmit={save}><fieldset className="form-fieldset" disabled={busy}>
      <div className="schedule-heading"><h3><CalendarDays size={18}/> Semana habitual</h3><span className="help">{schedule.slots.length}/42 franjas</span></div>
      {schedule.slots.length === 0 && <div className="empty-state"><p>Aún no tienes horarios registrados. Agrega una franja para comenzar.</p></div>}
      <div className="schedule-list">{schedule.slots.map((slot, index) => <div className="schedule-row" key={index}>
        <label className="field">Día<select value={slot.weekday} onChange={event => changeSlot(index, 'weekday', Number(event.target.value))}>{days.map((day, weekday) => <option value={weekday} key={day}>{day}</option>)}</select></label>
        <label className="field">Desde<input type="time" step="60" required value={slot.start_time} onChange={event => changeSlot(index, 'start_time', event.target.value)}/></label>
        <label className="field">Hasta<input type="time" step="60" required value={slot.end_time} onChange={event => changeSlot(index, 'end_time', event.target.value)}/></label>
        <button className="icon-btn remove-button" type="button" aria-label={`Quitar franja ${index + 1}, ${days[slot.weekday]}`} onClick={() => { setMessage(''); setSchedule(current => ({ ...current, slots: current.slots.filter((_, position) => position !== index) })); }}><Trash2 size={18}/></button>
      </div>)}</div>
      <button className="button secondary" type="button" disabled={schedule.slots.length >= 42} onClick={() => { setMessage(''); setSchedule(current => ({ ...current, slots: [...current.slots, { weekday: 0, start_time: '09:00', end_time: '13:00' }] })); }}><Plus size={17}/> Agregar franja</button>
      <section className="exceptions-section"><h3>Fechas en las que no puedes participar</h3><p className="help">Estas fechas bloquean el día completo, aunque coincida con tu semana habitual. No necesitas indicar el motivo.</p>
        <div className="exception-input"><label className="field">Fecha<input type="date" value={exceptionDate} onChange={event => setExceptionDate(event.target.value)}/></label><button className="button secondary" type="button" disabled={!exceptionDate || schedule.unavailable_dates.length >= 60} onClick={addException}><Plus size={17}/> Agregar fecha</button></div>
        {schedule.unavailable_dates.length === 0 ? <p className="help">Sin excepciones registradas.</p> : <ul className="date-list">{schedule.unavailable_dates.map(date => <li key={date}><time dateTime={date}>{date.split('-').reverse().join('/')}</time><button className="icon-btn remove-button" type="button" aria-label={`Quitar fecha ${date}`} onClick={() => { setMessage(''); setSchedule(current => ({ ...current, unavailable_dates: current.unavailable_dates.filter(item => item !== date) })); }}><XIcon/></button></li>)}</ul>}
      </section>
      <div className="form-actions"><span className="help">Los cambios se aplican al guardar. Quitar todas las franjas deja tu disponibilidad vacía.</span><button className="button primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar disponibilidad'}<Check size={17}/></button></div>
    </fieldset></form>}
  </section>;
}

function XIcon() { return <span aria-hidden="true">×</span>; }
