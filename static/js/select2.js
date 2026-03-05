// static/js/select2.js
(function($){
  // Universal init: sahifada ham, modal ichida ham
  function initSelect2(context) {
    context = context || document;

    // Oddiy sahifa selectlari: modal ichida bo'lmaganlar
    $(context).find('select[data-s2!="1"]').each(function () {
      const $el = $(this);

      // agar modal ichida bo'lsa — pastdagi modal init o'zi qiladi
      if ($el.closest('.modal').length) return;

      $el.select2({
        width: '100%',
        placeholder: $el.data('placeholder') || 'Tanlang...',
        allowClear: true
      });

      $el.attr('data-s2', '1');
    });

    // Modal ichidagi selectlar: dropdownParent = modal
    $(context).find('.modal').each(function(){
      const $modal = $(this);

      $modal.find('select[data-s2!="1"]').each(function(){
        const $el = $(this);

        $el.select2({
          width: '100%',
          dropdownParent: $modal, // MODAL uchun shart
          placeholder: $el.data('placeholder') || 'Tanlang...',
          allowClear: true
        });

        $el.attr('data-s2', '1');
      });
    });
  }

  // 1) Sahifa yuklanganda
  $(function(){
    initSelect2(document);
  });

  // 2) Bootstrap modal ochilganda (dinamik selectlar ham ishlaydi)
  document.addEventListener('shown.bs.modal', function (e) {
    initSelect2(e.target);
  });

  // 3) Agar siz AJAX bilan select qo‘shsangiz:
  //    AJAX success ichida: initSelect2(yangi_container);
  window.initSelect2 = initSelect2;

})(jQuery);