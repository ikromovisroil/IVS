/*
 * Select2 uchun "admin paneldagidek" sahifalash:
 * ro'yxat ochilganda 20 ta variant ko'rinadi, pastga skroll qilinsa keyingi 20 tasi yuklanadi,
 * qidiruv esa butun ro'yxat bo'yicha ishlaydi.
 *
 * select2.min.js dan keyin ulanadi va $.fn.select2 ni o'rab oladi — shu sabab
 * loyihadagi barcha select2 (global initSelect2 ham, sahifalardagi alohida chaqiruvlar ham)
 * avtomatik shu rejimda ishlaydi. Variantlar <option> lardan o'qiladi, shuning uchun
 * mavjud cascading JS, data-* atributlar va oldindan tanlangan qiymatlar o'zgarmaydi.
 *
 * Server rejimi (haqiqiy tezlashish): <select data-ajax-url="..." data-ajax-params='{"param":"#bogliq_select"}'>
 * Ro'yxat serverdan 20 tadan (`q` — qidiruv, `page` — sahifa) olinadi, <option> lar oldindan yuklanmaydi.
 * Javob: {"results":[{"id","text"}], "pagination":{"more":bool}}. Oldindan tanlangan qiymat
 * serverdan <option selected> sifatida berilishi kerak.
 *
 * Istisno: <select data-no-paging="1"> yoki optgroup / tags / ajax / data berilgan select'lar.
 */
(function ($) {
  if (!$ || !$.fn || !$.fn.select2) return;

  var PAGE_SIZE = 20;
  var original = $.fn.select2;

  function normalize(s) {
    return (s == null ? '' : String(s)).toLowerCase();
  }

  function localAjax($el) {
    return {
      data: function (params) {
        return { term: params.term || '', page: params.page || 1 };
      },
      transport: function (request, success) {
        var term = normalize($.trim(request.data.term));
        var page = request.data.page || 1;
        var items = [];

        $el.find('option').each(function () {
          var text = $.trim(this.text);
          if (term && normalize(text).indexOf(term) < 0) return;
          items.push({ id: this.value, text: text, disabled: this.disabled, title: this.title || undefined });
        });

        var start = (page - 1) * PAGE_SIZE;
        success({
          results: items.slice(start, start + PAGE_SIZE),
          pagination: { more: items.length > start + PAGE_SIZE }
        });
        return { abort: function () {} };
      }
    };
  }

  function serverAjax($el) {
    var mapping = {};
    try { mapping = JSON.parse($el.attr('data-ajax-params') || '{}'); } catch (e) {}
    return {
      url: $el.attr('data-ajax-url'),
      delay: 250,
      cache: false,
      data: function (params) {
        var data = { q: params.term || '', page: params.page || 1 };
        Object.keys(mapping).forEach(function (key) {
          var v = $(mapping[key]).val();
          if (v) data[key] = v;
        });
        return data;
      },
      processResults: function (resp) {
        return {
          results: (resp.results || []).map(function (r) {
            return { id: r.id, text: r.text || r.name };
          }),
          pagination: resp.pagination || { more: false }
        };
      }
    };
  }

  function pageable($el, opts) {
    return $el.is('select') &&
      !opts.ajax && !opts.data && !opts.tags && !opts.dataAdapter &&
      !$el.attr('data-no-paging') &&
      $el.find('optgroup').length === 0;
  }

  $.fn.select2 = function (options) {
    if (options === undefined || options === null || typeof options === 'object') {
      var base = options || {};
      return this.each(function () {
        var $el = $(this);
        var opts = base;
        if ($el.is('select') && !base.ajax && $el.attr('data-ajax-url')) {
          opts = $.extend({}, base, { ajax: serverAjax($el) });
        } else if (pageable($el, base)) {
          opts = $.extend({}, base, { ajax: localAjax($el) });
        }
        original.call($el, opts);
      });
    }
    return original.apply(this, arguments);
  };

  $.extend($.fn.select2, original);
})(window.jQuery);
