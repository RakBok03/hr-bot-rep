(function () {
  function apiHeaders() {
    return (window.HRTelegramWebApp && window.HRTelegramWebApp.getApiHeaders()) || {};
  }

  window.apiFetch = function (url, options) {
    options = options || {};
    options.headers = Object.assign({}, options.headers, apiHeaders());
    return fetch(url, options);
  };
})();

(function initTheme() {
  var stored = typeof localStorage !== "undefined" && localStorage.getItem("hr-theme");
  var theme = stored === "light" || stored === "dark" ? stored : "dark";
  if (document.documentElement) {
    document.documentElement.dataset.theme = theme;
  }
  if (typeof localStorage !== "undefined" && !stored) {
    localStorage.setItem("hr-theme", theme);
  }
})();

function getTheme() {
  return document.documentElement.getAttribute("data-theme") || "dark";
}

function setTheme(theme) {
  if (theme !== "light" && theme !== "dark") return;
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("hr-theme", theme);
  } catch (e) {}
}

function toggleTheme() {
  setTheme(getTheme() === "dark" ? "light" : "dark");
}

document.addEventListener("DOMContentLoaded", () => {
  const screens = document.querySelectorAll(".screen");
  const bottomNav = document.getElementById("bottom-nav");
  const navItems = bottomNav ? bottomNav.querySelectorAll(".bottom-nav__item") : [];

  const wizard = {
    el: document.getElementById("request-wizard"),
    titleEl: document.getElementById("wizard-step-title"),
    progressEl: document.getElementById("wizard-step-progress"),
    progressFillEl: document.getElementById("wizard-progress-fill"),
    progressCaptionEl: document.getElementById("wizard-progress-caption"),
    bodyEl: document.getElementById("wizard-body"),
    backBtn: document.getElementById("wizard-back"),
    nextBtn: document.getElementById("wizard-next"),
    cancelBtn: document.getElementById("wizard-cancel"),
    currentStep: 0,
    steps: [
      { id: "location", title: "Площадка" },
      { id: "position", title: "Должность" },
      { id: "headcount", title: "Количество человек" },
      { id: "schedule", title: "График работы" },
      { id: "workTime", title: "Время работы" },
      { id: "salary", title: "Оклад / ставка" },
      { id: "employmentType", title: "Вид оформления" },
      { id: "requirements", title: "Требования и обязанности" },
      { id: "startDate", title: "Желаемая дата выхода" },
      { id: "contact", title: "Контактное лицо" },
      { id: "candidateApproval", title: "Необходимость согласования кандидатов" },
      { id: "summary", title: "Предпросмотр заявки" },
    ],
    data: {
      location: null,
      location_custom: "",
      position: null,
      position_custom: "",
      headcount: 1,
      schedule: null,
      schedule_custom: "",
      workTimeFrom: "",
      workTimeTo: "",
      salary: "",
      salaryType: "fixed",
      employmentType: null,
      requirements: "",
      startDate: "",
      contactPerson: "",
      candidateApprovalRequired: null,
    },
  };

  let meUserCache = null;
  function updateUnregisteredBanner(data) {
    var block = document.getElementById("unregistered-banner");
    var shell = document.querySelector(".app-shell");
    if (!block) return;
    var show = data && data.from_telegram === true && data.registered === false;
    block.hidden = !show;
    if (shell) shell.setAttribute("aria-hidden", show ? "true" : "false");
  }
  (window.apiFetch || fetch)("/api/me")
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (data) {
        meUserCache = data;
        updateUnregisteredBanner(data);
        try {
          var u = data.user || {};
          var initialsEl = document.getElementById("header-avatar-initials");
          var avatarEl = document.getElementById("header-avatar");
          var first = (u.first_name || "").trim();
          var last = (u.last_name || "").trim();
          var initials = ((first[0] || "") + (last[0] || "")).toUpperCase() || "U";
          if (initialsEl) initialsEl.textContent = initials;
          var photoUrl = (u.photo_url || "").trim();
          if (avatarEl && photoUrl) {
            avatarEl.style.backgroundImage = 'url("' + photoUrl.replace(/"/g, "%22") + '")';
            avatarEl.style.backgroundSize = "cover";
            avatarEl.style.backgroundPosition = "center";
            avatarEl.style.backgroundRepeat = "no-repeat";
            if (initialsEl) initialsEl.style.display = "none";
          } else {
            if (avatarEl) avatarEl.style.backgroundImage = "";
            if (initialsEl) initialsEl.style.display = "";
          }
        } catch (e) {}
      }
    })
    .catch(function () {});

  function showScreen(target) {
    screens.forEach((screen) => {
      const name = screen.getAttribute("data-screen");
      screen.classList.toggle("screen--active", name === target);
    });
    updateHeaderTitle(target, null);
  }

  function updateHeaderTitle(screen, view) {
    const el = document.getElementById("header-title");
    if (!el) return;
    if (screen === "requests") {
      el.textContent = view === "list" ? "Мои заявки" : "Создание заявки";
    } else if (screen === "help") {
      el.textContent = "Помощь";
    } else if (screen === "candidates") {
      el.textContent = "Кандидаты";
    } else if (screen === "profile") {
      el.textContent = "Профиль";
    } else if (screen === "dashboard") {
      el.textContent = "Дашборд";
    }
  }

  function setActiveNavItem(targetScreen, view) {
    if (!navItems.length) return;
    navItems.forEach((btn) => {
      const t = btn.getAttribute("data-target");
      const v = btn.getAttribute("data-view");
      const active = t === targetScreen && (view == null ? !v : v === view);
      btn.classList.toggle("bottom-nav__item--active", !!active);
    });
  }

  const requestsCreateView = document.getElementById("requests-create-view");
  const requestsListView = document.getElementById("requests-list-view");

  function showRequestsView(view) {
    if (!requestsCreateView || !requestsListView) return;
    const isList = view === "list";
    requestsCreateView.classList.toggle("requests-view--hidden", isList);
    requestsListView.classList.toggle("requests-view--hidden", !isList);
    if (isList) renderMyRequests();
    else if (wizard.el) startWizard();
    setActiveNavItem("requests", view);
    updateHeaderTitle("requests", view);
  }

  var lastRequestsList = [];
  var currentRequestsFilter = "actual";
  var archiveCalendarYear = null;
  var archiveCalendarMonth = null;

  var ARCHIVE_MONTH_NAMES = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];

  function getYearMonthFromDateStr(dateStr) {
    if (!dateStr || !String(dateStr).trim()) return null;
    var part = String(dateStr).trim().split(/\s/)[0];
    var parts = part.split(".");
    if (parts.length !== 3) return null;
    var mm = parseInt(parts[1], 10);
    var yyyy = parseInt(parts[2], 10);
    if (isNaN(mm) || isNaN(yyyy) || mm < 1 || mm > 12) return null;
    return { year: yyyy, month: mm };
  }

  function getCurrentYearMonth() {
    var now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  }

  function ensureArchiveCalendarState() {
    if (archiveCalendarYear !== null && archiveCalendarMonth !== null) return;
    var cur = getCurrentYearMonth();
    archiveCalendarYear = cur.year;
    archiveCalendarMonth = cur.month;
  }

  function requestDateInMonth(r, year, month) {
    var dateStr = r.closed_at || r.created_at || "";
    var ym = getYearMonthFromDateStr(dateStr);
    return ym && ym.year === year && ym.month === month;
  }

  function getStatusEmoji(status) {
    if (status === "new") return "\uD83C\uDD95";
    if (status === "in_progress") return "\u231B";
    return "";
  }

  function getArchiveStatusEmoji(status) {
    if (status === "cancelled") return "\u274C";
    if (status === "closed") return "\u2705";
    return "";
  }

  function renderRequestsList(requests, isArchive) {
    var container = document.getElementById("my-requests-content");
    if (!container) return;
    container.innerHTML = requests
      .map(function (r) {
        var statusText = r.status === "new" ? "Новая" : (r.status === "in_progress" ? "В работе" : (r.status === "cancelled" ? "Отменена" : (r.status === "closed" ? "Закрыта" : (r.status || "—"))));
        var statusEmoji = isArchive ? getArchiveStatusEmoji(r.status) : getStatusEmoji(r.status);
        var createdStr = formatDateDisplay(r.created_at);
        var startStr = formatDateDisplay(r.start_date);
        var headcountStr = r.headcount != null ? r.headcount + " чел." : "—";
        var badgeHtml = statusEmoji ? '<span class="my-requests-card__status" aria-hidden="true">' + statusEmoji + "</span>" : "";
        return (
          '<div class="my-requests-card" data-id="' + r.id + '">' +
          badgeHtml +
          '<div class="my-requests-card__title">' + escapeHtml(r.position || "Заявка") + '</div>' +
          '<div class="my-requests-card__meta">' + escapeHtml(r.venue || "") + ' · ' + escapeHtml(statusText) + '</div>' +
          '<div class="my-requests-card__count">Кол-во: ' + escapeHtml(headcountStr) + '</div>' +
          '<div class="my-requests-card__dates">' +
          '<div class="my-requests-card__date-row">Дата создания: ' + escapeHtml(createdStr) + '</div>' +
          '<div class="my-requests-card__date-row">Дата выхода: ' + escapeHtml(startStr) + '</div>' +
          '</div>' +
          '</div>'
        );
      })
      .join("");
  }

  function applyRequestsFilterAndRender() {
    var container = document.getElementById("my-requests-content");
    if (!container) return;
    updateRequestsArchiveCalendarUI();
    var filtered = currentRequestsFilter === "archive"
      ? lastRequestsList.filter(function (r) { return r.status === "closed" || r.status === "cancelled"; })
      : lastRequestsList.filter(function (r) { return r.status !== "closed" && r.status !== "cancelled"; });
    if (currentRequestsFilter === "archive") {
      ensureArchiveCalendarState();
      filtered = filtered.filter(function (r) { return requestDateInMonth(r, archiveCalendarYear, archiveCalendarMonth); });
      if (filtered.length > 0) {
        filtered = filtered.slice().sort(function (a, b) {
          var da = a.closed_at || "";
          var db = b.closed_at || "";
          return da > db ? -1 : da < db ? 1 : 0;
        });
      }
    }
    if (filtered.length === 0) {
      if (currentRequestsFilter === "archive") {
        container.innerHTML =
          '<div class="my-requests-empty">' +
          '<p class="my-requests-empty__text">В архиве пока нет закрытых заявок</p>' +
          '<p class="my-requests-empty__hint">Закрытые заявки появятся здесь после закрытия.</p>' +
          '</div>';
      } else {
        container.innerHTML =
          '<div class="my-requests-empty">' +
          '<p class="my-requests-empty__text">Заявок нет</p>' +
          '<p class="my-requests-empty__hint">Создайте заявку на подбор, нажав «Создать» внизу.</p>' +
          '</div>';
      }
      return;
    }
    renderRequestsList(filtered, currentRequestsFilter === "archive");
  }

  function renderMyRequests() {
    var container = document.getElementById("my-requests-content");
    if (!container) return;
    container.innerHTML = '<div class="my-requests-loading">Загрузка…</div>';
    var url = window.HR_ADMIN_MODE ? "/api/admin/requests" : "/api/requests";
    (window.apiFetch || fetch)(url)
      .then(function (res) {
        if (!res.ok) return { requests: [] };
        return res.json();
      })
      .then(function (data) {
        var requests = (data && data.requests) ? data.requests : [];
        lastRequestsList = requests;
        if (lastRequestsList.length === 0) {
          container.innerHTML =
            '<div class="my-requests-empty">' +
            '<p class="my-requests-empty__text">Заявок нет</p>' +
            '<p class="my-requests-empty__hint">Создайте заявку на подбор, нажав «Создать» внизу.</p>' +
            '</div>';
          return;
        }
        applyRequestsFilterAndRender();
      })
      .catch(function () {
        container.innerHTML =
          '<div class="my-requests-empty">' +
          '<p class="my-requests-empty__text">Не удалось загрузить список</p>' +
          "</div>";
      });
  }

  window.RequestsScreen = {
    render: renderMyRequests,
  };

  function updateRequestsArchiveCalendarUI() {
    var cal = document.getElementById("requests-archive-calendar");
    var sel = document.getElementById("requests-archive-month");
    var prevBtn = document.getElementById("requests-archive-prev");
    var nextBtn = document.getElementById("requests-archive-next");
    if (!cal || !sel) return;
    if (currentRequestsFilter !== "archive") {
      cal.hidden = true;
      return;
    }
    cal.hidden = false;
    ensureArchiveCalendarState();
    var cur = getCurrentYearMonth();
    var minYear = 2020;
    var options = [];
    for (var y = minYear; y <= cur.year; y++) {
      var maxM = y === cur.year ? cur.month : 12;
      for (var m = 1; m <= maxM; m++) {
        var val = y + "-" + (m < 10 ? "0" + m : m);
        options.push({ value: val, label: ARCHIVE_MONTH_NAMES[m - 1] + " " + y });
      }
    }
    sel.innerHTML = options.map(function (o) { return '<option value="' + escapeHtml(o.value) + '">' + escapeHtml(o.label) + "</option>"; }).join("");
    sel.value = archiveCalendarYear + "-" + (archiveCalendarMonth < 10 ? "0" + archiveCalendarMonth : archiveCalendarMonth);
    if (prevBtn) prevBtn.disabled = archiveCalendarYear <= minYear && archiveCalendarMonth <= 1;
    if (nextBtn) {
      nextBtn.disabled = archiveCalendarYear >= cur.year && archiveCalendarMonth >= cur.month;
    }
  }

  (function initRequestsFilterRadios() {
    var radios = document.querySelectorAll('input[name="requests-filter"]');
    radios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        currentRequestsFilter = this.value;
        updateRequestsArchiveCalendarUI();
        applyRequestsFilterAndRender();
      });
    });
  })();

  (function initRequestsArchiveCalendar() {
    var cal = document.getElementById("requests-archive-calendar");
    var sel = document.getElementById("requests-archive-month");
    var prevBtn = document.getElementById("requests-archive-prev");
    var nextBtn = document.getElementById("requests-archive-next");
    if (!cal || !sel) return;
    updateRequestsArchiveCalendarUI();
    sel.addEventListener("change", function () {
      var parts = sel.value.split("-");
      if (parts.length !== 2) return;
      archiveCalendarYear = parseInt(parts[0], 10);
      archiveCalendarMonth = parseInt(parts[1], 10);
      applyRequestsFilterAndRender();
      updateRequestsArchiveCalendarUI();
    });
    if (prevBtn) prevBtn.addEventListener("click", function () {
      if (prevBtn.disabled) return;
      archiveCalendarMonth--;
      if (archiveCalendarMonth < 1) { archiveCalendarMonth = 12; archiveCalendarYear--; }
      ensureArchiveCalendarState();
      applyRequestsFilterAndRender();
      updateRequestsArchiveCalendarUI();
    });
    if (nextBtn) nextBtn.addEventListener("click", function () {
      if (nextBtn.disabled) return;
      var cur = getCurrentYearMonth();
      if (archiveCalendarYear > cur.year || (archiveCalendarYear === cur.year && archiveCalendarMonth >= cur.month)) return;
      archiveCalendarMonth++;
      if (archiveCalendarMonth > 12) { archiveCalendarMonth = 1; archiveCalendarYear++; }
      ensureArchiveCalendarState();
      applyRequestsFilterAndRender();
      updateRequestsArchiveCalendarUI();
    });
  })();

  function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatDateDisplay(val) {
    if (val == null || val === "") return "—";
    var s = String(val).trim();
    if (s.length >= 10 && s[2] === "." && s[5] === ".") return s.slice(0, 10);
    var match = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) return match[3] + "." + match[2] + "." + match[1];
    return s;
  }
  function formatDateWithTime(val) {
    if (val == null || val === "") return "—";
    var s = String(val).trim();
    if (s.length >= 16 && s[2] === "." && s[5] === "." && s[10] === " ") return s;
    if (s.length >= 10 && s[2] === "." && s[5] === ".") return s;
    var match = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if (match) return match[3] + "." + match[2] + "." + match[1] + " " + match[4] + ":" + match[5];
    match = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) return match[3] + "." + match[2] + "." + match[1];
    return s;
  }

  var currentRequestData = null;
  var editingRequestId = null;
  var detailModal = document.getElementById("request-detail-modal");
  var detailBody = document.getElementById("request-detail-body");
  var detailEditBtn = document.getElementById("request-detail-edit");
  var detailCloseBtn = document.getElementById("request-detail-close");
  var detailActions = document.getElementById("request-detail-actions");
  var detailCloseX = document.getElementById("request-detail-close-btn");
  var detailBackdrop = document.getElementById("request-detail-backdrop");
  var editModal = document.getElementById("request-edit-modal");
  var editForm = document.getElementById("request-edit-form");
  var editCancelBtn = document.getElementById("request-edit-cancel");
  var editSubmitBtn = document.getElementById("request-edit-submit");
  var editBackdrop = document.getElementById("request-edit-backdrop");
  var editCloseX = document.getElementById("request-edit-close-btn");
  var closeConfirmModal = document.getElementById("request-close-confirm-modal");
  var closeConfirmComment = document.getElementById("request-close-comment");
  var closeConfirmTypeClose = document.getElementById("request-close-confirm-type-close");
  var closeConfirmTypeCancel = document.getElementById("request-close-confirm-type-cancel");
  var closeConfirmDismiss = document.getElementById("request-close-confirm-dismiss");
  var closeConfirmSubmit = document.getElementById("request-close-confirm-submit");
  var closeConfirmBackdrop = document.getElementById("request-close-confirm-backdrop");
  var closeConfirmCloseX = document.getElementById("request-close-confirm-close-btn");
  var editSentHrModal = document.getElementById("edit-sent-hr-modal");
  var editSentHrBackdrop = document.getElementById("edit-sent-hr-backdrop");
  var editSentHrOk = document.getElementById("edit-sent-hr-ok");

  function row(label, value) {
    return '<div class="request-detail-row"><div class="request-detail-row__label">' + escapeHtml(label) + '</div><div class="request-detail-row__value">' + escapeHtml(value || "—") + '</div></div>';
  }
  function showDetailWithData(data) {
    currentRequestData = data;
    var statusText = data.status === "new" ? "Новая" : (data.status === "in_progress" ? "В работе" : (data.status === "cancelled" ? "Отменена" : (data.status === "closed" ? "Закрыта" : (data.status || "—"))));
    var headcountVal = data.headcount != null && data.headcount !== undefined ? data.headcount : (data.head_count != null && data.head_count !== undefined ? data.head_count : null);
    var headcountStr = headcountVal != null ? headcountVal + " чел." : "—";
    if (detailBody) {
      var parts = [
        row("Площадка", data.venue),
        row("Должность", data.position),
        row("Количество", headcountStr),
        row("График", data.schedule),
        (data.work_time ? row("Время работы", data.work_time) : ""),
        row("Оклад", data.salary),
        row("Вид оформления", data.employment_type),
        row("Требования", data.requirements),
        row("Дата выхода", formatDateDisplay(data.start_date)),
        row("Контакт", data.contact),
        row("Согласование кандидатов", data.candidate_approval_required === true ? "Да" : "Нет"),
        row("Статус", statusText),
        (data.created_at ? row("Дата создания", formatDateWithTime(data.created_at)) : ""),
        (data.closed_at ? row("Дата закрытия", formatDateWithTime(data.closed_at)) : ""),
        (data.result_notes ? row("Комментарий при закрытии", data.result_notes) : "")
      ];
      detailBody.innerHTML = parts.join("");
    }
    if (detailActions) detailActions.hidden = false;
    if (detailModal) detailModal.hidden = false;
    var isArchived = data.status === "closed" || data.status === "cancelled";
    if (detailCloseBtn) {
      detailCloseBtn.hidden = isArchived;
      detailCloseBtn.disabled = isArchived;
    }
    if (detailEditBtn) detailEditBtn.hidden = isArchived;
  }
  function openRequestDetail(id) {
    (window.apiFetch || fetch)("api/requests/" + id)
      .then(function (res) {
        if (!res.ok) throw res;
        return res.json();
      })
      .then(showDetailWithData)
      .catch(function (res) {
        var msg = "Не удалось загрузить заявку.";
        if (res && res.status === 401) msg = "Откройте приложение из Telegram.";
        else if (res && res.status === 404) msg = "Заявка не найдена.";
        if (detailBody) detailBody.innerHTML = "<p class=\"request-detail-error\">" + escapeHtml(msg) + "</p>";
        if (detailActions) detailActions.hidden = true;
        if (detailModal) detailModal.hidden = false;
      });
  }
  function closeDetailModal() {
    if (detailModal) detailModal.hidden = true;
    currentRequestData = null;
  }
  function openEditModal() {
    if (!currentRequestData || !editForm) return;
    var d = currentRequestData;
    editingRequestId = d.id;
    var editError = document.getElementById("request-edit-error");
    if (editError) {
      editError.textContent = "";
      editError.hidden = true;
    }
    if (editForm.start_date) editForm.start_date.removeAttribute("aria-invalid");
    editForm.venue.value = d.venue || "";
    editForm.position.value = d.position || "";
    editForm.headcount.value = d.headcount != null ? d.headcount : 1;
    editForm.schedule.value = d.schedule || "";
    var wtInput = editForm.querySelector('[name="work_time"]');
    if (wtInput) wtInput.value = d.work_time || "";
    editForm.salary.value = d.salary || "";
    editForm.employment_type.value = d.employment_type || "";
    editForm.requirements.value = d.requirements || "";
    editForm.start_date.value = (d.start_date || "").trim().slice(0, 10);
    editForm.contact.value = d.contact || "";
    var approvalInput = editForm.querySelector('[name="candidate_approval_required"]');
    if (approvalInput) approvalInput.checked = d.candidate_approval_required === true;
    closeDetailModal();
    if (editModal) editModal.hidden = false;
  }
  function closeEditModal() {
    if (editModal) editModal.hidden = true;
    editingRequestId = null;
  }
  function openCloseConfirmModal() {
    if (!currentRequestData || currentRequestData.status === "closed" || currentRequestData.status === "cancelled") return;
    if (closeConfirmComment) {
      closeConfirmComment.value = "";
      closeConfirmComment.removeAttribute("aria-invalid");
    }
    if (closeConfirmTypeClose) {
      closeConfirmTypeClose.classList.add("request-close-confirm__toggle-btn--active");
      closeConfirmTypeClose.setAttribute("aria-selected", "true");
    }
    if (closeConfirmTypeCancel) {
      closeConfirmTypeCancel.classList.remove("request-close-confirm__toggle-btn--active");
      closeConfirmTypeCancel.setAttribute("aria-selected", "false");
    }
    updateCloseConfirmSubmitState();
    if (closeConfirmModal) closeConfirmModal.hidden = false;
  }
  function closeCloseConfirmModal() {
    if (closeConfirmModal) closeConfirmModal.hidden = true;
  }
  function getCloseConfirmStatus() {
    if (closeConfirmTypeCancel && closeConfirmTypeCancel.classList.contains("request-close-confirm__toggle-btn--active")) return "cancelled";
    return "closed";
  }
  function updateCloseConfirmSubmitState() {
    var comment = (closeConfirmComment && closeConfirmComment.value) ? closeConfirmComment.value.trim() : "";
    if (closeConfirmSubmit) closeConfirmSubmit.disabled = comment.length === 0;
  }
  function submitCloseConfirm() {
    if (!currentRequestData) return;
    var comment = (closeConfirmComment && closeConfirmComment.value) ? closeConfirmComment.value.trim() : "";
    if (!comment) {
      if (closeConfirmComment) {
        closeConfirmComment.setAttribute("aria-invalid", "true");
        closeConfirmComment.focus();
      }
      return;
    }
    var status = getCloseConfirmStatus();
    var id = currentRequestData.id;
    if (closeConfirmSubmit) closeConfirmSubmit.disabled = true;
    closeCloseConfirmModal();
    closeDetailModal();
    if (editSentHrModal) editSentHrModal.removeAttribute("hidden");
    (window.apiFetch || fetch)("/api/requests/" + id + "/close", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status, result_notes: comment }),
    })
      .then(function (res) {
        if (!res.ok) {
          if (editSentHrModal) editSentHrModal.setAttribute("hidden", "");
          if (closeConfirmSubmit) closeConfirmSubmit.disabled = false;
          return;
        }
        renderMyRequests();
      })
      .catch(function () {
        if (editSentHrModal) editSentHrModal.setAttribute("hidden", "");
        if (closeConfirmSubmit) closeConfirmSubmit.disabled = false;
      });
  }

  if (detailBackdrop) detailBackdrop.addEventListener("click", closeDetailModal);
  if (detailCloseX) detailCloseX.addEventListener("click", closeDetailModal);
  if (detailEditBtn) detailEditBtn.addEventListener("click", openEditModal);
  if (detailCloseBtn) detailCloseBtn.addEventListener("click", function () {
    if (currentRequestData && currentRequestData.status !== "closed" && currentRequestData.status !== "cancelled") openCloseConfirmModal();
  });
  if (closeConfirmTypeClose) closeConfirmTypeClose.addEventListener("click", function () {
    closeConfirmTypeClose.classList.add("request-close-confirm__toggle-btn--active");
    closeConfirmTypeClose.setAttribute("aria-selected", "true");
    if (closeConfirmTypeCancel) {
      closeConfirmTypeCancel.classList.remove("request-close-confirm__toggle-btn--active");
      closeConfirmTypeCancel.setAttribute("aria-selected", "false");
    }
    updateCloseConfirmSubmitState();
  });
  if (closeConfirmTypeCancel) closeConfirmTypeCancel.addEventListener("click", function () {
    closeConfirmTypeCancel.classList.add("request-close-confirm__toggle-btn--active");
    closeConfirmTypeCancel.setAttribute("aria-selected", "true");
    if (closeConfirmTypeClose) {
      closeConfirmTypeClose.classList.remove("request-close-confirm__toggle-btn--active");
      closeConfirmTypeClose.setAttribute("aria-selected", "false");
    }
    updateCloseConfirmSubmitState();
  });
  if (closeConfirmComment) closeConfirmComment.addEventListener("input", function () {
    updateCloseConfirmSubmitState();
    if (closeConfirmComment) closeConfirmComment.removeAttribute("aria-invalid");
  });
  if (closeConfirmDismiss) closeConfirmDismiss.addEventListener("click", closeCloseConfirmModal);
  if (closeConfirmSubmit) closeConfirmSubmit.addEventListener("click", submitCloseConfirm);
  if (closeConfirmBackdrop) closeConfirmBackdrop.addEventListener("click", closeCloseConfirmModal);
  if (closeConfirmCloseX) closeConfirmCloseX.addEventListener("click", closeCloseConfirmModal);
  if (editBackdrop) editBackdrop.addEventListener("click", closeEditModal);
  if (editCancelBtn) editCancelBtn.addEventListener("click", closeEditModal);
  if (editCloseX) editCloseX.addEventListener("click", closeEditModal);
  function submitEditForm() {
    if (editingRequestId == null || !editForm) return;
    var id = editingRequestId;
    var editError = document.getElementById("request-edit-error");
    function setEditError(msg) {
      if (!editError) return;
      editError.textContent = msg || "";
      editError.hidden = !msg;
    }

    var startDateRaw = (editForm.start_date && editForm.start_date.value) ? editForm.start_date.value.trim() : "";
    if (startDateRaw) {
      var m = startDateRaw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
      if (!m) {
        if (editForm.start_date) {
          editForm.start_date.setAttribute("aria-invalid", "true");
          editForm.start_date.focus();
        }
        setEditError("Дата выхода должна быть в формате dd.mm.yyyy (например, 09.03.2026).");
        return;
      }
      var dd = parseInt(m[1], 10);
      var mm = parseInt(m[2], 10);
      var yyyy = parseInt(m[3], 10);
      var d = new Date(yyyy, mm - 1, dd);
      if (!(d && d.getFullYear() === yyyy && d.getMonth() === mm - 1 && d.getDate() === dd)) {
        if (editForm.start_date) {
          editForm.start_date.setAttribute("aria-invalid", "true");
          editForm.start_date.focus();
        }
        setEditError("Некорректная дата. Проверьте «Дата выхода» (dd.mm.yyyy).");
        return;
      }
    }
    if (editForm.start_date) editForm.start_date.removeAttribute("aria-invalid");
    setEditError("");

    var wtEl = editForm.querySelector('[name="work_time"]');
    var approvalEl = editForm.querySelector('[name="candidate_approval_required"]');
    var payload = {
      venue: (editForm.venue && editForm.venue.value) || "",
      position: (editForm.position && editForm.position.value) || "",
      headcount: parseInt(editForm.headcount.value, 10) || 1,
      schedule: (editForm.schedule && editForm.schedule.value) || "",
      work_time: (wtEl && wtEl.value) ? wtEl.value.trim() : null,
      salary: (editForm.salary && editForm.salary.value) || "",
      employment_type: (editForm.employment_type && editForm.employment_type.value) || "",
      requirements: (editForm.requirements && editForm.requirements.value) || "",
      start_date: startDateRaw,
      contact: (editForm.contact && editForm.contact.value) || "",
      candidate_approval_required: approvalEl ? approvalEl.checked : true,
    };
    closeEditModal();
    if (editSentHrModal) editSentHrModal.removeAttribute("hidden");
    (window.apiFetch || fetch)("/api/requests/" + id, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (!res.ok) {
          if (editSentHrModal) editSentHrModal.setAttribute("hidden", "");
          return Promise.reject();
        }
        return res.json();
      })
      .then(function () {
        renderMyRequests();
      })
      .catch(function () {
        if (editSentHrModal) editSentHrModal.setAttribute("hidden", "");
      });
  }
  function closeEditSentHrModal() {
    if (editSentHrModal) editSentHrModal.setAttribute("hidden", "");
  }
  if (editSentHrOk) editSentHrOk.addEventListener("click", closeEditSentHrModal);
  if (editSentHrBackdrop) editSentHrBackdrop.addEventListener("click", closeEditSentHrModal);
  if (editSubmitBtn) {
    editSubmitBtn.addEventListener("click", function (e) {
      e.preventDefault();
      submitEditForm();
    });
  }
  if (editForm) {
    editForm.addEventListener("submit", function (e) {
      e.preventDefault();
      submitEditForm();
    });
  }
  if (editForm && editForm.start_date) {
    editForm.start_date.addEventListener("input", function () {
      editForm.start_date.removeAttribute("aria-invalid");
      var editError = document.getElementById("request-edit-error");
      if (editError) {
        editError.textContent = "";
        editError.hidden = true;
      }
    });
  }

  var myRequestsContent = document.getElementById("my-requests-content");
  if (myRequestsContent) {
    myRequestsContent.addEventListener("click", function (e) {
      var card = e.target.closest(".my-requests-card");
      if (!card) return;
      var id = card.getAttribute("data-id");
      if (!id) return;
      openRequestDetail(id);
    });
  }

  if (bottomNav) {
    navItems.forEach((item) => {
      item.addEventListener("click", () => {
        const target = item.getAttribute("data-target");
        const view = item.getAttribute("data-view");
        if (!target) return;

        showScreen(target);
        if (target === "requests" && view) {
          showRequestsView(view);
        } else if (target === "requests" && !view && wizard.el) {
          showRequestsView("create");
        } else {
          setActiveNavItem(target, null);
          if (target === "candidates" && window.CandidatesScreen && window.CandidatesScreen.render) {
            window.CandidatesScreen.render();
          }
        }
      });
    });
  }

  const headerAvatarBtn = document.getElementById("header-avatar-btn");
  if (headerAvatarBtn) {
    headerAvatarBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      toggleTheme();
      if (window.HRTelegramWebApp && window.HRTelegramWebApp.haptic) {
        window.HRTelegramWebApp.haptic("light");
      }
    });
  }

  showScreen("requests");
  showRequestsView("list");

  const faqData = [
    {
      q: "Когда нужно создавать заявку на сотрудника?",
      a: "Заявку необходимо оформить минимум за 2 дня до планируемой даты выхода сотрудника. HR-отделу требуется 2–3 дня для подбора кандидата.",
    },
    {
      q: "Можно ли оформить срочную заявку «на сегодня»?",
      a: "Нет. Подбор персонала требует времени. Заявки в день выхода сотрудника не обрабатываются.",
    },
    {
      q: "Что делать, если кандидат уже найден самостоятельно?",
      a: "В этом случае необходимо сообщить HR, чтобы закрыть заявку и обновить статус.",
    },
    {
      q: "Нужно ли давать обратную связь по кандидатам?",
      a: "Да. Если кандидат был направлен HR, необходимо сообщить результат собеседования: принят, отказ или требуется дополнительное рассмотрение. Это помогает ускорить подбор и избежать лишних приглашений.",
    },
    {
      q: "Можно ли отказать кандидату без причины?",
      a: "Если кандидат не подходит, желательно кратко указать причину отказа. Это помогает HR корректнее подбирать следующих кандидатов.",
    },
    {
      q: "Что делать, если потребность в сотруднике изменилась?",
      a: "Если заявка стала неактуальной или условия изменились, необходимо обновить заявку или уведомить HR.",
    },
    {
      q: "Что делать, если кандидат не вышел на смену?",
      a: "Необходимо сообщить HR, чтобы можно было оперативно начать повторный поиск.",
    },
    {
      q: "Кто отвечает за собеседование кандидата?",
      a: "HR организует поиск и направляет кандидатов, окончательное решение о приёме принимает площадка.",
    },
    {
      q: "Где посмотреть свои заявки?",
      a: "Все созданные заявки можно посмотреть в разделе «Мои заявки».",
    },
    {
      q: "Возник вопрос, которого нет в списке?",
      a: "Свяжитесь с HR напрямую.",
    },
  ];

  const faqList = document.getElementById("faq-list");
  if (faqList) {
    faqList.innerHTML = faqData
      .map(
        (item, i) => `
      <div class="faq-item" data-faq-index="${i}">
        <button type="button" class="faq-item__btn" aria-expanded="false" aria-controls="faq-answer-${i}" id="faq-btn-${i}">
          ${escapeHtml(item.q)}
        </button>
        <div class="faq-item__answer" id="faq-answer-${i}" role="region" aria-labelledby="faq-btn-${i}" hidden>
          <p>${escapeHtml(item.a)}</p>
        </div>
      </div>
    `
      )
      .join("");
    faqList.querySelectorAll(".faq-item__btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const item = btn.closest(".faq-item");
        const answer = item.querySelector(".faq-item__answer");
        const isOpen = item.classList.toggle("faq-item--open");
        btn.setAttribute("aria-expanded", isOpen);
        answer.hidden = !isOpen;
      });
    });
  }

  function formatDateDisplay(iso) {
    if (iso == null || iso === "") return "—";
    var s = String(iso).trim();
    if (s.length < 10) return s;
    if (s[2] === "." && s[5] === ".") return s.slice(0, 10);
    var parts = s.slice(0, 10).split("-");
    if (parts.length >= 3 && parts[0].length === 4) {
      return parts[2] + "." + parts[1] + "." + parts[0];
    }
    return s;
  }

  function formatSalaryDisplay(str) {
    const digits = String(str).replace(/\D/g, "");
    if (!digits) return "";
    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function parseSalaryInput(str) {
    const num = parseInt(String(str).replace(/\s/g, "").replace(/\D/g, ""), 10);
    return Number.isNaN(num) ? 0 : num;
  }

  function buildWorkTimeValue(from, to) {
    const f = (from && String(from).trim()) || "";
    const t = (to && String(to).trim()) || "";
    if (f && t) return f + "-" + t;
    return f || t || "";
  }

  function formatWorkTimeDisplay(from, to) {
    const v = buildWorkTimeValue(from, to);
    return v || "—";
  }

  const MONTH_NAMES = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
  const MONTH_NAMES_GENITIVE = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];

  function toISO(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }
  function isoToDdMmYyyy(iso) {
    if (!iso || iso.length < 10) return iso || "";
    var p = iso.slice(0, 10).split("-");
    if (p.length === 3 && p[0].length === 4) return p[2] + "." + p[1] + "." + p[0];
    return iso;
  }
  function ddMmYyyyToIso(s) {
    if (!s || s.length < 10) return s || "";
    if (s[2] === "." && s[5] === ".") return s.slice(6, 10) + "-" + s.slice(3, 5) + "-" + s.slice(0, 2);
    return s.slice(0, 10);
  }

  function formatDayShort(iso) {
    if (!iso || iso.length < 10) return "";
    const s = String(iso).trim().slice(0, 10);
    let d, m;
    if (s[2] === "." && s[5] === ".") {
      d = s.slice(0, 2);
      m = s.slice(3, 5);
    } else {
      const parts = s.split("-");
      if (parts.length < 3) return s;
      [, m, d] = parts;
    }
    const monthShort = MONTH_NAMES[parseInt(m, 10) - 1].slice(0, 3);
    return `${parseInt(d, 10)} ${monthShort}`;
  }

  function formatDateLong(iso) {
    if (!iso || iso.length < 10) return "";
    const s = String(iso).trim().slice(0, 10);
    let d, m, y;
    if (s[2] === "." && s[5] === ".") {
      d = s.slice(0, 2);
      m = s.slice(3, 5);
      y = s.slice(6, 10);
    } else {
      const parts = s.split("-");
      if (parts.length < 3 || parts[0].length !== 4) return s;
      [y, m, d] = parts;
    }
    const mi = parseInt(m, 10) - 1;
    return `${parseInt(d, 10)} ${MONTH_NAMES_GENITIVE[mi]} ${y}`;
  }

  function daysFromToday(iso) {
    if (!iso || iso.length < 10) return null;
    const s = String(iso).trim().slice(0, 10);
    const isoStr = s[2] === "." && s[5] === "." ? s.slice(6, 10) + "-" + s.slice(3, 5) + "-" + s.slice(0, 2) : s;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const that = new Date(isoStr + "T00:00:00");
    if (Number.isNaN(that.getTime())) return null;
    that.setHours(0, 0, 0, 0);
    return Math.floor((that - today) / (24 * 60 * 60 * 1000));
  }

  function formatDaysAway(iso) {
    const days = daysFromToday(iso);
    if (days === null) return "";
    if (days === 0) return "сегодня";
    if (days === 1) return "завтра";
    if (days >= 2 && days <= 4) return `через ${days} дня`;
    return `через ${days} дней`;
  }

  function renderStep() {
    if (!wizard.el) return;

    const step = wizard.steps[wizard.currentStep];
    const total = wizard.steps.length;

    wizard.titleEl.textContent = `Шаг ${wizard.currentStep + 1}. ${step.title}`;
    wizard.progressEl.textContent = `${wizard.currentStep + 1} / ${total}`;

    if (wizard.progressFillEl) {
      const ratio = (wizard.currentStep + 1) / total;
      wizard.progressFillEl.style.width = `${Math.round(ratio * 100)}%`;
    }
    const progressDots = document.querySelectorAll("#wizard-progress-dots .wizard-progress-dot");
    progressDots.forEach((dot, i) => {
      dot.classList.toggle("wizard-progress-dot--filled", i < wizard.currentStep);
      dot.classList.toggle("wizard-progress-dot--current", i === wizard.currentStep);
    });

    let html = "";

    switch (step.id) {
      case "location": {
        const venues = [
          "LOFT #4",
          "LOFT #2-3",
          "LOFT #1,#5",
          "SERP&MOLOT",
          "TAU",
          "The Birch",
          "SUBSTANCE (Парк Горького)",
          "SUBSTANCE (Авиамоторная)",
          "ZORKA",
          "MR.PINKY",
          "PINK MILK",
          "Метелица",
          "Madam Roche",
          "Другое"
        ];
        html = `
          <div class="wizard-field-group">
            <div class="wizard-label">Выберите площадку:</div>
            <div class="wizard-options">
              ${venues.map(function (v) {
                const value = v === "Другое" ? "custom" : v;
                return `
              <label class="wizard-option">
                <input type="radio" name="location" value="${escapeHtml(value)}" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">${escapeHtml(v)}</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>`;
              }).join("")}
              <input type="text" id="location-custom" class="wizard-input wizard-input--hidden" placeholder="Введите название площадки" />
            </div>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      }
      case "position": {
        const positions = [
          "Официант",
          "Бармен",
          "Бариста",
          "Менеджер",
          "Хостес",
          "Повар горячего цеха",
          "Повар холодного цеха",
          "Повар-универсал",
          "Пиццемейкер",
          "Кондитер",
          "Су-Шеф",
          "Шеф-повар",
          "Мойщица",
          "Котломой",
          "Другое"
        ];
        html = `
          <div class="wizard-field-group">
            <div class="wizard-label">Кого ищем?</div>
            <div class="wizard-options">
              ${positions.map(function (p) {
                const value = p === "Другое" ? "custom" : p;
                return `
              <label class="wizard-option">
                <input type="radio" name="position" value="${escapeHtml(value)}" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text"><span class="wizard-option__title">${escapeHtml(p)}</span></span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>`;
              }).join("")}
              <input type="text" id="position-custom" class="wizard-input wizard-input--hidden" placeholder="Введите должность" />
            </div>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      }
      case "headcount":
        html = `
          <div class="wizard-field-group wizard-field-group--headcount">
            <label class="wizard-label" for="headcount-input">Сколько человек требуется?</label>
            <div class="stepper" id="headcount-stepper" aria-hidden="false">
              <button type="button" class="stepper__btn" id="headcount-decrease">−</button>
              <div class="stepper__value" id="headcount-value">${wizard.data.headcount}</div>
              <button type="button" class="stepper__btn" id="headcount-increase">+</button>
            </div>
            <div class="stepper-quick-label">или выберите</div>
            <div class="stepper-quick" id="headcount-quick">
              <button type="button" class="stepper-quick__btn ${wizard.data.headcount === 1 ? "wizard-quick--active" : ""}" data-val="1">1</button>
              <button type="button" class="stepper-quick__btn ${wizard.data.headcount === 2 ? "wizard-quick--active" : ""}" data-val="2">2</button>
              <button type="button" class="stepper-quick__btn ${wizard.data.headcount === 3 ? "wizard-quick--active" : ""}" data-val="3">3</button>
              <button type="button" class="stepper-quick__btn ${wizard.data.headcount === 5 ? "wizard-quick--active" : ""}" data-val="5">5</button>
              <button type="button" class="stepper-quick__btn ${wizard.data.headcount === 10 ? "wizard-quick--active" : ""}" data-val="10">10</button>
            </div>
            <input type="number" id="headcount-input" class="wizard-input wizard-input--hidden" min="1" max="100" value="${wizard.data.headcount}" />
            <div class="wizard-hint">Минимум 1 сотрудник</div>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      case "schedule":
        html = `
          <div class="wizard-field-group">
            <div class="wizard-label">График работы:</div>
            <div class="wizard-options">
              <label class="wizard-option">
                <input type="radio" name="schedule" value="5/2 (пн-пт)" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">5/2 (пн-пт)</span>
                      <span class="wizard-option__desc">Пять рабочих, два выходных</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <label class="wizard-option">
                <input type="radio" name="schedule" value="2/2" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">2/2</span>
                      <span class="wizard-option__desc">Два через два</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <label class="wizard-option">
                <input type="radio" name="schedule" value="Сменный график" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">Сменный график</span>
                      <span class="wizard-option__desc">Утро / день / вечер</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <label class="wizard-option">
                <input type="radio" name="schedule" value="Вахта (15/15)" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">Вахта (15/15)</span>
                      <span class="wizard-option__desc">15 дней работа / 15 отдых</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <label class="wizard-option">
                <input type="radio" name="schedule" value="Разовый проект" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">Разовый проект</span>
                      <span class="wizard-option__desc">Одно мероприятие или подмена</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <label class="wizard-option">
                <input type="radio" name="schedule" value="custom" />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text"><span class="wizard-option__title">Другое</span></span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <input type="text" id="schedule-custom" class="wizard-input wizard-input--hidden" placeholder="Опишите график" />
            </div>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      case "workTime":
        html = `
          <div class="wizard-field-group wizard-field-group--work-time">
            <div class="wizard-label">Время работы</div>
            <div class="work-time-row">
              <label class="work-time-field">
                <span class="work-time-field__label">От</span>
                <input type="time" id="work-time-from" class="wizard-input" value="${escapeHtml(wizard.data.workTimeFrom)}" />
              </label>
              <span class="work-time-sep">—</span>
              <label class="work-time-field">
                <span class="work-time-field__label">До</span>
                <input type="time" id="work-time-to" class="wizard-input" value="${escapeHtml(wizard.data.workTimeTo)}" />
              </label>
            </div>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      case "salary": {
        const salaryDisplay = wizard.data.salary && wizard.data.salaryType !== "negotiable"
          ? formatSalaryDisplay(String(wizard.data.salary).replace(/\s/g, ""))
          : "";
        html = `
          <div class="wizard-field-group wizard-field-group--salary">
            <div class="wizard-label">Зарплата</div>
            <div class="wizard-segmented" role="group" aria-label="Тип оклада">
              <label class="wizard-segmented__option">
                <input type="radio" name="salary-type" value="fixed" ${wizard.data.salaryType === "fixed" ? "checked" : ""} />
                <span>Фиксированная</span>
              </label>
              <label class="wizard-segmented__option">
                <input type="radio" name="salary-type" value="negotiable" ${wizard.data.salaryType === "negotiable" ? "checked" : ""} />
                <span>Договорная</span>
              </label>
            </div>
            <div class="salary-row ${wizard.data.salaryType === "negotiable" ? "wizard-input--hidden" : ""}" id="salary-row">
              <div class="salary-input-wrap">
                <input type="text" id="salary-input" class="wizard-input wizard-input--salary" inputmode="numeric" autocomplete="off" placeholder="Например: 90 000" value="${salaryDisplay}" />
                <span class="salary-row__suffix">₽</span>
              </div>
            </div>
            <div class="salary-quick ${wizard.data.salaryType === "negotiable" ? "wizard-input--hidden" : ""}" id="salary-quick">
              <button type="button" class="salary-quick__btn" data-value="80000">80 000</button>
              <button type="button" class="salary-quick__btn" data-value="100000">100 000</button>
              <button type="button" class="salary-quick__btn" data-value="120000">120 000</button>
            </div>
            <div class="wizard-error" id="wizard-error"></div>
          </div>
        `;
        break;
      }
      case "employmentType":
        html = `
          <div class="wizard-field-group">
            <div class="wizard-label">Вид оформления</div>
            <div class="wizard-options">
              <label class="wizard-option">
                <input type="radio" name="employment-type" value="ТК" ${wizard.data.employmentType === "ТК" ? "checked" : ""} />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">ТК</span>
                      <span class="wizard-option__desc">Трудовой договор</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <label class="wizard-option">
                <input type="radio" name="employment-type" value="СЗ" ${wizard.data.employmentType === "СЗ" ? "checked" : ""} />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">СЗ</span>
                      <span class="wizard-option__desc">Самозанятый</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
            </div>
            <div class="wizard-error" id="wizard-error"></div>
          </div>
        `;
        break;
      case "requirements":
        html = `
          <div class="wizard-field-group">
            <label class="wizard-label" for="requirements-input">Требования и обязанности:</label>
            <div class="wizard-templates" id="requirements-templates">
              <button type="button" class="wizard-templates__chip" data-text="Без опыта">Без опыта</button>
              <button type="button" class="wizard-templates__chip" data-text="Опыт от 1 года">Опыт 1+ год</button>
              <button type="button" class="wizard-templates__chip" data-text="Медкнижка обязательна">Медкнижка</button>
              <button type="button" class="wizard-templates__chip" data-text="Пунктуальность">Пунктуальность</button>
            </div>
            <textarea id="requirements-input" class="wizard-textarea" placeholder="Опишите ключевые требования и обязанности">${wizard.data.requirements}</textarea>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      case "startDate": {
        html = `
          <div class="wizard-field-group">
            <div class="wizard-label-row">
              <span class="wizard-label">Желаемая дата выхода</span>
              <button type="button" class="wizard-info-btn" id="date-info-btn" aria-label="Почему нельзя выбрать сегодня или завтра">❓</button>
              <div class="wizard-info-tooltip" id="date-info-tooltip" role="tooltip" hidden>
                Заявка должна быть оформлена не менее чем за 2 дня до планируемой даты выхода сотрудника, т.к HR-отделу требуется время для подбора кандидатов.
              </div>
            </div>
            <div id="calendar-inline" class="calendar-inline" role="application" aria-label="Выбор даты"></div>
            <div id="calendar-selected-summary" class="calendar-selected-summary" style="display: ${wizard.data.startDate ? "block" : "none"}">
              <div class="calendar-selected-summary__date">Выбрано: <span id="calendar-selected-date-text"></span></div>
              <div class="calendar-selected-summary__distance" id="calendar-selected-distance"></div>
            </div>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      }
      case "contact":
        if (!wizard.data.contactPerson && meUserCache && meUserCache.from_telegram && meUserCache.user && meUserCache.user.username) {
          var u = meUserCache.user;
          var fio = ((u.first_name || "") + " " + (u.last_name || "")).trim();
          wizard.data.contactPerson = fio ? fio + " (@" + u.username + ")" : "@" + u.username;
        }
        html = `
          <div class="wizard-field-group">
            <label class="wizard-label" for="contact-input">Контактное лицо (ФИО или имя + @username):</label>
            <input type="text" id="contact-input" class="wizard-input" placeholder="Например, Иванов Иван (@ivanov)" value="${escapeHtml(wizard.data.contactPerson)}" />
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      case "candidateApproval":
        html = `
          <div class="wizard-field-group">
            <div class="wizard-label">Нужно ли согласовывать каждого кандидата?</div>
            <div class="wizard-options">
              <label class="wizard-option">
                <input type="radio" name="candidate-approval" value="yes" ${wizard.data.candidateApprovalRequired === true ? "checked" : ""} />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">Да</span>
                      <span class="wizard-option__desc wizard-option__desc--small">Каждый найденный кандидат будет отправляться Вам в чат для согласования кандидата, дня и времени собеседования.</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
              <label class="wizard-option">
                <input type="radio" name="candidate-approval" value="no" ${wizard.data.candidateApprovalRequired === false ? "checked" : ""} />
                <span class="wizard-option__card">
                  <span class="wizard-option__left">
                    <span class="wizard-option__icon"></span>
                    <span class="wizard-option__text">
                      <span class="wizard-option__title">Нет</span>
                      <span class="wizard-option__desc wizard-option__desc--small">HR отдел самостоятельно назначит день и время, после чего Вы получите уведомление о предстоящем собеседовании.</span>
                    </span>
                  </span>
                  <span class="wizard-option__check"></span>
                </span>
              </label>
            </div>
          </div>
          <div class="wizard-error" id="wizard-error"></div>
        `;
        break;
      case "summary":
        html = `
          <div class="wizard-field-group">
            <div class="wizard-label">Проверьте данные заявки:</div>
            <div class="wizard-summary">
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Площадка</div>
                <div class="wizard-summary-value">${wizard.data.location || "—"}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Должность</div>
                <div class="wizard-summary-value">${wizard.data.position || "—"}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Количество</div>
                <div class="wizard-summary-value">${wizard.data.headcount || "—"} человек</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">График</div>
                <div class="wizard-summary-value">${wizard.data.schedule || "—"}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Время работы</div>
                <div class="wizard-summary-value">${formatWorkTimeDisplay(wizard.data.workTimeFrom, wizard.data.workTimeTo)}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Оклад</div>
                <div class="wizard-summary-value">${wizard.data.salaryType === "negotiable" ? "Договорная" : (wizard.data.salary ? formatSalaryDisplay(wizard.data.salary) + " ₽" : "—")}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Вид оформления</div>
                <div class="wizard-summary-value">${wizard.data.employmentType || "—"}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Требования</div>
                <div class="wizard-summary-value">${wizard.data.requirements || "—"}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Дата выхода</div>
                <div class="wizard-summary-value">${wizard.data.startDate ? (typeof wizard.data.startDate === "string" && wizard.data.startDate.length === 10 ? formatDateDisplay(wizard.data.startDate) : wizard.data.startDate) : "—"}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Контакт</div>
                <div class="wizard-summary-value">${wizard.data.contactPerson || "—"}</div>
              </div>
              <div class="wizard-summary-row">
                <div class="wizard-summary-label">Согласование кандидатов</div>
                <div class="wizard-summary-value">${wizard.data.candidateApprovalRequired === true ? "Да" : wizard.data.candidateApprovalRequired === false ? "Нет" : "—"}</div>
              </div>
            </div>
          </div>
        `;
        break;
    }

    if (wizard.bodyEl) {
      wizard.bodyEl.style.opacity = "0";
      wizard.bodyEl.style.transform = "translateY(8px)";
    }

    setTimeout(() => {
      wizard.bodyEl.innerHTML = html;

      if (step.id === "location") {
        const radios = wizard.bodyEl.querySelectorAll('input[name="location"]');
        const customInput = document.getElementById("location-custom");
        radios.forEach((r) =>
          r.addEventListener("change", () => {
            if (r.value === "custom" && r.checked) {
              customInput.classList.remove("wizard-input--hidden");
            } else if (r.value !== "custom" && r.checked) {
              customInput.classList.add("wizard-input--hidden");
            }
          }),
        );
      }
      if (step.id === "position") {
        const radios = wizard.bodyEl.querySelectorAll('input[name="position"]');
        const customInput = document.getElementById("position-custom");
        radios.forEach((r) =>
          r.addEventListener("change", () => {
            if (r.value === "custom" && r.checked) {
              customInput.classList.remove("wizard-input--hidden");
            } else if (r.value !== "custom" && r.checked) {
              customInput.classList.add("wizard-input--hidden");
            }
          }),
        );
      }
      if (step.id === "schedule") {
        const radios = wizard.bodyEl.querySelectorAll('input[name="schedule"]');
        const customInput = document.getElementById("schedule-custom");
        radios.forEach((r) =>
          r.addEventListener("change", () => {
            if (r.value === "custom" && r.checked) {
              customInput.classList.remove("wizard-input--hidden");
            } else if (r.value !== "custom" && r.checked) {
              customInput.classList.add("wizard-input--hidden");
            }
          }),
        );
      }
      if (step.id === "headcount") {
        const dec = document.getElementById("headcount-decrease");
        const inc = document.getElementById("headcount-increase");
        const valEl = document.getElementById("headcount-value");
        const input = document.getElementById("headcount-input");
        const MIN = 1;
        const MAX = 100;
        function syncQuickActive() {
          const v = wizard.data.headcount;
          document.querySelectorAll("#headcount-quick .stepper-quick__btn").forEach((b) => {
            b.classList.toggle("wizard-quick--active", parseInt(b.getAttribute("data-val"), 10) === v);
          });
        }
        function setVal(v) {
          v = Math.max(MIN, Math.min(MAX, Number(v) || MIN));
          wizard.data.headcount = v;
          if (valEl) valEl.textContent = v;
          if (input) input.value = v;
          syncQuickActive();
        }
        if (dec) dec.addEventListener("click", () => setVal(wizard.data.headcount - 1));
        if (inc) inc.addEventListener("click", () => setVal(wizard.data.headcount + 1));
        if (input) {
          input.addEventListener("change", () => {
            let v = Number(input.value);
            setVal(v);
          });
        }
        document.querySelectorAll("#headcount-quick .stepper-quick__btn").forEach((btn) => {
          btn.addEventListener("click", () => {
            const v = parseInt(btn.getAttribute("data-val"), 10);
            setVal(v);
          });
        });
      }
      if (step.id === "salary") {
        const row = document.getElementById("salary-row");
        const salaryInput = document.getElementById("salary-input");
        const toggles = wizard.bodyEl.querySelectorAll('input[name="salary-type"]');
        toggles.forEach((t) =>
          t.addEventListener("change", () => {
            wizard.data.salaryType = t.value;
            const quick = document.getElementById("salary-quick");
            if (t.value === "negotiable") {
              row.classList.add("wizard-input--hidden");
              if (quick) quick.classList.add("wizard-input--hidden");
              wizard.data.salary = "";
              if (salaryInput) salaryInput.value = "";
            } else {
              row.classList.remove("wizard-input--hidden");
              if (quick) quick.classList.remove("wizard-input--hidden");
            }
          }),
        );
        if (wizard.data.salaryType === "negotiable" && row) row.classList.add("wizard-input--hidden");

        const SALARY_MAX = 1000000;
        if (salaryInput) {
          salaryInput.addEventListener("input", () => {
            const digits = salaryInput.value.replace(/\D/g, "");
            const clamped = Math.min(SALARY_MAX, parseInt(digits.slice(0, 7), 10) || 0);
            salaryInput.value = formatSalaryDisplay(clamped);
            wizard.data.salary = clamped ? String(clamped) : "";
          });
        }
        document.querySelectorAll("#salary-quick .salary-quick__btn").forEach((btn) => {
          btn.addEventListener("click", () => {
            const val = parseInt(btn.getAttribute("data-value"), 10);
            wizard.data.salary = String(val);
            salaryInput.value = formatSalaryDisplay(val);
          });
        });
      }
      if (step.id === "employmentType") {
        wizard.bodyEl.querySelectorAll('input[name="employment-type"]').forEach((radio) => {
          radio.addEventListener("change", () => {
            wizard.data.employmentType = radio.value;
          });
        });
      }
      if (step.id === "requirements") {
        document.querySelectorAll("#requirements-templates .wizard-templates__chip").forEach((chip) => {
          chip.addEventListener("click", () => {
            const ta = document.getElementById("requirements-input");
            const text = chip.getAttribute("data-text");
            const sep = ta.value.trim() ? ", " : "";
            ta.value = ta.value.trim() + sep + text;
          });
        });
      }
      if (step.id === "startDate") {
        const calendarEl = document.getElementById("calendar-inline");
        const summaryBlock = document.getElementById("calendar-selected-summary");
        const summaryDateText = document.getElementById("calendar-selected-date-text");
        const summaryDistance = document.getElementById("calendar-selected-distance");
        let calendarView = new Date();
        if (wizard.data.startDate && wizard.data.startDate.length >= 10) {
          var isoForDate = ddMmYyyyToIso(wizard.data.startDate);
          calendarView = new Date(isoForDate + "T12:00:00");
        }

        function setDate(iso) {
          wizard.data.startDate = iso;
          if (summaryBlock) summaryBlock.style.display = "block";
          if (summaryDateText) summaryDateText.textContent = formatDateLong(iso);
          if (summaryDistance) summaryDistance.textContent = formatDaysAway(iso);
          if (wizard.nextBtn) wizard.nextBtn.disabled = false;
          calendarEl.querySelectorAll(".calendar-day").forEach((c) => {
            c.classList.toggle("calendar-day--selected", c.getAttribute("data-iso") === iso);
          });
        }

        function renderCalendar() {
          const year = calendarView.getFullYear();
          const month = calendarView.getMonth();
          const first = new Date(year, month, 1);
          let start = new Date(first);
          const startDay = start.getDay();
          const offset = startDay === 0 ? 6 : startDay - 1;
          start.setDate(start.getDate() - offset);
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          const minSelectable = new Date(today);
          minSelectable.setDate(minSelectable.getDate() + 2);
          minSelectable.setHours(0, 0, 0, 0);
          const selectedIso = wizard.data.startDate && wizard.data.startDate.length >= 10 ? ddMmYyyyToIso(wizard.data.startDate) : null;

          let daysHtml = "";
          for (let i = 0; i < 42; i++) {
            const d = new Date(start);
            d.setDate(d.getDate() + i);
            const iso = toISO(d);
            const isDisabled = d < minSelectable;
            const isOther = d.getMonth() !== month;
            const isSelected = iso === selectedIso;
            const classes = ["calendar-day"];
            if (isDisabled) classes.push("calendar-day--past");
            if (isOther) classes.push("calendar-day--other");
            if (isSelected) classes.push("calendar-day--selected");
            daysHtml += `<button type="button" class="${classes.join(" ")}" data-iso="${iso}" ${isDisabled ? "disabled" : ""}>${d.getDate()}</button>`;
          }

          calendarEl.innerHTML = `
            <div class="calendar-header">
              <select class="calendar-month-select" id="calendar-month-select" aria-label="Месяц">
                ${MONTH_NAMES.map((name, i) => `<option value="${i}" ${i === month ? "selected" : ""}>${name} ${year}</option>`).join("")}
              </select>
              <div class="calendar-nav">
                <button type="button" class="calendar-nav__btn" id="calendar-prev" aria-label="Предыдущий месяц">&#9664;</button>
                <button type="button" class="calendar-nav__btn" id="calendar-next" aria-label="Следующий месяц">&#9654;</button>
              </div>
            </div>
            <div class="calendar-weekdays">
              <span>Пн</span><span>Вт</span><span>Ср</span><span>Чт</span><span>Пт</span><span>Сб</span><span>Вс</span>
            </div>
            <div class="calendar-days">${daysHtml}</div>
            <button type="button" class="calendar-reset-btn" id="calendar-reset">Сбросить</button>
          `;

          const monthSelect = document.getElementById("calendar-month-select");
          const prevBtn = document.getElementById("calendar-prev");
          const nextBtn = document.getElementById("calendar-next");
          const resetBtn = document.getElementById("calendar-reset");

          monthSelect.addEventListener("change", () => {
            calendarView = new Date(year, parseInt(monthSelect.value, 10), 1);
            renderCalendar();
          });
          prevBtn.addEventListener("click", () => {
            calendarView.setMonth(calendarView.getMonth() - 1);
            renderCalendar();
          });
          nextBtn.addEventListener("click", () => {
            calendarView.setMonth(calendarView.getMonth() + 1);
            renderCalendar();
          });
          resetBtn.addEventListener("click", () => {
            wizard.data.startDate = "";
            if (summaryBlock) summaryBlock.style.display = "none";
            if (wizard.nextBtn) wizard.nextBtn.disabled = true;
            renderCalendar();
          });

          calendarEl.querySelectorAll(".calendar-day:not(.calendar-day--past)").forEach((cell) => {
            cell.addEventListener("click", () => {
              const iso = cell.getAttribute("data-iso");
              setDate(iso);
            });
          });
        }

        renderCalendar();

        const dateInfoBtn = document.getElementById("date-info-btn");
        const dateInfoTooltip = document.getElementById("date-info-tooltip");
        if (dateInfoBtn && dateInfoTooltip) {
          dateInfoBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            const willShow = dateInfoTooltip.hidden;
            dateInfoTooltip.hidden = !willShow;
            if (willShow) {
              setTimeout(() => {
                const closeDateInfo = (ev) => {
                  if (!dateInfoTooltip.contains(ev.target) && ev.target !== dateInfoBtn) {
                    dateInfoTooltip.hidden = true;
                    document.removeEventListener("click", closeDateInfo);
                  }
                };
                document.addEventListener("click", closeDateInfo);
              }, 0);
            }
          });
        }

        if (wizard.data.startDate) {
          setDate(wizard.data.startDate.slice(0, 10));
        } else {
          if (summaryBlock) summaryBlock.style.display = "none";
          if (wizard.nextBtn) wizard.nextBtn.disabled = true;
        }
      }

      requestAnimationFrame(() => {
        wizard.bodyEl.style.opacity = "1";
        wizard.bodyEl.style.transform = "translateY(0)";
      });
    }, 140);

    wizard.backBtn.disabled = wizard.currentStep === 0;
    wizard.backBtn.style.visibility = wizard.currentStep === 0 ? "hidden" : "visible";
    wizard.nextBtn.textContent = step.id === "summary" ? "Создать заявку" : "Далее";
    if (step.id === "startDate") wizard.nextBtn.disabled = !wizard.data.startDate;
  }

  function showError(message) {
    const err = document.getElementById("wizard-error");
    if (err) err.textContent = message || "";
  }

  function collectAndValidateStep() {
    showError("");
    const step = wizard.steps[wizard.currentStep];

    switch (step.id) {
      case "location": {
        const checked = wizard.bodyEl.querySelector('input[name="location"]:checked');
        const custom = document.getElementById("location-custom");
        if (!checked) {
          showError("Пожалуйста, выберите площадку.");
          return false;
        }
        if (checked.value === "custom") {
          const v = custom.value.trim();
          if (!v) {
            showError("Укажите название площадки.");
            return false;
          }
          wizard.data.location = v;
        } else {
          wizard.data.location = checked.value;
        }
        return true;
      }
      case "position": {
        const checked = wizard.bodyEl.querySelector('input[name="position"]:checked');
        const custom = document.getElementById("position-custom");
        if (!checked) {
          showError("Пожалуйста, выберите должность.");
          return false;
        }
        if (checked.value === "custom") {
          const v = custom.value.trim();
          if (!v) {
            showError("Укажите должность.");
            return false;
          }
          wizard.data.position = v;
        } else {
          wizard.data.position = checked.value;
        }
        return true;
      }
      case "headcount": {
        const input = document.getElementById("headcount-input");
        const value = Number(input.value);
        if (!Number.isInteger(value) || value <= 0) {
          showError("Введите корректное количество человек.");
          return false;
        }
        wizard.data.headcount = value;
        return true;
      }
      case "schedule": {
        const checked = wizard.bodyEl.querySelector('input[name="schedule"]:checked');
        const custom = document.getElementById("schedule-custom");
        if (!checked) {
          showError("Пожалуйста, выберите график работы.");
          return false;
        }
        if (checked.value === "custom") {
          const v = custom.value.trim();
          if (!v) {
            showError("Опишите график работы.");
            return false;
          }
          wizard.data.schedule = v;
        } else {
          wizard.data.schedule = checked.value;
        }
        return true;
      }
      case "workTime": {
        const fromEl = document.getElementById("work-time-from");
        const toEl = document.getElementById("work-time-to");
        wizard.data.workTimeFrom = fromEl ? fromEl.value.trim() : "";
        wizard.data.workTimeTo = toEl ? toEl.value.trim() : "";
        if (!wizard.data.workTimeFrom || !wizard.data.workTimeTo) {
          showError("Укажите время работы (от и до).");
          return false;
        }
        return true;
      }
      case "salary": {
        const negotiable = wizard.bodyEl.querySelector('input[name="salary-type"]:checked')?.value === "negotiable";
        if (negotiable) {
          wizard.data.salaryType = "negotiable";
          wizard.data.salary = "договорная";
          return true;
        }
        const input = document.getElementById("salary-input");
        const raw = input ? parseSalaryInput(input.value) : 0;
        if (raw < 1000) {
          showError("Укажите оклад не менее 1 000 ₽.");
          return false;
        }
        if (raw > 1000000) {
          showError("Укажите оклад не более 1 000 000 ₽.");
          return false;
        }
        wizard.data.salaryType = "fixed";
        wizard.data.salary = String(raw);
        return true;
      }
      case "employmentType": {
        const checked = wizard.bodyEl.querySelector('input[name="employment-type"]:checked');
        if (!checked) {
          showError("Выберите вид оформления.");
          return false;
        }
        wizard.data.employmentType = checked.value;
        return true;
      }
      case "requirements": {
        const input = document.getElementById("requirements-input");
        const value = input.value.trim();
        if (!value) {
          showError("Опишите хотя бы ключевые требования.");
          return false;
        }
        wizard.data.requirements = value;
        return true;
      }
      case "startDate": {
        const value = wizard.data.startDate ? String(wizard.data.startDate).trim().slice(0, 10) : "";
        if (!value) {
          showError("Укажите желаемую дату выхода.");
          return false;
        }
        wizard.data.startDate = value;
        return true;
      }
      case "contact": {
        const input = document.getElementById("contact-input");
        const value = input.value.trim();
        if (!value) {
          showError("Укажите контактное лицо.");
          return false;
        }
        wizard.data.contactPerson = value;
        return true;
      }
      case "candidateApproval": {
        const checked = wizard.bodyEl.querySelector('input[name="candidate-approval"]:checked');
        if (!checked) {
          showError("Выберите вариант.");
          return false;
        }
        wizard.data.candidateApprovalRequired = checked.value === "yes";
        return true;
      }
      case "summary":
        return true;
    }
  }

  function startWizard() {
    if (!wizard.el) return;
    wizard.currentStep = 0;
    wizard.el.style.display = "block";
    renderStep();
  }

  function closeWizard() {
    if (!wizard.el) return;
    wizard.el.style.display = "none";
  }

  function resetWizardData() {
    wizard.data.location = null;
    wizard.data.location_custom = "";
    wizard.data.position = null;
    wizard.data.position_custom = "";
    wizard.data.headcount = 1;
    wizard.data.schedule = null;
    wizard.data.schedule_custom = "";
    wizard.data.workTimeFrom = "";
    wizard.data.workTimeTo = "";
    wizard.data.salary = "";
    wizard.data.salaryType = "fixed";
    wizard.data.employmentType = null;
    wizard.data.requirements = "";
    wizard.data.startDate = "";
    wizard.data.contactPerson = "";
    wizard.data.candidateApprovalRequired = null;
    wizard.currentStep = 0;
  }

  function hideSuccessToast() {
    var t = document.getElementById("request-success-toast");
    if (t) {
      t.hidden = true;
      t.classList.remove("is-visible");
      t.style.display = "";
      t.style.visibility = "";
      t.style.opacity = "";
    }
  }

  if (wizard.el) {
    wizard.backBtn.addEventListener("click", () => {
      if (wizard.currentStep === 0) return;
      wizard.currentStep -= 1;
      renderStep();
    });

    wizard.cancelBtn.addEventListener("click", () => {
      closeWizard();
      showRequestsView("list");
    });

    wizard.nextBtn.addEventListener("click", async () => {
      const step = wizard.steps[wizard.currentStep];
      if (!collectAndValidateStep()) return;

      if (step.id === "summary") {
        const d = wizard.data;
        const salaryStr = d.salaryType === "negotiable" ? "Договорная" : (d.salary || "");
        const payload = {
          venue: d.location || "",
          position: d.position || "",
          headcount: d.headcount || 1,
          schedule: d.schedule || "",
          salary: salaryStr,
          employment_type: d.employmentType || "",
          requirements: d.requirements || "",
          start_date: isoToDdMmYyyy((d.startDate || "").slice(0, 10)),
          contact: d.contactPerson || "",
          work_time: buildWorkTimeValue(d.workTimeFrom, d.workTimeTo),
          candidate_approval_required: d.candidateApprovalRequired === true,
        };

        wizard.nextBtn.disabled = true;
        if (wizard.backBtn) wizard.backBtn.disabled = true;
        if (wizard.cancelBtn) wizard.cancelBtn.disabled = true;

        closeWizard();
        var toast = document.getElementById("request-success-toast");
        if (toast) {
          toast.removeAttribute("hidden");
          toast.classList.add("is-visible");
          toast.style.display = "flex";
          toast.style.visibility = "visible";
          toast.style.opacity = "1";
        }

        try {
          if (window.HRTelegramWebApp && window.HRTelegramWebApp.haptic) {
            window.HRTelegramWebApp.haptic("notificationOccurred");
          }
        } catch (err) {}

        (window.apiFetch || fetch)("/api/requests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }).catch(function () {});

        return;
      }

      wizard.currentStep += 1;
      renderStep();
    });
  }

  var btnCreateAnother = document.getElementById("success-toast-create-another");
  var btnCloseToast = document.getElementById("success-toast-close");
  if (btnCreateAnother) {
    btnCreateAnother.addEventListener("click", function () {
      hideSuccessToast();
      resetWizardData();
      if (wizard.nextBtn) wizard.nextBtn.disabled = false;
      if (wizard.backBtn) wizard.backBtn.disabled = false;
      if (wizard.cancelBtn) wizard.cancelBtn.disabled = false;
      startWizard();
    });
  }
  if (btnCloseToast) {
    btnCloseToast.addEventListener("click", function () {
      hideSuccessToast();
      if (window.HRTelegramWebApp && window.HRTelegramWebApp.close) {
        window.HRTelegramWebApp.close();
      }
    });
  }
});
