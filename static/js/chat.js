const CURRENT_EMPLOYEE_ID = window.CHAT_CONFIG.currentEmployeeId;
document.addEventListener("DOMContentLoaded", function () {
  const csrfToken = document.querySelector('#chatSendForm [name=csrfmiddlewaretoken]').value;
  const URLS = {
    conversations: window.CHAT_CONFIG.urls.conversations,
    contacts: window.CHAT_CONFIG.urls.contacts,
    open: window.CHAT_CONFIG.urls.open,
    messages: function (id) { return "/chat/api/" + id + "/messages/"; },
    send: function (id) { return "/chat/api/" + id + "/send/"; },
    edit: function (id) { return "/chat/api/message/" + id + "/edit/"; },
    del: function (id) { return "/chat/api/message/" + id + "/delete/"; },
    hide: function (id) { return "/chat/api/" + id + "/hide/"; },
    createGroup: window.CHAT_CONFIG.urls.createGroup,
    groupMembers: function (id) { return "/chat/api/" + id + "/members/"; },
    groupAddMembers: function (id) { return "/chat/api/" + id + "/members/add/"; },
    groupRemoveMember: function (id, mid) { return "/chat/api/" + id + "/members/" + mid + "/remove/"; },
    groupSetAdmin: function (id, mid) { return "/chat/api/" + id + "/members/" + mid + "/admin/"; },
  };

  let activeConversationId = null;
  let activeOtherId = null;
  let pendingFile = null;
  let ws = null;
  let activeTab = "direct";
  let wsPingTimer = null;
  let convPollTimer = null;
  let conversationsCache = [];

  function esc(s) {
    return $("<div>").text(s || "").html();
  }

  function fmtTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function fmtLastSeen(iso) {
    if (!iso) return "hech qachon kirmagan";
    const d = new Date(iso);
    const diffMin = Math.round((Date.now() - d.getTime()) / 60000);
    if (diffMin < 1) return "hozirgina";
    if (diffMin < 60) return diffMin + " daqiqa oldin";
    if (diffMin < 24 * 60) return Math.floor(diffMin / 60) + " soat oldin";
    return d.toLocaleDateString() + " " + fmtTime(iso);
  }

  // ---------------- Suhbatlar ro'yxati ----------------
  function loadConversations(cb) {
    $.getJSON(URLS.conversations, function (resp) {
      conversationsCache = resp.results || [];
      renderConversations();
      updateActiveHeaderStatus();
      if (cb) cb();
    });
  }

  function avatarColor(seed) {
    const colors = ["#7c5cff", "#17a2b8", "#22c55e", "#ef4444", "#f59e0b", "#8b5cf6", "#0ea5e9", "#ec4899"];
    let hash = 0;
    const s = String(seed || "?");
    for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
    return colors[hash % colors.length];
  }
  function initials(name) {
    const parts = (name || "?").trim().split(/\s+/);
    return ((parts[0] ? parts[0][0] : "") + (parts[1] ? parts[1][0] : "")).toUpperCase() || "?";
  }
  function avatarHtml(name, seed, extraClass) {
    return '<div class="chat-avatar ' + (extraClass || "") + '" style="background:' + avatarColor(seed) + '">' +
           esc(initials(name)) + '</div>';
  }

  function renderConversations() {
    const $list = $("#chatConvList").empty();
    const visible = conversationsCache.filter(function (c) {
      if (c.kind === "saved") return false;
      return activeTab === "group" ? c.kind === "group" : c.kind !== "group";
    });
    const savedConv = conversationsCache.find(function (c) { return c.kind === "saved"; });
    $("#chatSavedBtn")
      .toggleClass("active", !!savedConv && savedConv.id === activeConversationId)
      .off("click")
      .on("click", function () { openSavedMessages(savedConv); });
    visible.forEach(function (c) {
      const dotClass = c.kind === "direct" ? ("dot" + (c.online ? " online" : "")) : "";
      const $item = $(
        '<div class="chat-conv-item" data-id="' + c.id + '">' +
          '<div class="chat-conv-item-row">' +
            avatarHtml(c.title, c.other_id || c.id) +
            '<div>' +
              '<div class="chat-conv-title">' +
                (dotClass ? '<span class="' + dotClass + '"></span>' : '') +
                esc(c.title) +
              '</div>' +
              '<div class="chat-conv-preview">' + esc(c.last_message) + '</div>' +
            '</div>' +
          '</div>' +
          (c.unread_count > 0 ? '<span class="chat-unread-badge">' + c.unread_count + '</span>' : '') +
        '</div>'
      );
      if (c.id === activeConversationId) $item.addClass("active");
      $item.on("click", function () { openConversation(c); });
      $list.append($item);
    });
    updateTabBadges();
  }

  function updateTabBadges() {
    let directUnread = 0, groupUnread = 0;
    conversationsCache.forEach(function (c) {
      if (c.kind === "group") groupUnread += (c.unread_count || 0);
      else directUnread += (c.unread_count || 0);
    });
    $("#chatTabBadgeDirect").text(directUnread).toggleClass("d-none", directUnread === 0);
    $("#chatTabBadgeGroup").text(groupUnread).toggleClass("d-none", groupUnread === 0);
  }

  // ---------------- Yorliqlar (Xodimlar / Guruhlar) ----------------
  $(".chat-tab").on("click", function () {
    activeTab = $(this).data("tab");
    $(".chat-tab").removeClass("active");
    $(this).addClass("active");
    $("#chatDirectSearch").toggleClass("d-none", activeTab !== "direct");
    $("#chatGroupSearch").toggleClass("d-none", activeTab !== "group");
    $("#chatSavedBtn").toggleClass("d-none", activeTab !== "direct");
    renderConversations();
  });

  function updateActiveHeaderStatus() {
    if (!activeConversationId) return;
    const c = conversationsCache.find(function (x) { return x.id === activeConversationId; });
    if (!c) return;
    const $status = $("#chatHeaderStatus");
    if (!$status.length) return;
    if (c.kind === "group") {
      $status.text(c.member_count + " ta a'zo").removeClass("online");
    } else if (c.kind === "direct") {
      if (c.online) $status.text("Onlayn").addClass("online");
      else $status.text("Oxirgi faollik: " + fmtLastSeen(c.last_seen)).removeClass("online");
    }
    if (!$("#chatInfoPanel").hasClass("d-none")) updateInfoStatus();
  }

  // ---------------- Saqlangan xabarlar (Telegram'dagi kabi, o'zi bilan suhbat) ----------------
  function openSavedMessages(savedConv) {
    if (savedConv) {
      openConversation(savedConv);
      return;
    }
    $.post(URLS.open, { target: "saved", csrfmiddlewaretoken: csrfToken }, function (r) {
      loadConversations(function () {
        openConversation({ id: r.conversation_id, title: "Saqlangan xabarlar", kind: "saved", other_id: null });
      });
    });
  }

  // ---------------- Kontakt qidiruv (yangi suhbat) ----------------
  let searchTimer = null;
  $("#chatContactSearch").on("input", function () {
    const q = $(this).val().trim();
    clearTimeout(searchTimer);
    if (!q) { $("#chatContactResults").empty(); return; }
    searchTimer = setTimeout(function () {
      $.getJSON(URLS.contacts, { q: q }, function (resp) {
        const $res = $("#chatContactResults").empty();
        (resp.results || []).forEach(function (emp) {
          const $row = $('<div class="chat-contact-result">' + esc(emp.name) + '</div>');
          $row.on("click", function () {
            $.post(URLS.open, { target: emp.id, csrfmiddlewaretoken: csrfToken }, function (r) {
              $("#chatContactSearch").val("");
              $("#chatContactResults").empty();
              loadConversations(function () {
                openConversation({ id: r.conversation_id, title: emp.name, kind: "direct", other_id: emp.id });
              });
            }).fail(function (xhr) {
              alert((xhr.responseJSON && xhr.responseJSON.error) || "Suhbat ochilmadi (xatolik)");
            });
          });
          $res.append($row);
        });
      });
    }, 250);
  });

  // ---------------- Suhbatni ochish ----------------
  let activeConvData = null;

  function openConversation(c) {
    activeConversationId = c.id;
    activeOtherId = c.other_id || null;
    activeConvData = c;
    $("#chatHeader").html(
      '<button type="button" id="chatBackBtn" class="chat-back-btn" title="Orqaga"><i class="bi bi-arrow-left"></i></button>' +
      (c.kind === "saved"
        ? '<div class="chat-avatar chat-saved-avatar"><i class="bi bi-bookmark-fill"></i></div>'
        : avatarHtml(c.title, c.other_id || c.id)) +
      '<div>' +
        '<div class="chat-header-title">' + esc(c.title) + '</div>' +
        (c.kind !== "ai" && c.kind !== "saved" ? '<div id="chatHeaderStatus" class="chat-header-status"></div>' : '') +
      '</div>' +
      (c.kind !== "ai" && c.kind !== "saved"
        ? '<div class="chat-header-actions"><button type="button" id="chatInfoBtn" title="Ma\'lumot"><i class="bi bi-info-circle"></i></button></div>'
        : "")
    );
    $("#chatBackBtn").on("click", function () { $("#chatWrap").removeClass("mobile-chat-open"); });
    $("#chatInfoBtn").on("click", openInfoPanel);
    $("#chatSendForm").removeClass("d-none");
    $(".chat-conv-item").removeClass("active").filter('[data-id="' + c.id + '"]').addClass("active");
    $("#chatSavedBtn").toggleClass("active", c.kind === "saved");
    $("#chatWrap").addClass("mobile-chat-open");
    loadMessages(c.id);
    updateActiveHeaderStatus();
    if (!$("#chatInfoPanel").hasClass("d-none")) openInfoPanel();
  }

  // ---------------- Ma'lumot paneli (fon + tema + a'zolar + o'chirish) ----------------
  function openInfoPanel() {
    if (!activeConvData) return;
    $("#chatInfoAvatar")
      .css("background", avatarColor(activeOtherId || activeConversationId))
      .text(initials(activeConvData.title));
    $("#chatInfoName").text(activeConvData.title);
    updateInfoStatus();
    $("#chatMemberAddWrap").addClass("d-none");
    $("#chatMemberAddSearch").val("");
    $("#chatMemberAddResults").empty();
    if (activeConvData.kind === "group") {
      $("#chatMemberSection").removeClass("d-none");
      loadGroupMembers();
    } else {
      $("#chatMemberSection").addClass("d-none");
    }
    $("#chatInfoPanel").removeClass("d-none");
  }

  let currentGroupMemberIds = new Set();

  function loadGroupMembers() {
    $.getJSON(URLS.groupMembers(activeConversationId), function (resp) {
      const amAdmin = resp.am_admin;
      const amCreator = resp.am_creator;
      currentGroupMemberIds = new Set(resp.results.map(function (m) { return m.id; }));
      const $list = $("#chatMemberList").empty();
      resp.results.forEach(function (m) {
        const badge = m.is_creator
          ? '<span class="chat-member-admin-badge chat-member-creator-badge">yaratuvchi</span>'
          : (m.is_admin ? '<span class="chat-member-admin-badge">admin</span>' : '');
        const $row = $(
          '<div class="chat-member-row">' +
            avatarHtml(m.name, m.id) +
            badge +
            '<span class="chat-member-name">' + esc(m.name) + (m.is_me ? " (siz)" : "") + '</span>' +
            '<span class="chat-member-actions"></span>' +
          '</div>'
        );
        const $actions = $row.find(".chat-member-actions");
        // Admin tayinlash/tushirish - faqat yaratuvchi (super admin) qila oladi.
        if (amCreator && !m.is_creator && !m.is_me) {
          const $adminBtn = $('<button type="button" title="' + (m.is_admin ? "Admindan tushirish" : "Admin qilish") + '"><i class="bi bi-star' + (m.is_admin ? "-fill" : "") + '"></i></button>');
          $adminBtn.on("click", function () { toggleGroupAdmin(m.id, !m.is_admin); });
          $actions.append($adminBtn);
        }
        // Chiqarish - o'zini har doim, yaratuvchini hech kim, adminni faqat
        // yaratuvchi, oddiy a'zoni admin yoki yaratuvchi chiqara oladi.
        const canRemove = m.is_me || (!m.is_creator && (amCreator || (amAdmin && !m.is_admin)));
        if (canRemove) {
          const $rmBtn = $('<button type="button" title="' + (m.is_me ? "Guruhdan chiqish" : "Guruhdan chiqarish") + '"><i class="bi bi-' + (m.is_me ? "box-arrow-right" : "x-lg") + '"></i></button>');
          $rmBtn.on("click", function () { removeGroupMember(m.id, m.is_me); });
          $actions.append($rmBtn);
        }
        $list.append($row);
      });

      $("#chatMemberAddWrap").toggleClass("d-none", !amAdmin);
      if (amAdmin && !$("#chatMemberAddToggle").length) {
        const $toggle = $('<button type="button" id="chatMemberAddToggle" class="chat-member-add-toggle"><i class="bi bi-plus-lg"></i> A\'zo qo\'shish</button>');
        $toggle.on("click", function () { $("#chatMemberAddWrap").removeClass("d-none"); $("#chatMemberAddSearch").trigger("focus"); });
        $("#chatMemberSection").find(".chat-info-section-title").after($toggle);
      }
    });
  }

  function toggleGroupAdmin(memberId, makeAdmin) {
    $.post(URLS.groupSetAdmin(activeConversationId, memberId), { is_admin: makeAdmin ? "1" : "0", csrfmiddlewaretoken: csrfToken }, function () {
      loadGroupMembers();
    }).fail(function (xhr) {
      alert((xhr.responseJSON && xhr.responseJSON.error) || "Xatolik yuz berdi");
    });
  }

  function removeGroupMember(memberId, isMe) {
    const msg = isMe ? "Guruhdan chiqmoqchimisiz?" : "Bu a'zoni guruhdan chiqarmoqchimisiz?";
    if (!confirm(msg)) return;
    $.post(URLS.groupRemoveMember(activeConversationId, memberId), { csrfmiddlewaretoken: csrfToken }, function () {
      if (isMe) {
        $("#chatInfoPanel").addClass("d-none");
        activeConversationId = null;
        $("#chatSendForm").addClass("d-none");
        $("#chatHeader").html('<div class="chat-header-title">Suhbat tanlang</div>');
        $("#chatMessages").html('<div class="chat-empty">Chapdan suhbat tanlang yoki yangisini boshlang</div>');
        $("#chatWrap").removeClass("mobile-chat-open");
        loadConversations();
      } else {
        loadGroupMembers();
        loadConversations();
      }
    }).fail(function (xhr) {
      alert((xhr.responseJSON && xhr.responseJSON.error) || "Xatolik yuz berdi");
    });
  }

  let memberAddTimer = null;
  $("#chatMemberAddSearch").on("input", function () {
    clearTimeout(memberAddTimer);
    const q = $(this).val().trim();
    if (!q) { $("#chatMemberAddResults").empty(); return; }
    memberAddTimer = setTimeout(function () {
      $.getJSON(URLS.contacts, { q: q }, function (resp) {
        const $res = $("#chatMemberAddResults").empty();
        // Guruhda allaqachon bor a'zolar qidiruv natijasida chiqmaydi.
        const filtered = (resp.results || []).filter(function (emp) { return !currentGroupMemberIds.has(emp.id); });
        filtered.forEach(function (emp) {
          const $row = $('<div class="chat-contact-result">' + esc(emp.name) + '</div>');
          $row.on("click", function () {
            $.post(URLS.groupAddMembers(activeConversationId), { "members[]": emp.id, csrfmiddlewaretoken: csrfToken }, function () {
              $("#chatMemberAddSearch").val("");
              $("#chatMemberAddResults").empty();
              loadGroupMembers();
              loadConversations();
            });
          });
          $res.append($row);
        });
      });
    }, 250);
  });
  function updateInfoStatus() {
    const c = conversationsCache.find(function (x) { return x.id === activeConversationId; }) || activeConvData;
    const $s = $("#chatInfoStatus");
    if (c && c.kind === "group") {
      $s.text(c.member_count + " ta a'zo").removeClass("online");
    } else if (c && c.online) {
      $s.text("Onlayn").addClass("online");
    } else {
      $s.text("Oxirgi faollik: " + fmtLastSeen(c ? c.last_seen : null)).removeClass("online");
    }
    $("#chatHideBtn").html(
      '<i class="bi bi-box-arrow-right me-1"></i>' +
      (c && c.kind === "group" ? "Guruhdan chiqish" : "Chatni o'chirish")
    );
  }
  $("#chatInfoClose").on("click", function () { $("#chatInfoPanel").addClass("d-none"); });

  $("#chatHideBtn").on("click", function () {
    if (!activeConversationId) return;
    const c = conversationsCache.find(function (x) { return x.id === activeConversationId; }) || activeConvData;
    if (c && c.kind === "group") {
      removeGroupMember(CURRENT_EMPLOYEE_ID, true);
      return;
    }
    if (!confirm("Suhbatni o'chirmoqchimisiz? Boshqalarga ta'sir qilmaydi.")) return;
    $.post(URLS.hide(activeConversationId), { csrfmiddlewaretoken: csrfToken }, function () {
      $("#chatInfoPanel").addClass("d-none");
      activeConversationId = null;
      $("#chatSendForm").addClass("d-none");
      $("#chatHeader").html('<div class="chat-header-title">Suhbat tanlang</div>');
      $("#chatMessages").html('<div class="chat-empty">Chapdan suhbat tanlang yoki yangisini boshlang</div>');
      $("#chatWrap").removeClass("mobile-chat-open");
      loadConversations();
    });
  });

  // ---------------- Guruh yaratish ----------------
  let selectedMemberIds = new Set();

  function renderGroupMemberList(q) {
    $.getJSON(URLS.contacts, { q: q || "" }, function (resp) {
      const $list = $("#chatGroupMemberList").empty();
      (resp.results || []).forEach(function (emp) {
        const checked = selectedMemberIds.has(emp.id);
        const $row = $(
          '<div class="chat-group-member-row" data-id="' + emp.id + '">' +
            '<input type="checkbox" ' + (checked ? "checked" : "") + '>' +
            avatarHtml(emp.name, emp.id) +
            '<span>' + esc(emp.name) + '</span>' +
          '</div>'
        );
        $row.on("click", function () {
          const id = emp.id;
          if (selectedMemberIds.has(id)) selectedMemberIds.delete(id);
          else selectedMemberIds.add(id);
          $row.find("input").prop("checked", selectedMemberIds.has(id));
          $("#chatGroupSelectedCount").text(selectedMemberIds.size + " ta xodim tanlandi");
        });
        $list.append($row);
      });
    });
  }

  $("#chatNewGroupBtn").on("click", function () {
    selectedMemberIds = new Set();
    $("#chatGroupName").val("");
    $("#chatGroupMemberSearch").val("");
    $("#chatGroupSelectedCount").text("0 ta xodim tanlandi");
    renderGroupMemberList("");
    $("#chatGroupModal").removeClass("d-none");
  });
  $("#chatGroupModalClose").on("click", function () { $("#chatGroupModal").addClass("d-none"); });

  let groupSearchTimer = null;
  $("#chatGroupMemberSearch").on("input", function () {
    clearTimeout(groupSearchTimer);
    const q = $(this).val().trim();
    groupSearchTimer = setTimeout(function () { renderGroupMemberList(q); }, 250);
  });

  $("#chatGroupCreateBtn").on("click", function () {
    const name = $("#chatGroupName").val().trim();
    if (!name) { alert("Guruh nomini kiriting"); return; }
    if (selectedMemberIds.size < 2) { alert("Kamida 2 ta xodim tanlang"); return; }

    const fd = new FormData();
    fd.append("csrfmiddlewaretoken", csrfToken);
    fd.append("name", name);
    selectedMemberIds.forEach(function (id) { fd.append("members[]", id); });

    $.ajax({
      url: URLS.createGroup, type: "POST", data: fd, processData: false, contentType: false,
      success: function (r) {
        $("#chatGroupModal").addClass("d-none");
        activeTab = "group";
        $(".chat-tab").removeClass("active").filter('[data-tab="group"]').addClass("active");
        $("#chatDirectSearch").addClass("d-none");
        $("#chatGroupSearch").removeClass("d-none");
        loadConversations(function () {
          const c = conversationsCache.find(function (x) { return x.id === r.conversation_id; });
          if (c) openConversation(c);
        });
      },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.error) || "Guruh yaratilmadi (xatolik)");
      }
    });
  });

  // ---------------- Fon (wallpaper) tanlovi ----------------
  const WALLPAPER_KEY = "chat_wallpaper";
  const THEME_KEY = "chat_theme_color";

  function applyWallpaper(w) {
    if (w && w !== "plain") $("#chatMessages").attr("data-wallpaper", w);
    else $("#chatMessages").removeAttr("data-wallpaper");
    $(".chat-wallpaper-swatch").removeClass("active").filter('[data-w="' + (w || "plain") + '"]').addClass("active");
  }
  function applyThemeColor(c) {
    if (c) $("#chatWrap")[0].style.setProperty("--chat-accent", c);
    $(".chat-theme-swatch").removeClass("active").filter('[data-c="' + c + '"]').addClass("active");
  }

  $(".chat-wallpaper-swatch").on("click", function () {
    const w = $(this).data("w");
    applyWallpaper(w);
    try { localStorage.setItem(WALLPAPER_KEY, w); } catch (e) {}
  });
  $(".chat-theme-swatch").on("click", function () {
    const c = $(this).data("c");
    applyThemeColor(c);
    try { localStorage.setItem(THEME_KEY, c); } catch (e) {}
  });

  (function initAppearance() {
    let savedWallpaper = "plain", savedTheme = "";
    try {
      savedWallpaper = localStorage.getItem(WALLPAPER_KEY) || "plain";
      savedTheme = localStorage.getItem(THEME_KEY) || "";
    } catch (e) {}
    applyWallpaper(savedWallpaper);
    if (savedTheme) applyThemeColor(savedTheme);
  })();

  let lastMessagesJson = null;

  function renderMessageList(results) {
    const $box = $("#chatMessages");
    const nearBottom = $box[0].scrollHeight - $box.scrollTop() - $box.outerHeight() < 80;
    $box.empty();
    (results || []).forEach(function (m) { appendMessage(m); });
    if (nearBottom) $box.scrollTop($box[0].scrollHeight);
  }

  function loadMessages(id) {
    $.getJSON(URLS.messages(id), function (resp) {
      lastMessagesJson = JSON.stringify(resp.results || []);
      renderMessageList(resp.results);
      loadConversations();
    });
  }

  // WebSocket biror sababga ko'ra ulanmasa/uzilib qolsa ham (server ASGI
  // rejimida ishlamasa, proksi WS'ni to'smasa va h.k.) ochiq suhbat
  // "qotib" qolmasligi uchun zaxira sifatida davriy so'rov - o'zgarish
  // bo'lmasa qayta chizmaydi (ekran "sakramaydi").
  setInterval(function () {
    if (!activeConversationId) return;
    $.getJSON(URLS.messages(activeConversationId), function (resp) {
      const json = JSON.stringify(resp.results || []);
      if (json === lastMessagesJson) return;
      lastMessagesJson = json;
      renderMessageList(resp.results);
      loadConversations();
    });
  }, 4000);

  function tickHtml(m) {
    if (m.is_ai) return "";
    const mine = String(m.sender_id) === String(CURRENT_EMPLOYEE_ID);
    if (!mine) return "";
    return m.read_at
      ? '<i class="bi bi-check2-all" title="O\'qildi"></i>'
      : '<i class="bi bi-check2" title="Yuborildi"></i>';
  }

  function bodyHtml(m) {
    // Eslatma: o'chirilgan xabarlar server tomonidan umuman yuborilmaydi
    // (chat_messages `is_deleted=False` bilan filtrlaydi), shu sabab bu yerda
    // "o'chirildi" kabi maxsus holatni ko'rsatish shart emas.
    let html = "";
    if (m.attachment_url) {
      if (m.is_image) {
        html += '<a href="' + m.attachment_url + '" target="_blank" rel="noopener">' +
                '<img class="chat-bubble-img" src="' + m.attachment_url + '"></a>';
      } else {
        html += '<a class="chat-bubble-file" href="' + m.attachment_url + '" target="_blank" rel="noopener">' +
                '<i class="bi bi-file-earmark-arrow-down fs-5"></i><span>' + esc(m.attachment_name || "Fayl") + '</span></a>';
      }
    }
    if (m.body) html += '<span class="chat-bubble-body">' + esc(m.body) + '</span>';
    return html;
  }

  function appendMessage(m) {
    // Dublikatdan saqlanish: bir xil xabar ham "yuborildi" javobidan (optimistik
    // ko'rsatish), ham WebSocket push orqali kelishi mumkin (server xabarni
    // yuboruvchining o'ziga ham jonli push qiladi - boshqa qurilma/oynasi
    // sinxron bo'lishi uchun). Xabar allaqachon ekranda bo'lsa - qayta qo'shilmaydi.
    if ($('#chatMessages .chat-row[data-msg-id="' + m.id + '"]').length) return;

    const mine = !m.is_ai && String(m.sender_id) === String(CURRENT_EMPLOYEE_ID);
    const $row = $('<div class="chat-row ' + (mine ? "chat-row-mine" : "chat-row-theirs") + '" data-msg-id="' + m.id + '"></div>');

    if (mine && !m.is_deleted) {
      const $actions = $(
        '<div class="chat-msg-actions can-edit">' +
          (m.attachment_url ? "" : '<button type="button" class="js-msg-edit" title="Tahrirlash"><i class="bi bi-pencil"></i></button>') +
          '<button type="button" class="js-msg-delete" title="O\'chirish"><i class="bi bi-trash"></i></button>' +
        '</div>'
      );
      $actions.find(".js-msg-edit").on("click", function () { startEdit(m.id); });
      $actions.find(".js-msg-delete").on("click", function () { deleteMessage(m.id); });
      $row.append($actions);
    }

    const isGroup = activeConvData && activeConvData.kind === "group";
    const $bubble = $(
      '<div class="chat-bubble ' + (mine ? "chat-bubble-mine" : "chat-bubble-theirs") + '">' +
        (isGroup && !mine ? '<div class="chat-bubble-sender">' + esc(m.sender_name) + '</div>' : "") +
        bodyHtml(m) +
        '<span class="chat-bubble-meta">' +
          (m.is_edited && !m.is_deleted ? '<span class="chat-bubble-edited">tahrirlangan</span>' : "") +
          (m.is_ai ? "AI - " : "") + fmtTime(m.date_creat) + " " + tickHtml(m) +
        '</span>' +
      '</div>'
    );
    $row.append($bubble);
    $("#chatMessages").append($row);
  }

  function startEdit(msgId) {
    const $row = $('.chat-row[data-msg-id="' + msgId + '"]');
    const $bubbleBody = $row.find(".chat-bubble-body");
    const current = $bubbleBody.length ? $bubbleBody.text() : "";
    const val = prompt("Xabarni tahrirlash:", current);
    if (val === null) return;
    const text = val.trim();
    if (!text) return;
    $.post(URLS.edit(msgId), { body: text, csrfmiddlewaretoken: csrfToken }, function (resp) {
      replaceMessage(resp.message);
    }).fail(function (xhr) {
      alert((xhr.responseJSON && xhr.responseJSON.error) || "Xatolik yuz berdi");
    });
  }

  function deleteMessage(msgId) {
    if (!confirm("Xabarni o'chirishni tasdiqlaysizmi?")) return;
    $.post(URLS.del(msgId), { csrfmiddlewaretoken: csrfToken }, function () {
      $('.chat-row[data-msg-id="' + msgId + '"]').remove();
      loadConversations();
    });
  }

  function replaceMessage(m) {
    $('.chat-row[data-msg-id="' + m.id + '"]').remove();
    // eski o'rniga qo'ymaymiz - oddiylik uchun oxiriga qo'shamiz, chunki
    // tahrirlash sana tartibini o'zgartirmaydi va foydalanuvchi ko'zi bilan
    // ko'rgan holatda bo'ladi. To'g'ri joyga qo'yish uchun ro'yxatni to'liq
    // qayta yuklaymiz - ishonchliroq:
    loadMessages(activeConversationId);
  }

  function markTicksRead(messageIds) {
    (messageIds || []).forEach(function (id) {
      const $row = $('.chat-row[data-msg-id="' + id + '"]');
      $row.find(".chat-bubble-meta i").removeClass("bi-check2").addClass("bi-check2-all").attr("title", "O'qildi");
    });
  }

  // ---------------- Fayl biriktirish ----------------
  $("#chatAttachBtn").on("click", function () { $("#chatFileInput").trigger("click"); });
  $("#chatFileInput").on("change", function () {
    const f = this.files[0];
    if (!f) return;
    pendingFile = f;
    $("#chatAttachName").text(f.name);
    $("#chatAttachPreview").removeClass("d-none");
  });
  $("#chatAttachRemove").on("click", function () {
    pendingFile = null;
    $("#chatFileInput").val("");
    $("#chatAttachPreview").addClass("d-none");
  });

  // ---------------- Smayliklar (kengaytirilgan to'plam) ----------------
  const EMOJIS = [
    // Yuz ifodalari
    "😀","😃","😄","😁","😆","😅","🤣","😂","🙂","🙃",
    "😉","😊","😇","🥰","😍","🤩","😘","😗","😚","😙",
    "😋","😛","😜","🤪","😝","🤑","🤗","🤭","🤫","🤔",
    "🤐","🤨","😐","😑","😶","😏","😒","🙄","😬","🤥",
    "😌","😔","😪","🤤","😴","😷","🤒","🤕","🤢","🤮",
    "🥵","🥶","🥴","😵","🤯","🤠","🥳","😎","🤓","🧐",
    "😕","😟","🙁","☹️","😮","😯","😲","😳","🥺","😦",
    "😧","😨","😰","😥","😢","😭","😱","😖","😣","😞",
    "😓","😩","😫","🥱","😤","😡","😠","🤬","😈","👿",
    // Imo-ishoralar va odamlar
    "👋","🤚","🖐️","✋","🖖","👌","🤌","🤏","✌️","🤞",
    "🤟","🤘","🤙","👈","👉","👆","🖕","👇","☝️","👍",
    "👎","✊","👊","🤛","🤜","👏","🙌","👐","🤲","🙏",
    "💪","🦾","🫶","🤝","💅","🧠",
    // Yuraklar va belgilar
    "❤️","🧡","💛","💚","💙","💜","🖤","🤍","🤎","💔",
    "❣️","💕","💞","💓","💗","💖","💘","💝","💯","✅",
    "❌","❗","❓","⚠️","🔥","✨","🎉","🎊","🎈","🎁",
    "🏆","🥇","⭐","🌟","💤","💢","💬",
    // Odamlar/kasblar (qisqa)
    "🧑","👨","👩","🧓","👴","👵","👶","🧑‍💻","👨‍💼","👩‍💼",
    "🕵️","👮","🧑‍⚕️","👨‍🏫","👩‍🏫","🧑‍🔧",
    // Hayvonlar va tabiat
    "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🐯",
    "🦁","🐮","🐷","🐸","🐵","🐔","🐧","🐦","🦄","🐝",
    "🌸","🌼","🌻","🌈","☀️","⛅","☁️","🌧️","❄️","🌙",
    // Ovqat va ichimlik
    "🍏","🍎","🍊","🍋","🍌","🍉","🍇","🍓","🍒","🍑",
    "🍕","🍔","🍟","🌭","🥪","🌮","🍣","🍜","🍦","🍩",
    "🍪","🎂","☕","🍵","🥤","🍺","🍷",
    // Faoliyat va sport
    "⚽","🏀","🏈","⚾","🎾","🏐","🏓","🎯","🎮","🎲",
    "🎸","🎹","🎤","🎧","🚴","🏃","🧘",
    // Sayohat va transport
    "🚗","🚕","🚌","🚀","✈️","🚲","⛵","🚦","🗺️","🏠",
    // Ish/ofis buyumlari
    "💻","📱","⌚","📷","💡","🔋","📎","📌","📅","📞",
    "✉️","📩","📝","📚","🔑","🔒","🔓","💰","💳","🎓",
  ];
  const $emojiPanel = $("#chatEmojiPanel");
  if (!$emojiPanel.children().length) {
    EMOJIS.forEach(function (e) { $emojiPanel.append($("<span>").text(e)); });
  }
  $emojiPanel.on("click", "span", function () {
    const input = document.getElementById("chatInput");
    const start = input.selectionStart || input.value.length;
    const end = input.selectionEnd || input.value.length;
    const val = input.value;
    input.value = val.slice(0, start) + $(this).text() + val.slice(end);
    const pos = start + $(this).text().length;
    input.focus();
    input.setSelectionRange(pos, pos);
  });
  $("#chatEmojiBtn").on("click", function (e) {
    e.stopPropagation();
    $emojiPanel.toggleClass("d-none");
  });
  $(document).on("click", function (e) {
    if (!$emojiPanel.hasClass("d-none") && !$(e.target).closest("#chatEmojiPanel, #chatEmojiBtn").length) {
      $emojiPanel.addClass("d-none");
    }
  });

  // ---------------- Xabar yuborish ----------------
  $("#chatSendForm").on("submit", function (e) {
    e.preventDefault();
    if (!activeConversationId) return;
    const text = $("#chatInput").val().trim();
    if (!text && !pendingFile) return;

    const fd = new FormData();
    fd.append("csrfmiddlewaretoken", csrfToken);
    if (text) fd.append("body", text);
    if (pendingFile) fd.append("attachment", pendingFile);

    $("#chatInput").val("");
    const sentFile = pendingFile;
    pendingFile = null;
    $("#chatFileInput").val("");
    $("#chatAttachPreview").addClass("d-none");

    $.ajax({
      url: URLS.send(activeConversationId),
      type: "POST",
      data: fd,
      processData: false,
      contentType: false,
      success: function (resp) {
        appendMessage(resp.message);
        const $box = $("#chatMessages");
        $box.scrollTop($box[0].scrollHeight);
        loadConversations();
      },
      error: function (xhr) {
        alert((xhr.responseJSON && xhr.responseJSON.error) || "Xatolik yuz berdi");
      }
    });
  });

  // ---------------- WebSocket (jonli push + onlayn holat) ----------------
  function connectWs() {
    if (ws) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    try {
      ws = new WebSocket(proto + "//" + window.location.host + "/ws/chat/");
      ws.onopen = function () {
        wsPingTimer = setInterval(function () {
          if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
        }, 20000);
      };
      ws.onmessage = function (evt) {
        const data = JSON.parse(evt.data);
        if (data.type === "message") {
          const m = data.message;
          if (m.conversation_id === activeConversationId) {
            appendMessage(m);
            const $box = $("#chatMessages");
            $box.scrollTop($box[0].scrollHeight);
          }
          loadConversations();
        } else if (data.type === "delete") {
          // O'chirilgan xabar izsiz olib tashlanadi - "o'chirildi" degan
          // yozuv chiqmaydi.
          $('.chat-row[data-msg-id="' + data.message.id + '"]').remove();
          loadConversations();
        } else if (data.type === "edit") {
          if (data.message.conversation_id === activeConversationId) {
            loadMessages(activeConversationId);
          } else {
            loadConversations();
          }
        } else if (data.type === "read") {
          if (data.conversation_id === activeConversationId) {
            markTicksRead(data.message_ids);
          }
        } else if (data.type === "group_update") {
          loadConversations();
          if (data.conversation_id === activeConversationId) {
            updateActiveHeaderStatus();
            if (!$("#chatInfoPanel").hasClass("d-none")) loadGroupMembers();
          }
        }
      };
      ws.onclose = function () { ws = null; clearInterval(wsPingTimer); };
      ws.onerror = function () { ws = null; clearInterval(wsPingTimer); };
    } catch (e) {
      ws = null;
    }
  }

  connectWs();
  loadConversations();
  convPollTimer = setInterval(loadConversations, 20000);
});
