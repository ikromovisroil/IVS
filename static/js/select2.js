function initSelect2(context) {
  context = context || document;

  function opts($el, dropdownParent) {
    const isMultiple = $el.prop('multiple');
    return {
      width: '100%',
      placeholder: $el.data('placeholder') || 'Tanlang...',
      allowClear: !isMultiple,
      closeOnSelect: !isMultiple,
      dropdownParent: dropdownParent
    };
  }

  $(context).find('select[data-s2!="1"]').each(function () {
    const $el = $(this);
    if ($el.closest('.modal').length) return;

    $el.select2(opts($el));
    $el.attr('data-s2', '1');
  });

  $(context).find('.modal').each(function(){
    const $modal = $(this);

    $modal.find('select[data-s2!="1"]').each(function(){
      const $el = $(this);
      $el.select2(opts($el, $modal));
      $el.attr('data-s2', '1');
    });
  });
}

$(function(){
  initSelect2(document);
});

document.addEventListener('shown.bs.modal', function (e) {
  initSelect2(e.target);
});

window.initSelect2 = initSelect2;