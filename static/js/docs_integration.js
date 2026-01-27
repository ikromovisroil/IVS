(function () {
  const cfg = window.ONLYOFFICE_CONFIG || {};
  const token = window.ONLYOFFICE_TOKEN || "";

  if (token.length > 0) {
    cfg.token = token;
  }

  cfg.events = cfg.events || {};

  cfg.events.onDocumentReady = function () {
    console.log("OnlyOffice ready");
  };

  cfg.events.onError = function (e) {
    console.error("OnlyOffice error:", e);
    alert("OnlyOffice xatolik!");
  };

  // Editor
  const docEditor = new DocsAPI.DocEditor("editor", cfg);

  // Save tugmasi -> forcesave
  const btn = document.getElementById("btnSave");
  if (btn) {
    btn.addEventListener("click", function () {
      try {
        docEditor.executeCommand("forcesave");
        alert("Saqlash yuborildi. 1-5 soniyada serverga tushadi.");
      } catch (err) {
        console.error(err);
        alert("Saqlashda xatolik!");
      }
    });
  }
})();
