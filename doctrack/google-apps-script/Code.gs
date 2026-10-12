/**
 * Backend for doctrack (https://an-mish.github.io/doctrack/).
 * Stores documents in this Google Sheet, mirrors them to a Google Calendar
 * and sends daily renewal reminders.
 * Setup instructions: doctrack/README.md
 */

// Leave empty when the script is opened from the sheet (Extensions → Apps Script).
// For a standalone script project, put the spreadsheet ID from its URL here.
const SHEET_ID = '';
const SHEET_NAME = 'Документы';
const HEADERS = ['id', 'Тип', 'Название', 'Дата выдачи', 'Действует до', 'Начать обновление за', 'Единица', 'Заметка',
  'Подан на обновление'];
const FIELDS = ['id', 'type', 'name', 'issued', 'expires', 'leadValue', 'leadUnit', 'note', 'submitted'];
const UNITS = { d: 'дней', w: 'недель', m: 'месяцев' };
const DAY = 86400000;
const CALENDAR_NAME = 'Сроки документов';

// Run once from the editor (and again after updating this code): creates the sheet, the access key,
// the calendar and the daily reminder trigger.
function setup() {
  const props = PropertiesService.getScriptProperties();
  if (!SHEET_ID) props.setProperty('SHEET_ID', SpreadsheetApp.getActiveSpreadsheet().getId());
  let key = props.getProperty('API_KEY');
  if (!key) {
    key = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
    props.setProperty('API_KEY', key);
  }
  sheet_();
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'dailyCheck')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('dailyCheck').timeBased().everyDays(1).atHour(9).create();
  syncCalendar_(readDocs_());
  Logger.log('Готово. Ключ доступа для приложения:\n' + key);
}

// Sends a reminder right now for everything in the renewal window — to check that mail works.
function testReminder() {
  dailyCheck(true);
}

// ---------- web API ----------

function doGet() {
  return ContentService.createTextOutput('doctrack backend работает.');
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const req = JSON.parse(e.postData.contents);
    const key = PropertiesService.getScriptProperties().getProperty('API_KEY');
    if (!key || req.key !== key) return json_({ ok: false, error: 'bad_key' });

    lock.waitLock(15000);
    let docs = readDocs_();
    if (req.action === 'upsert') {
      const doc = clean_(req.doc);
      const i = docs.findIndex(d => d.id === doc.id);
      if (i >= 0) docs[i] = doc; else docs.push(doc);
    } else if (req.action === 'delete') {
      docs = docs.filter(d => d.id !== req.id);
    } else if (req.action === 'replace') {
      docs = req.docs.map(clean_);
    } else if (req.action !== 'list') {
      return json_({ ok: false, error: 'unknown_action' });
    }
    if (req.action === 'list') return json_({ ok: true, docs });
    writeDocs_(docs);
    docs = readDocs_();
    try { syncCalendar_(docs); } catch (err) { console.error('Calendar sync failed', err); }
    return json_({ ok: true, docs });
  } catch (err) {
    return json_({ ok: false, error: String(err && err.message || err) });
  } finally {
    lock.releaseLock();
  }
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ---------- sheet storage ----------

function sheet_() {
  const ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID)
    : SpreadsheetApp.getActiveSpreadsheet()
      || SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('SHEET_ID'));
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) sh = ss.insertSheet(SHEET_NAME, 0);
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
    sh.getRange('D:E').setNumberFormat('dd.MM.yyyy');
    sh.hideColumns(1);
  }
  // Sheets created by an older version of this script lack the newer columns.
  const head = sh.getRange(1, 1, 1, HEADERS.length);
  const current = head.getValues()[0];
  if (current.some(v => !v)) {
    head.setValues([HEADERS.map((h, i) => current[i] || h)]).setFontWeight('bold');
    sh.getRange('I:I').setNumberFormat('dd.MM.yyyy');
  }
  return sh;
}

function readDocs_() {
  const sh = sheet_();
  const tz = sh.getParent().getSpreadsheetTimeZone();
  const rows = sh.getLastRow() - 1;
  if (rows < 1) return [];
  const range = sh.getRange(2, 1, rows, FIELDS.length);
  const values = range.getValues();
  let idsAdded = false;
  const docs = [];
  values.forEach(r => {
    if (!r[2] || !r[4]) return; // rows without a name or expiry date are ignored
    if (!r[0]) { r[0] = Utilities.getUuid(); idsAdded = true; } // row typed by hand in the sheet
    const doc = {};
    FIELDS.forEach((f, i) => { doc[f] = r[i]; });
    doc.id = String(doc.id);
    doc.type = String(doc.type || 'Другое');
    doc.name = String(doc.name);
    doc.issued = toISO_(doc.issued, tz);
    doc.expires = toISO_(doc.expires, tz);
    doc.leadValue = Math.max(0, parseInt(doc.leadValue, 10) || 0);
    doc.leadUnit = unitCode_(doc.leadUnit);
    doc.note = String(doc.note || '');
    doc.submitted = toISO_(doc.submitted, tz);
    if (doc.expires) docs.push(doc);
  });
  if (idsAdded) sh.getRange(2, 1, rows, 1).setValues(values.map(r => [r[0]]));
  return docs;
}

function writeDocs_(docs) {
  const sh = sheet_();
  const old = sh.getLastRow() - 1;
  if (old > 0) sh.getRange(2, 1, old, FIELDS.length).clearContent();
  if (!docs.length) return;
  const tz = sh.getParent().getSpreadsheetTimeZone();
  const rows = docs.map(d => [d.id, d.type, d.name, isoToDate_(d.issued, tz), isoToDate_(d.expires, tz),
    d.leadValue, UNITS[d.leadUnit], d.note, isoToDate_(d.submitted, tz)]);
  sh.getRange(2, 1, rows.length, FIELDS.length).setValues(rows);
}

function clean_(d) {
  const iso = /^\d{4}-\d{2}-\d{2}$/;
  if (!d || !d.name || !iso.test(d.expires)) throw new Error('invalid_doc');
  return {
    id: String(d.id || Utilities.getUuid()),
    type: String(d.type || 'Другое'),
    name: String(d.name).slice(0, 200),
    issued: iso.test(d.issued) ? d.issued : '',
    expires: d.expires,
    leadValue: Math.max(0, parseInt(d.leadValue, 10) || 0),
    leadUnit: UNITS[d.leadUnit] ? d.leadUnit : 'd',
    note: String(d.note || '').slice(0, 2000),
    submitted: iso.test(d.submitted) ? d.submitted : '',
  };
}

function toISO_(v, tz) {
  if (v instanceof Date) return Utilities.formatDate(v, tz, 'yyyy-MM-dd');
  const s = String(v || '').trim();
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return s;
  m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  return '';
}

function isoToDate_(s, tz) {
  return s ? Utilities.parseDate(s, tz, 'yyyy-MM-dd') : '';
}

function unitCode_(v) {
  const s = String(v || '').trim().toLowerCase();
  if (UNITS[s]) return s;
  if (s.startsWith('мес')) return 'm';
  if (s.startsWith('нед')) return 'w';
  return 'd';
}

// ---------- reminders ----------

function dailyCheck(force) {
  force = force === true; // a time trigger passes an event object
  const sh = sheet_();
  // Picks up rows edited by hand in the sheet.
  try { syncCalendar_(readDocs_()); } catch (err) { console.error('Calendar sync failed', err); }
  const tz = sh.getParent().getSpreadsheetTimeZone();
  const todayISO = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');
  const today = utcDay_(todayISO);
  const weekday = new Date(today).getUTCDay();

  const lines = [];
  readDocs_()
    .map(d => ({ d, exp: utcDay_(d.expires) }))
    .sort((a, b) => a.exp - b.exp)
    .forEach(({ d, exp }) => {
      const start = subtractLead_(exp, d.leadValue, d.leadUnit);
      if (today < start || d.submitted) return; // already handed in for renewal
      const left = Math.round((exp - today) / DAY);
      // First day of the window, milestones, then a weekly Monday digest — not daily spam.
      const due = force || today === start || [60, 30, 14, 7, 3, 1, 0].indexOf(left) >= 0 || weekday === 1;
      if (!due) return;
      const name = d.name.replace(/[<>&]/g, '');
      if (left < 0) lines.push(`🔴 <b>${name}</b> — истёк ${fmt_(exp)} (${days_(-left)} назад)`);
      else if (left === 0) lines.push(`🔴 <b>${name}</b> — истекает сегодня!`);
      else lines.push(`🟠 <b>${name}</b> — действует до ${fmt_(exp)}, осталось ${days_(left)}`);
    });

  if (!lines.length) {
    Logger.log('Сегодня напоминать не о чем.');
    return;
  }

  const appUrl = 'https://an-mish.github.io/doctrack/';
  MailApp.sendEmail({
    to: Session.getEffectiveUser().getEmail(),
    subject: `Пора обновить документы (${lines.length})`,
    htmlBody: `<p>${lines.join('<br>')}</p><p><a href="${appUrl}">Открыть приложение</a></p>`,
  });

  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('TELEGRAM_BOT_TOKEN');
  const chatId = props.getProperty('TELEGRAM_CHAT_ID');
  if (token && chatId) {
    UrlFetchApp.fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify({
        chat_id: chatId,
        parse_mode: 'HTML',
        text: `📄 <b>Пора обновить документы</b>\n\n${lines.join('\n')}\n\n${appUrl}`,
      }),
    });
  }
  Logger.log(`Отправлено напоминаний: ${lines.length}`);
}

function utcDay_(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}

function subtractLead_(t, value, unit) {
  const d = new Date(t);
  if (unit === 'm') {
    const day = d.getUTCDate();
    d.setUTCDate(1);
    d.setUTCMonth(d.getUTCMonth() - value);
    d.setUTCDate(Math.min(day, new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()));
  } else {
    d.setUTCDate(d.getUTCDate() - value * (unit === 'w' ? 7 : 1));
  }
  return d.getTime();
}

function fmt_(t) {
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  const d = new Date(t);
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

function days_(n) {
  const a = Math.abs(n) % 100, b = a % 10;
  const w = a > 10 && a < 20 ? 'дней' : b === 1 ? 'день' : b > 1 && b < 5 ? 'дня' : 'дней';
  return `${n} ${w}`;
}

// ---------- calendar ----------

// A separate calendar keeps these events apart from personal ones; it can be hidden or recoloured in Google Calendar.
function calendar_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('CALENDAR_ID');
  let cal = id && CalendarApp.getCalendarById(id);
  if (!cal) {
    cal = CalendarApp.createCalendar(CALENDAR_NAME, { color: CalendarApp.Color.BLUE });
    props.setProperty('CALENDAR_ID', cal.getId());
  }
  return cal;
}

// Two all-day events per document — renewal start and expiry — each with a reminder at 9:00 the day before.
// Events are tagged with the document id, so only changed ones are touched.
function syncCalendar_(docs) {
  const cal = calendar_();
  const tz = Session.getScriptTimeZone();
  const wanted = {};
  docs.forEach(d => {
    const exp = utcDay_(d.expires);
    const start = subtractLead_(exp, d.leadValue, d.leadUnit);
    const note = d.note ? `\n\n${d.note}` : '';
    const app = '\n\nhttps://an-mish.github.io/doctrack/';
    if (start < exp) {
      wanted[`${d.id}|start`] = {
        date: isoFromUtc_(start), title: `🟠 Начать обновление: ${d.name}`,
        desc: `${d.type}. Действует до ${fmt_(exp)}.${note}${app}`,
      };
    }
    wanted[`${d.id}|expire`] = {
      date: d.expires, title: `🔴 Истекает: ${d.name}`,
      desc: `${d.type}. Последний день действия документа.${note}${app}`,
    };
  });

  cal.getEvents(new Date(2000, 0, 1), new Date(2100, 0, 1)).forEach(ev => {
    const key = `${ev.getTag('doctrackId')}|${ev.getTag('kind')}`;
    const w = wanted[key];
    if (!w) { ev.deleteEvent(); return; }
    const date = Utilities.formatDate(ev.getAllDayStartDate(), tz, 'yyyy-MM-dd');
    if (date !== w.date) { ev.deleteEvent(); return; } // recreated below on the new date
    if (ev.getTitle() !== w.title) ev.setTitle(w.title);
    if (ev.getDescription() !== w.desc) ev.setDescription(w.desc);
    delete wanted[key];
  });

  Object.keys(wanted).forEach(key => {
    const w = wanted[key];
    const [id, kind] = key.split('|');
    const ev = cal.createAllDayEvent(w.title, Utilities.parseDate(w.date, tz, 'yyyy-MM-dd'), { description: w.desc });
    ev.setTag('doctrackId', id);
    ev.setTag('kind', kind);
    ev.removeAllReminders();
    ev.addPopupReminder(15 * 60); // all-day events start at midnight: 15 h before = 9:00 the day before
  });
}

function isoFromUtc_(t) {
  return new Date(t).toISOString().slice(0, 10);
}
