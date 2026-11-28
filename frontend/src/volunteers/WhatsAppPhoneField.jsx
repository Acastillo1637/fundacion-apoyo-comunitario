export default function WhatsAppPhoneField({ name = 'phone', value, defaultValue, onChange }) {
  const national = phone => typeof phone === 'string' && /^[+]?569[0-9]{8}$/.test(phone) ? phone.slice(-9) : phone;
  return <label className="field whatsapp-phone-field"><span>Celular</span>
    <span className="chilean-phone-control"><span className="chilean-phone-prefix" aria-hidden="true">+56</span>
      <input name={name} aria-label="Celular" type="tel" required autoComplete="tel-national" inputMode="numeric" maxLength={9}
        pattern="9[0-9]{8}" placeholder="912345678"
        value={national(value)} defaultValue={national(defaultValue)} onChange={onChange}/>
    </span>
  </label>;
}
