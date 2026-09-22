import { dayKey } from "./service.js";
// Civil-date arithmetic uses UTC solely as a calendar, never as appointment timezone.
export const civilDate = (date) => new Date(`${date}T12:00:00Z`);
const key = (date) => date.toISOString().slice(0, 10);
export function shiftMonth(month, offset) {
  const date = civilDate(`${month}-01`);
  date.setUTCMonth(date.getUTCMonth() + offset);
  return key(date).slice(0, 7);
}
export function monthDays(month) {
  const first = civilDate(`${month}-01`);
  const last = civilDate(`${shiftMonth(month, 1)}-01`);
  last.setUTCDate(0);
  first.setUTCDate(first.getUTCDate() - ((first.getUTCDay() + 6) % 7));
  last.setUTCDate(last.getUTCDate() + ((7 - last.getUTCDay()) % 7));
  const days = [];
  for (
    const date = new Date(first);
    date <= last;
    date.setUTCDate(date.getUTCDate() + 1)
  )
    days.push(key(date));
  return days;
}
export function groupEvents(rows) {
  const groups = {};
  for (const row of [...rows].sort(
    (a, b) => Date.parse(a.startsAt) - Date.parse(b.startsAt),
  )) {
    (groups[dayKey(row.startsAt)] ||= []).push(row);
  }
  return groups;
}
export function appointmentState(row, now = Date.now()) {
  if (row.status === "cancelled" || row.status === "completed")
    return row.status;
  if (Date.parse(row.startsAt) < now) return "past";
  return row.status === "scheduled" ? "upcoming" : "unknown";
}
