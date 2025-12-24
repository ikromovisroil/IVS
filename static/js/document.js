// ===============================
// 1) INPUTLARNI SARIQ QILISH
// ===============================
function highlightInput(inputId, targetId, defaultText) {
  const input = document.getElementById(inputId);
  const targets = document.querySelectorAll(`#${targetId}`);

  if (!input) return; // agar input bo‘lmasa – chiqib ketadi

  input.addEventListener('input', function () {
    targets.forEach(target => {
      if (this.value.trim() !== "") {
        target.innerHTML = `<span style="background-color: yellow;">${this.value}</span>`;
      } else {
        target.textContent = defaultText;
      }
    });
  });
}

// Ishlatish:
highlightInput('fio_id', 'fio_id_text', 'Sh.Muxamedov');
highlightInput('post_id', 'post_id_text', 'direktori');
highlightInput('namber_id', 'namber_id_text', '1');
highlightInput('rim_id', 'rim_id_text', 'I');


// ===============================
// 2) SANA FORMATLAB SARIQ QILISH
// ===============================
function highlightDate(inputId, targetId, defaultText) {
  const input = document.getElementById(inputId);
  const target = document.getElementById(targetId);

  if (!input || !target) return;

  const months = [
    "yanvarda", "fevralda", "martda", "aprelda", "mayda", "iyunda",
    "iyulda", "avgustda", "sentabrda", "oktabrda", "noyabrda", "dekabrda"
  ];

  input.addEventListener('input', function () {
    if (this.value) {
      const [y, m, d] = this.value.split("-");
      const formatted = `${y} yil ${parseInt(d)} - ${months[m - 1]}`;
      target.innerHTML = `<span style="background-color: yellow;">${formatted}</span>`;
    } else {
      target.textContent = defaultText;
    }
  });
}

highlightDate('date_id', 'date_id_text', '2025 yil 4 - martda');


// ===============================
// 3) SELECTDAN TANLANGAN NOMSARIQ
// ===============================
$(document).ready(function(){

    function updateSelektText() {

        let val = "";
        let isSelected = false;

        if ($('#division').val()) {
            val = $('#division option:selected').text();
            isSelected = true;
        }
        else if ($('#directorate').val()) {
            val = $('#directorate option:selected').text();
            isSelected = true;
        }
        else if ($('#department').val()) {
            val = $('#department option:selected').text();
            isSelected = true;
        }
        else if ($('#organization').val()) {
            val = $('#organization option:selected').text();
            isSelected = true;
        }

        if (!isSelected || val === "" || val === "Tanlang...") {
            val = "Davlat byudjeti siyosati departamenti";
            isSelected = false;
        }

        $('span#selekt_id_text').each(function () {
            if (isSelected) {
                $(this).html(`<span style="background-color: yellow;padding:2px 4px;">${val}</span>`);
            } else {
                $(this).text(val);
            }
        });
    }

    $(document).on('change', '#organization, #department, #directorate, #division', function () {
        updateSelektText();
    });

    updateSelektText();

});
