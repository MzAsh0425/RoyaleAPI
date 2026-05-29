/**
 * クラロワ アーキタイプ辞書入力支援 GAS
 * CardMasterシートのカード画像を使い、サイドバーからクリックで入力する。
 */

// ==========================================
// メニュー追加
// ==========================================
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("クラロワ管理")
    .addItem("カード入力パネルを開く", "showSidebar")
    .addToUi();
}

function showSidebar() {
  var html = HtmlService.createHtmlOutputFromFile("Sidebar")
    .setTitle("カード入力パネル");
  SpreadsheetApp.getUi().showSidebar(html);
}

// ==========================================
// CardMasterからカード一覧を取得
// ==========================================
function getCardMaster() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName("CardMaster");
  if (!ws) {
    return [];
  }
  var data = ws.getDataRange().getValues();
  var headers = data[0];
  var cards = [];
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    cards.push({
      name: row[0] || "",
      iconUrl: row[1] || "",
      elixirCost: row[2] !== "" ? row[2] : null,
      rarity: row[3] || ""
    });
  }
  return cards;
}

// ==========================================
// アクティブセルにカード名を追記（重複ブロック）
// ==========================================
function appendCardToCell(cardName) {
  var sheet = SpreadsheetApp.getActiveSheet();
  var cell = sheet.getActiveCell();
  var current = cell.getValue().toString().trim();

  if (current === "") {
    cell.setValue(cardName);
    return { success: true, value: cardName };
  }

  // 既存カードをパースして重複チェック
  var existing = current.split(",").map(function(s) { return s.trim(); });
  if (existing.indexOf(cardName) !== -1) {
    return { success: false, value: current, message: cardName + " は既に追加済みです" };
  }

  var newValue = current + ", " + cardName;
  cell.setValue(newValue);
  return { success: true, value: newValue };
}

// ==========================================
// アクティブセルをクリア
// ==========================================
function clearCell() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var cell = sheet.getActiveCell();
  cell.setValue("");
  return { success: true, value: "" };
}

// ==========================================
// 末尾のカードを1つ削除（Undo）
// ==========================================
function undoLastCard() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var cell = sheet.getActiveCell();
  var current = cell.getValue().toString().trim();

  if (current === "") {
    return { success: false, value: "", message: "セルは空です" };
  }

  var cards = current.split(",").map(function(s) { return s.trim(); });
  var removed = cards.pop();
  var newValue = cards.join(", ");
  cell.setValue(newValue);
  return { success: true, value: newValue, removed: removed };
}
