// Daily check of document expiry dates; sends a Telegram message when renewal is due.
// Input comes from repository secrets so personal data never lands in the public repo.
const { DOCS_JSON, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, FORCE_SEND } = process.env;
if (!DOCS_JSON || !TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
  console.log('Secrets DOCS_JSON / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set — skipping.');
  process.exit(0);
}

const DAY = 86400000;
const parseDate = s => { const [y, m, d] = s.split('-').map(Number); return Date.UTC(y, m - 1, d); };
const fmt = t => new Date(t).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
function subtractLead(t, value, unit) {
  const d = new Date(t);
  if (unit === 'm') {
    const day = d.getUTCDate();
    d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() - value);
    d.setUTCDate(Math.min(day, new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()));
  } else d.setUTCDate(d.getUTCDate() - value * (unit === 'w' ? 7 : 1));
  return d.getTime();
}
function plural(n, one, few, many) {
  const a = Math.abs(n) % 100, b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  return b === 1 ? one : many;
}
const days = n => `${n} ${plural(n, 'день', 'дня', 'дней')}`;

// Today in Moscow time (the job runs on a UTC schedule).
const now = new Date(Date.now() + 3 * 3600 * 1000);
const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
const isMonday = now.getUTCDay() === 1;
const force = FORCE_SEND === 'true';

const lines = [];
for (const doc of JSON.parse(DOCS_JSON)) {
  const exp = parseDate(doc.expires);
  const start = subtractLead(exp, Number(doc.leadValue) || 0, doc.leadUnit);
  if (today < start) continue;
  const left = Math.round((exp - today) / DAY);
  // First day of the window, milestones, then a weekly Monday digest — not daily spam.
  const due = force || today === start || [60, 30, 14, 7, 3, 1, 0].includes(left) || isMonday;
  if (!due) continue;
  const name = doc.name.replace(/[<>&]/g, '');
  if (left < 0) lines.push(`🔴 <b>${name}</b> — истёк ${fmt(exp)} (${days(-left)} назад)`);
  else if (left === 0) lines.push(`🔴 <b>${name}</b> — истекает сегодня!`);
  else lines.push(`🟠 <b>${name}</b> — действует до ${fmt(exp)}, осталось ${days(left)}`);
}

if (!lines.length) { console.log('Nothing to report today.'); process.exit(0); }

const text = `📄 <b>Пора обновить документы</b>\n\n${lines.join('\n')}`;
const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text, parse_mode: 'HTML' }),
});
if (!res.ok) { console.error('Telegram error:', res.status, await res.text()); process.exit(1); }
console.log(`Sent ${lines.length} reminder(s).`);
