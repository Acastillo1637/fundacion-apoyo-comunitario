import { test } from 'node:test';
import assert from 'node:assert/strict';
import { coversWindow, toggleWindow } from './volunteers/availability-grid.js';

const slot = (start_time, end_time, weekday = 0) => ({ weekday, start_time, end_time });

test('la matriz no confunde un hueco horario con disponibilidad completa', () => {
  assert.equal(coversWindow([slot('08:00', '10:00'), slot('11:00', '13:00')], 0, '08:00', '13:00'), false);
  assert.equal(coversWindow([slot('08:00', '10:00'), slot('10:00', '13:00')], 0, '08:00', '13:00'), true);
});

test('activar una franja conserva y une los horarios personalizados contiguos', () => {
  assert.deepEqual(toggleWindow([slot('09:00', '14:00')], 0, '08:00', '13:00'), [slot('08:00', '14:00')]);
});

test('desactivar una franja conserva la disponibilidad de ambos extremos', () => {
  assert.deepEqual(toggleWindow([slot('08:00', '22:00')], 0, '13:00', '18:00'), [slot('08:00', '13:00'), slot('18:00', '22:00')]);
});

test('los cambios en la matriz no modifican otros días ni el arreglo original', () => {
  const original = [slot('08:00', '13:00'), slot('09:00', '12:00', 1)];
  const result = toggleWindow(original, 0, '08:00', '13:00');
  assert.deepEqual(result, [slot('09:00', '12:00', 1)]);
  assert.equal(original.length, 2);
});
