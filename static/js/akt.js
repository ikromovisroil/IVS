// akt.js
$(function () {
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text || "";
  }

  function selectedText($select) {
    const val = $select.val();
    if (!val) return "";
    const txt = $select.find("option:selected").text();
    if (!txt || txt.toLowerCase().includes("tanlang")) return "";
    return txt.trim();
  }

  function syncOrgText() {
    const t = selectedText($("#organization"));
    setText("org_id_1", t);
    setText("org_id_2", t);
  }

  function syncDepText() {
    setText("dep_id", selectedText($("#department")));
  }

  function syncSenderText() {
    const t = selectedText($("#sender"));
    setText("sender_name1", t); // ✅ HTMLdagi id
    setText("sender_name2", t); // ✅ HTMLdagi id
  }

  function clearDepSenderText() {
    setText("dep_id", "");
    setText("sender_name1", "");
    setText("sender_name2", "");
  }

  function clearSenderText() {
    setText("sender_name1", "");
    setText("sender_name2", "");
  }

  // ✅ Select2 bo‘lsa ham change ishlaydi
  $("#organization").on("change", function () {
    syncOrgText();
    clearDepSenderText(); // org o‘zgarsa dep + sender text tozalanadi
  });

  $("#department").on("change", function () {
    syncDepText();
    clearSenderText(); // dep o‘zgarsa sender text tozalanadi
  });

  $("#sender").on("change", function () {
    syncSenderText();
  });

  // ✅ Sahifa ochilganda ham bir marta sync qilib qo‘yamiz
  syncOrgText();
  syncDepText();
  syncSenderText();
});
