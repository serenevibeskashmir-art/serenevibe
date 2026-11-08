// Google Apps Script - receives one row per generated quote PDF and writes it to the sheet.
// Setup: see the steps in the chat / README. Columns: Name | Quote No | Cost | Travel Date | Generated At
const SECRET = "June@2024";          // must equal GOOGLE_SHEET_SECRET in your server settings
const SHEET_NAME = "Quotes";

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.secret !== SECRET) return out({ ok: false, error: "bad secret" });

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
    if (sh.getLastRow() === 0) {
      sh.appendRow(["Name", "Quote No", "Cost", "Travel Date", "Generated At"]);
      sh.getRange(1, 1, 1, 5).setFontWeight("bold").setBackground("#0f172a").setFontColor("#ffffff");
      sh.setFrozenRows(1);
    }
    const row = [d.name, d.quote_no, d.cost, "'" + d.travel_date, d.generated_at];   // ' keeps the date as typed
    // Re-generating the same quote updates its row instead of adding a duplicate.
    const last = sh.getLastRow();
    if (last > 1) {
      const vals = sh.getRange(2, 1, last - 1, 2).getValues();
      for (let i = 0; i < vals.length; i++) {
        if (vals[i][0] === d.name && vals[i][1] === d.quote_no) {
          sh.getRange(i + 2, 1, 1, 5).setValues([row]);
          return out({ ok: true, updated: true });
        }
      }
    }
    sh.appendRow(row);
    sh.getRange(sh.getLastRow(), 3).setNumberFormat("#,##0");
    return out({ ok: true });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
