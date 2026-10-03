/** Deterministic appointment slots: next business days, 09:00-15:00, 4 per day. */
export function slotFor(index: number): string {
  const d = new Date();
  d.setUTCHours(0, 0, 0, 0);
  let days = 1 + Math.floor(index / 4);
  while (days > 0) {
    d.setUTCDate(d.getUTCDate() + 1);
    if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) days--;
  }
  const hour = 9 + (index % 4) * 2;
  return `${d.toISOString().slice(0, 10)} ${String(hour).padStart(2, "0")}:00`;
}
