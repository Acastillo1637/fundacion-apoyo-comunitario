export default function WhatsAppPhoneField({ name = 'phone', value, defaultValue, onChange }) {
  const national = phone => typeof phone === 'string' && /^[+]?569[0-9]{8}$/.test(phone) ? phone.slice(-9) : phone;
  return <label className="field">Celular de WhatsApp (Chile) — obligatorio
    <input name={name} type="tel" required autoComplete="tel" inputMode="tel" maxLength={12}
      pattern="(?:9[0-9]{8}|[+]?569[0-9]{8})" placeholder="912345678"
      value={national(value)} defaultValue={national(defaultValue)} onChange={onChange}/>
    <small>Ingresa los 9 dígitos de tu celular, comenzando con 9. Agregamos +56 automáticamente.</small>
  </label>;
}
