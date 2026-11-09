// Google Apps Script - receives one row per generated quote PDF and writes it to the sheet.
// Columns: Name | Quote No | Cost | Travel Date | Generated At | Email | Days | Adults | Kids | Budget Tier | Vehicle | Meal Plan | Pick-up | Drop | Hotels | Inclusions | Booking Amount
const SECRET = "June@2024";          // must equal GOOGLE_SHEET_SECRET in your server settings
const SHEET_NAME = "Quotes";
const SHEET_ID = "";                 // only needed if this script was NOT created from the sheet (Extensions > Apps Script)

const HEADERS = ["Name", "Quote No", "Cost", "Travel Date", "Generated At",
                 "Email", "Days", "Adults", "Kids", "Budget Tier", "Vehicle", "Meal Plan", "Pick-up", "Drop", "Hotels", "Inclusions", "Booking Amount"];   // last column is filled in by hand once the client pays
const AUTO_COLS = HEADERS.length - 1;   // the script only writes these; "Booking Amount" is never touched

// Open the Web app URL in a browser: you should see {"ok":true,"alive":true}. If you see a Google login page, redeploy as "Anyone".
function doGet() { return out({ ok: true, alive: true }); }

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (String(d.secret || "").trim() !== SECRET) return out({ ok: false, error: "bad secret" });

    const ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
    const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    const n = HEADERS.length;

    // Create or upgrade the header row (older sheets only had the first 5 columns).
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
          sh.getRange(i + 2, 1, 1, AUTO_COLS).setValues([row]);   // keeps a Booking Amount you already typed
          sh.getRange(i + 2, 3).setNumberFormat("#,##0");
          return out({ ok: true, updated: true });
        }
      }
    }
    sh.appendRow(row);
    sh.getRange(sh.getLastRow(), 3).setNumberFormat("#,##0");
    sh.getRange(sh.getLastRow(), n).setNumberFormat("#,##0");   // Booking Amount cell: empty, ready to type in
    return out({ ok: true });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function whereAmI() {
  Logger.log(SpreadsheetApp.getActiveSpreadsheet().getUrl());
}
