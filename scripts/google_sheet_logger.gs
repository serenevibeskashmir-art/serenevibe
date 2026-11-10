// Google Apps Script - receives one row per generated quote PDF and writes it to the sheet.
// Columns: Name | Quote No | Cost | Travel Date | Generated At | Email | Days | Adults | Kids | Budget Tier | Vehicle | Meal Plan | Pick-up | Drop | Hotels | Inclusions | Booking Amount | Payment Status | Balance
//
// The admin panel (Payments tab) also talks to this script: action "list" reads the rows, action "pay" saves a booking amount.
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

// Open the Web app URL in a browser: you should see {"ok":true,"alive":true}. If you see a Google login page, redeploy as "Anyone".
function doGet() { return out({ ok: true, alive: true }); }

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (String(d.secret || "").trim() !== SECRET) return out({ ok: false, error: "bad secret" });

    const ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
    if (d.action === "list") return out(listRows(ss));
    if (d.action === "pay") return out(payRow(ss, d));
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

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function whereAmI() {
  Logger.log(SpreadsheetApp.getActiveSpreadsheet().getUrl());
}
