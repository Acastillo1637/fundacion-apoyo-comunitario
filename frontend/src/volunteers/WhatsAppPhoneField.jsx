export default function WhatsAppPhoneField({ name = 'phone', value, defaultValue, onChange }) {
  const national = phone => typeof phone === 'string' && /^[+]?569[0-9]{8}$/.test(phone) ? phone.slice(-9) : phone;
  function digitsOnly(event) {
    event.currentTarget.value = event.currentTarget.value.replace(/[^0-9]/g, '').slice(0, 9);
  }
  function updateDigits(event) {
    digitsOnly(event);
    onChange?.(event);
  }
  function pasteDigits(event) {
    event.preventDefault();
    const input = event.currentTarget;
    const digits = event.clipboardData.getData('text').replace(/[^0-9]/g, '');
    const start = input.selectionStart ?? input.value.length;
    const end = input.selectionEnd ?? start;
    const available = Math.max(0, 9 - (input.value.length - (end - start)));
    input.setRangeText(digits.slice(0, available), start, end, 'end');
    onChange?.(event);
  }
  return <label className="field whatsapp-phone-field"><span>Celular</span>
    <span className="chilean-phone-control"><span className="chilean-phone-prefix" aria-hidden="true">+56</span>
      <input name={name} aria-label="Celular" type="tel" required autoComplete="tel-national" inputMode="numeric" maxLength={9}
        pattern="9[0-9]{8}" placeholder="912345678"
        value={national(value)} defaultValue={national(defaultValue)} onInput={updateDigits} onPaste={pasteDigits} onChange={digitsOnly}/>
    </span>
  </label>;
}
