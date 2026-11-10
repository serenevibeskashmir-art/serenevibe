// Google Apps Script - receives one row per generated quote PDF and writes it to the sheet.
// Columns: Name | Quote No | Cost | Travel Date | Generated At | Email | Days | Adults | Kids | Budget Tier | Vehicle | Meal Plan | Pick-up | Drop | Hotels | Inclusions | Booking Amount | Payment Status | Balance
//
// The admin panel (Accounts tab) also talks to this script: action "list" reads the rows, action "pay" saves a booking amount.
// It also keeps a second tab, "Expenses", for money you spend and profit you earn (actions "ledger_list", "ledger_add", "ledger_delete").
// Expenses columns: Date | Type | Category | Description | Amount | Quote No | Added At | ID   (totals appear in J1:K4)
// Payment tracking (no typing needed):
//   Payment Status is a dropdown on every row. Pick "Token paid"   -> Booking Amount fills with 25% of Cost.
//                                              Pick "Paid in full" -> Booking Amount fills with the full Cost.
//   Balance is a formula (Cost - Booking Amount). If the client paid a different amount, just type over Booking Amount.
//   The script never overwrites Booking Amount or Payment Status when a quote is re-generated.
const SECRET = "June@2024";          // must equal GOOGLE_SHEET_SECRET in your server settings
const SHEET_NAME = "Quotes";
const SHEET_ID = "";                 // only needed if this script was NOT created from the sheet (Extensions > Apps Script)
const INSTALMENT_PCT = 0.25;         // 1st instalment, same as the PDF payment schedule

const HEADERS = ["Name", "Quote No", "Cost", "Travel Date", "Generated At",
                 "Email", "Days", "Adults", "Kids", "Budget Tier", "Vehicle", "Meal Plan", "Pick-up", "Drop", "Hotels", "Inclusions",
                 "Booking Amount", "Payment Status", "Balance"];
const AUTO_COLS = 16;                // the server writes columns 1-16 only
const COST_COL = 3, AMOUNT_COL = 17, STATUS_COL = 18, BALANCE_COL = 19;
const STATUS_TOKEN = "Token paid", STATUS_FULL = "Paid in full";
const STATUSES = ["Pending", STATUS_TOKEN, STATUS_FULL];

// ---- Expenses & profit tab ----
const LEDGER_SHEET = "Expenses";
const LEDGER_HEADERS = ["Date", "Type", "Category", "Description", "Amount", "Quote No", "Added At", "ID"];
const L_DATE = 1, L_TYPE = 2, L_CAT = 3, L_DESC = 4, L_AMT = 5, L_QUOTE = 6, L_ADDED = 7, L_ID = 8;
const L_PROFIT = "Profit", L_EXPENSE = "Expense";
const L_TYPES = [L_PROFIT, L_EXPENSE];
const IMPORT_TAG = "(payment received)";   // marks rows made by importPastPayments()

// Open the Web app URL in a browser: you should see {"ok":true,"alive":true}. If you see a Google login page, redeploy as "Anyone".
function doGet() { return out({ ok: true, alive: true }); }

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (String(d.secret || "").trim() !== SECRET) return out({ ok: false, error: "bad secret" });

    const ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
    if (d.action === "list") return out(listRows(ss));
    if (d.action === "pay") return out(payRow(ss, d));
    if (d.action === "ledger_list") return out(ledgerList(ss));
    if (d.action === "ledger_add") return out(ledgerAdd(ss, d));
    if (d.action === "ledger_delete") return out(ledgerDelete(ss, d));
    const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    const n = HEADERS.length;

    // Create or upgrade the header row (older sheets had fewer columns).
    sh.getRange(1, 1, 1, n).setValues([HEADERS])
      .setFontWeight("bold").setBackground("#0f172a").setFontColor("#ffffff");
    sh.setFrozenRows(1);

    const row = [d.name, d.quote_no, d.cost, "'" + d.travel_date, d.generated_at,
                 d.email || "", d.days || "", d.adults || "", d.kids || 0, d.budget_tier || "",
                 d.vehicle || "", d.meal_plan || "", d.pickup || "", d.drop || "", d.hotels || "", d.inclusions || ""];

    // Re-generating the same quote updates its row instead of adding a duplicate.
    const last = sh.getLastRow();
    if (last > 1) {
      const vals = sh.getRange(2, 1, last - 1, 2).getValues();
      for (let i = 0; i < vals.length; i++) {
        if (String(vals[i][0]) === String(d.name) && String(vals[i][1]) === String(d.quote_no)) {
          sh.getRange(i + 2, 1, 1, AUTO_COLS).setValues([row]);   // keeps Booking Amount / Payment Status already set
          finishRow(sh, i + 2);
          return out({ ok: true, updated: true });
        }
      }
    }
    sh.appendRow(row);
    finishRow(sh, sh.getLastRow());
    return out({ ok: true });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}

// Status that matches an amount received (used by the admin panel and the dropdown).
function statusFor(amount, cost) {
  if (!(amount > 0)) return STATUSES[0];
  return cost > 0 && amount >= cost ? STATUS_FULL : STATUS_TOKEN;
}

function cellText(v) {
  if (v instanceof Date) return Utilities.formatDate(v, Session.getScriptTimeZone(), "dd MMM yyyy");
  return v === null || v === undefined ? "" : String(v);
}

// Admin panel: every quote row with its payment details.
function listRows(ss) {
  const sh = ss.getSheetByName(SHEET_NAME);
  if (!sh || sh.getLastRow() < 2) return { ok: true, rows: [] };
  const vals = sh.getRange(2, 1, sh.getLastRow() - 1, AMOUNT_COL).getValues();
  const rows = vals.map(function (v) {
    const cost = Number(v[COST_COL - 1]) || 0, paid = Number(v[AMOUNT_COL - 1]) || 0;
    return { name: cellText(v[0]), quote_no: cellText(v[1]), cost: cost, travel_date: cellText(v[3]),
             generated_at: cellText(v[4]), email: cellText(v[5]), booking_amount: paid,
             status: statusFor(paid, cost), balance: cost - paid };
  }).filter(function (r) { return r.name || r.quote_no; });
  return { ok: true, rows: rows.reverse() };      // newest first
}

// Admin panel: save the amount received for one quote (name + quote no). 0 clears it.
function payRow(ss, d) {
  const sh = ss.getSheetByName(SHEET_NAME);
  if (!sh || sh.getLastRow() < 2) return { ok: false, error: "Quotes sheet is empty." };
  const amount = Math.round(Number(d.amount));
  if (!(amount >= 0)) return { ok: false, error: "Amount must be a number." };
  const keys = sh.getRange(2, 1, sh.getLastRow() - 1, 2).getValues();
  for (let i = keys.length - 1; i >= 0; i--) {         // newest match first
    if (String(keys[i][0]) === String(d.name) && String(keys[i][1]) === String(d.quote_no)) {
      const r = i + 2, cost = Number(sh.getRange(r, COST_COL).getValue()) || 0;
      const cell = sh.getRange(r, AMOUNT_COL);
      if (amount > 0) cell.setValue(amount); else cell.clearContent();
      finishRow(sh, r);
      sh.getRange(r, STATUS_COL).setValue(statusFor(amount, cost));
      return { ok: true, row: { name: String(d.name), quote_no: String(d.quote_no), cost: cost,
               booking_amount: amount, status: statusFor(amount, cost), balance: cost - amount } };
    }
  }
  return { ok: false, error: "That quote is not in the sheet." };
}

// Number formats, the Payment Status dropdown and the Balance formula for one row.
function finishRow(sh, r) {
  sh.getRange(r, COST_COL).setNumberFormat("#,##0");
  sh.getRange(r, AMOUNT_COL).setNumberFormat("#,##0");
  const status = sh.getRange(r, STATUS_COL);
  status.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(true).build());
  if (status.isBlank()) status.setValue(STATUSES[0]);
  const bal = sh.getRange(r, BALANCE_COL);
  bal.setFormula('=IF(OR(Q' + r + '="",C' + r + '=""),"",C' + r + '-Q' + r + ')').setNumberFormat("#,##0");
}

// Runs by itself whenever you edit the sheet (a simple trigger: nothing to install or authorise).
function onEdit(e) {
  if (!e || !e.range) return;
  const sh = e.range.getSheet();
  if (sh.getName() !== SHEET_NAME) return;
  const r = e.range.getRow();
  if (r < 2 || e.range.getColumn() !== STATUS_COL || e.range.getNumRows() !== 1) return;
  const status = String(e.value || "").trim();
  const cost = Number(sh.getRange(r, COST_COL).getValue());
  const amount = sh.getRange(r, AMOUNT_COL);
  if (!(cost > 0)) return;
  if (status === STATUS_TOKEN && amount.isBlank()) amount.setValue(Math.round(cost * INSTALMENT_PCT));
  if (status === STATUS_FULL) amount.setValue(cost);
}

// Run this once by hand (select it above, press Run) to add the dropdown and Balance formula to quotes that are already in the sheet.
function upgradeExistingRows() {
  const ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
  const sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) return;
  sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS])
    .setFontWeight("bold").setBackground("#0f172a").setFontColor("#ffffff");
  for (let r = 2; r <= sh.getLastRow(); r++) {
    finishRow(sh, r);
    // Rows where you already typed a Booking Amount are marked Token paid / Paid in full to match.
    const amt = Number(sh.getRange(r, AMOUNT_COL).getValue()), cost = Number(sh.getRange(r, COST_COL).getValue());
    if (amt > 0 && cost > 0) sh.getRange(r, STATUS_COL).setValue(amt >= cost ? STATUS_FULL : STATUS_TOKEN);
  }
}

// ---------------------------------------------------------------------------------------------
// Expenses & profit
// ---------------------------------------------------------------------------------------------

// The Expenses tab: created (with header, dropdown and totals) the first time it is needed.
function getLedger(ss) {
  let sh = ss.getSheetByName(LEDGER_SHEET);
  if (!sh) sh = ss.insertSheet(LEDGER_SHEET);
  const n = LEDGER_HEADERS.length;
  const head = sh.getRange(1, 1, 1, n);
  if (String(head.getValues()[0].join("|")) !== LEDGER_HEADERS.join("|")) {
    head.setValues([LEDGER_HEADERS]).setFontWeight("bold").setBackground("#0f172a").setFontColor("#ffffff");
    sh.setFrozenRows(1);
    sh.getRange(2, L_DATE, sh.getMaxRows() - 1, 1).setNumberFormat("dd mmm yyyy");
    sh.getRange(2, L_AMT, sh.getMaxRows() - 1, 1).setNumberFormat("#,##0");
    sh.getRange(2, L_TYPE, sh.getMaxRows() - 1, 1).setDataValidation(
      SpreadsheetApp.newDataValidation().requireValueInList(L_TYPES, true).setAllowInvalid(true).build());
    sh.setColumnWidth(L_DESC, 260);
    sh.setColumnWidth(L_ID, 90);
    // Running totals, always up to date because they are formulas.
    sh.getRange("J1:K4").setValues([["Summary", ""], ["Total Profit", ""], ["Total Expenses", ""], ["Net (Profit - Expenses)", ""]]);
    sh.getRange("K2").setFormula('=SUMIF(B:B,"' + L_PROFIT + '",E:E)');
    sh.getRange("K3").setFormula('=SUMIF(B:B,"' + L_EXPENSE + '",E:E)');
    sh.getRange("K4").setFormula("=K2-K3");
    sh.getRange("J1:K1").setFontWeight("bold").setBackground("#0f172a").setFontColor("#ffffff");
    sh.getRange("J2:J4").setFontWeight("bold");
    sh.getRange("K2:K4").setNumberFormat("#,##0");
    sh.setColumnWidth(10, 170);
    sh.setColumnWidth(11, 110);
  }
  return sh;
}

// Run this once by hand if you want the Expenses tab to appear before the first entry is added.
function setupLedger() {
  const ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
  getLedger(ss);
}

function dateText(v) {                                  // yyyy-MM-dd for the admin panel
  if (v instanceof Date) return Utilities.formatDate(v, Session.getScriptTimeZone(), "yyyy-MM-dd");
  return v === null || v === undefined ? "" : String(v);
}

function newId() { return Utilities.getUuid().replace(/-/g, "").slice(0, 8); }

// Admin panel: every entry, newest date first. Rows you typed by hand in the sheet get an ID here.
function ledgerList(ss) {
  const sh = getLedger(ss);
  const last = sh.getLastRow();
  if (last < 2) return { ok: true, rows: [] };
  const range = sh.getRange(2, 1, last - 1, LEDGER_HEADERS.length);
  const vals = range.getValues();
  let filled = false;
  const rows = [];
  vals.forEach(function (v) {
    if (!v[L_TYPE - 1] && !v[L_AMT - 1] && !v[L_DESC - 1] && !v[L_CAT - 1]) return;   // blank line
    if (!v[L_ID - 1]) { v[L_ID - 1] = newId(); filled = true; }
    const type = String(v[L_TYPE - 1]).trim() === L_PROFIT ? L_PROFIT : L_EXPENSE;
    rows.push({ id: String(v[L_ID - 1]), date: dateText(v[L_DATE - 1]), type: type, category: cellText(v[L_CAT - 1]),
                description: cellText(v[L_DESC - 1]), amount: Number(v[L_AMT - 1]) || 0, quote_no: cellText(v[L_QUOTE - 1]),
                added_at: cellText(v[L_ADDED - 1]) });
  });
  if (filled) sh.getRange(2, L_ID, vals.length, 1).setValues(vals.map(function (v) { return [v[L_ID - 1]]; }));
  rows.reverse();                                       // later rows first ...
  rows.sort(function (a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : 0; });   // ... then newest date on top (stable)
  return { ok: true, rows: rows };
}

// Admin panel: add one entry (type, amount, date, category, description, quote_no).
function ledgerAdd(ss, d) {
  const type = String(d.type || "").trim();
  if (L_TYPES.indexOf(type) < 0) return { ok: false, error: "Type must be Profit or Expense." };
  const amount = Math.round(Number(d.amount) * 100) / 100;
  if (!(amount > 0)) return { ok: false, error: "Amount must be more than 0." };
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(d.date || ""));
  if (!m) return { ok: false, error: "Date must look like 2026-11-10." };
  const date = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);                                 // two quick saves must not write to the same row
  try {
    const sh = getLedger(ss);
    const id = newId();
    const added = Utilities.formatDate(new Date(), "Asia/Kolkata", "dd MMM yyyy HH:mm");
    const row = [date, type, String(d.category || "").slice(0, 60), String(d.description || "").slice(0, 300),
                 amount, String(d.quote_no || "").slice(0, 40), added, id];
    const r = sh.getLastRow() + 1;
    sh.getRange(r, 1, 1, row.length).setValues([row]);
    sh.getRange(r, L_DATE).setNumberFormat("dd mmm yyyy");
    sh.getRange(r, L_AMT).setNumberFormat("#,##0");
    sh.getRange(r, L_TYPE).setDataValidation(
      SpreadsheetApp.newDataValidation().requireValueInList(L_TYPES, true).setAllowInvalid(true).build());
    return { ok: true, row: { id: id, date: dateText(date), type: type, category: row[2], description: row[3],
                              amount: amount, quote_no: row[5], added_at: added } };
  } finally {
    lock.releaseLock();
  }
}

// Admin panel: remove one entry by its ID.
function ledgerDelete(ss, d) {
  const id = String(d.id || "").trim();
  if (!id) return { ok: false, error: "Entry not specified." };
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sh = getLedger(ss);
    if (sh.getLastRow() < 2) return { ok: false, error: "That entry is not in the sheet." };
    const ids = sh.getRange(2, L_ID, sh.getLastRow() - 1, 1).getValues();
    for (let i = ids.length - 1; i >= 0; i--) {
      if (String(ids[i][0]) === id) { sh.deleteRow(i + 2); return { ok: true }; }
    }
    return { ok: false, error: "That entry is not in the sheet (maybe it was already deleted)." };
  } finally {
    lock.releaseLock();
  }
}

// Run this ONCE by hand (select it above, press Run) to copy the money already received on the Quotes tab
// into the Expenses tab as Profit entries (one per quote with a Booking Amount). Safe to run again: quotes
// already imported are skipped. Date used = the day the quote was generated. Shows how many were added.
function importPastPayments() {
  const ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
  const q = ss.getSheetByName(SHEET_NAME);
  if (!q || q.getLastRow() < 2) { Logger.log("Quotes sheet is empty - nothing to import."); return; }
  const led = getLedger(ss);
  const have = {};                                       // quotes already in the Expenses tab
  if (led.getLastRow() > 1) {
    led.getRange(2, 1, led.getLastRow() - 1, LEDGER_HEADERS.length).getValues().forEach(function (v) {
      if (String(v[L_DESC - 1]).indexOf(IMPORT_TAG) >= 0) have[String(v[L_QUOTE - 1]) + "|" + String(v[L_DESC - 1])] = true;
    });
  }
  const vals = q.getRange(2, 1, q.getLastRow() - 1, AMOUNT_COL).getValues();
  const added = Utilities.formatDate(new Date(), "Asia/Kolkata", "dd MMM yyyy HH:mm");
  const rows = [];
  vals.forEach(function (v) {
    const paid = Number(v[AMOUNT_COL - 1]) || 0;
    if (!(paid > 0)) return;
    const desc = String(v[0]) + " " + IMPORT_TAG;
    const quoteNo = String(v[1]);
    if (have[quoteNo + "|" + desc]) return;
    let when = v[4] instanceof Date ? v[4] : new Date(String(v[4]));
    if (isNaN(when.getTime())) when = new Date();
    rows.push([new Date(when.getFullYear(), when.getMonth(), when.getDate()), L_PROFIT, "Package booking",
               desc, paid, quoteNo, added, newId()]);
  });
  if (rows.length) {
    const r = led.getLastRow() + 1;
    led.getRange(r, 1, rows.length, LEDGER_HEADERS.length).setValues(rows);
    led.getRange(r, L_DATE, rows.length, 1).setNumberFormat("dd mmm yyyy");
    led.getRange(r, L_AMT, rows.length, 1).setNumberFormat("#,##0");
  }
  Logger.log("Imported " + rows.length + " past payment(s) as Profit.");
}

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function whereAmI() {
  Logger.log(SpreadsheetApp.getActiveSpreadsheet().getUrl());
}
