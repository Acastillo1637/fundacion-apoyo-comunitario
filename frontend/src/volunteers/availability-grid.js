const minutes = value => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
const time = value => `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;

export function coversWindow(slots, weekday, from, to) {
  const intervals = slots.filter(item => item.weekday === weekday).map(item => [minutes(item.start_time), minutes(item.end_time)]).sort((a, b) => a[0] - b[0]);
  let covered = minutes(from);
  for (const [start, end] of intervals) {
    if (start > covered) break;
    covered = Math.max(covered, end);
  }
  return covered >= minutes(to);
}

export function toggleWindow(slots, weekday, from, to) {
  const start = minutes(from), end = minutes(to);
  const day = slots.filter(item => item.weekday === weekday).map(item => [minutes(item.start_time), minutes(item.end_time)]);
  let intervals;
  if (coversWindow(slots, weekday, from, to)) {
    intervals = day.flatMap(([a, b]) => b <= start || a >= end ? [[a, b]] : [...(a < start ? [[a, start]] : []), ...(b > end ? [[end, b]] : [])]);
  } else intervals = [...day, [start, end]];
  intervals.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [a, b] of intervals) {
    const previous = merged.at(-1);
    if (previous && a <= previous[1]) previous[1] = Math.max(previous[1], b);
    else merged.push([a, b]);
  }
  return [...slots.filter(item => item.weekday !== weekday), ...merged.map(([a, b]) => ({ weekday, start_time: time(a), end_time: time(b) }))].sort((a, b) => a.weekday - b.weekday || a.start_time.localeCompare(b.start_time));
}
