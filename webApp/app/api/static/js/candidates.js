(function () {
  var container = document.getElementById("candidates-content");
  var detailModal = document.getElementById("candidate-detail-modal");
  var detailTitle = document.getElementById("candidate-detail-title");
  var detailBody = document.getElementById("candidate-detail-body");
  var detailBackdrop = document.getElementById("candidate-detail-backdrop");
  var detailCloseBtn = document.getElementById("candidate-detail-close-btn");
  var detailBtnHired = document.getElementById("candidate-detail-btn-hired");
  var detailBtnReschedule = document.getElementById("candidate-detail-btn-reschedule");
  var detailBtnReject = document.getElementById("candidate-detail-btn-reject");
  var rejectModal = document.getElementById("candidate-reject-modal");
  var rejectBackdrop = document.getElementById("candidate-reject-backdrop");
  var rejectComment = document.getElementById("candidate-reject-comment");
  var rejectCancel = document.getElementById("candidate-reject-cancel");
  var rejectSubmit = document.getElementById("candidate-reject-submit");
  var rejectCloseBtn = document.getElementById("candidate-reject-close-btn");
  var rescheduleModal = document.getElementById("candidate-reschedule-modal");
  var rescheduleBackdrop = document.getElementById("candidate-reschedule-backdrop");
  var rescheduleDate = document.getElementById("candidate-reschedule-date");
  var rescheduleTime = document.getElementById("candidate-reschedule-time");
  var rescheduleCancel = document.getElementById("candidate-reschedule-cancel");
  var rescheduleSubmit = document.getElementById("candidate-reschedule-submit");
  var rescheduleCloseBtn = document.getElementById("candidate-reschedule-close-btn");

  var currentCandidateId = null;


  var STATUS_LABELS = {
    new: "Новая",
    interview: "Собеседование",
    sobes: "Собеседование",
    hired: "Принят",
    rejected: "Отказ",
    offer: "Оффер",
  };

  var ACTUAL_STATUSES = ["new", "interview", "sobes"];
  var lastCandidatesList = [];
  var currentCandidatesFilter = "actual";
  function normalizeStatus(status) {
    var s = String(status || "").trim().toLowerCase();
    if (!s) return "";
    if (s === "собес" || s === "собеседование") return "sobes";
    return s;
  }

  var candidatesArchiveYear = null;
  var candidatesArchiveMonth = null;

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

  function ensureCandidatesArchiveCalendarState() {
    if (candidatesArchiveYear !== null && candidatesArchiveMonth !== null) return;
    var cur = getCurrentYearMonth();
    candidatesArchiveYear = cur.year;
    candidatesArchiveMonth = cur.month;
  }

  function candidateDateInMonth(c, year, month) {
    var dateStr = c.decision_date || c.created_at || "";
    var ym = getYearMonthFromDateStr(dateStr);
    return ym && ym.year === year && ym.month === month;
  }

  function statusLabel(status) {
    var norm = normalizeStatus(status);
    return (norm && STATUS_LABELS[norm]) ? STATUS_LABELS[norm] : (status || "—");
  }

  function getActualStatusEmoji(status) {
    var norm = normalizeStatus(status);
    if (norm === "interview" || norm === "sobes") return "📢";
    if (norm === "new") return "🆕";
    return "";
  }

  if (!container) return;

  function escapeHtml(str) {
    if (str == null) return "";
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatDate(val) {
    if (val == null || val === "") return "—";
    var s = String(val).trim();
    if (/^\d{1,2}\.\d{1,2}\.\d{4}( \d{1,2}:\d{2})?$/.test(s)) return s;
    var match = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) return match[3] + "." + match[2] + "." + match[1];
    var matchT = s.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (matchT) return matchT[3] + "." + matchT[2] + "." + matchT[1] + " " + matchT[4] + ":" + matchT[5];
    return s;
  }

  function row(label, value) {
    return (
      '<div class="request-detail-row">' +
      '<div class="request-detail-row__label">' + escapeHtml(label) + "</div>" +
      '<div class="request-detail-row__value">' + escapeHtml(value || "—") + "</div>" +
      "</div>"
    );
  }
  function rowHtml(label, html) {
    return (
      '<div class="request-detail-row">' +
      '<div class="request-detail-row__label">' + escapeHtml(label) + "</div>" +
      '<div class="request-detail-row__value">' + (html || "—") + "</div>" +
      "</div>"
    );
  }

  function fillDetailBody(data) {
    var venuePos = [data.request_venue, data.request_position].filter(Boolean).join(" · ") || "—";
    detailBody.innerHTML =
      row("ID заявки", data.request_id != null ? String(data.request_id) : "—") +
      row("ФИО", data.full_name) +
      row("Возраст", data.age != null ? String(data.age) : "—") +
      row("Опыт работы", data.work_experience) +
      row("Номер телефона", data.contact) +
      rowHtml("Ссылка на резюме", data.resume_url ? '<a href="' + escapeHtml(data.resume_url) + '" target="_blank" rel="noopener">' + escapeHtml(data.resume_url) + "</a>" : "—") +
      row("Дата хантинга", formatDate(data.hunting_date || data.created_at)) +
      row("Дата собеседования", formatDate(data.interview_date)) +
      row("Дата решения", formatDate(data.decision_date)) +
      row("Статус", statusLabel(data.status)) +
      row("Заявка", venuePos);
  }

  function setDetailActionsReadonly(readonly) {
    var isReadonly = !!readonly;
    [detailBtnHired, detailBtnReschedule, detailBtnReject].forEach(function (btn) {
      if (!btn) return;
      btn.hidden = isReadonly;
      btn.disabled = isReadonly;
    });
  }

  function openDetail(candidateId, isArchiveView) {
    if (!detailModal || !detailBody) return;
    currentCandidateId = candidateId;
    setDetailActionsReadonly(isArchiveView);
    detailBody.innerHTML = '<div class="my-requests-loading">Загрузка…</div>';
    detailTitle.textContent = "Кандидат";
    detailModal.hidden = false;
    (window.apiFetch || fetch)("/api/candidates/" + candidateId)
      .then(function (res) {
        if (!res.ok) throw new Error("Not found");
        return res.json();
      })
      .then(fillDetailBody)
      .catch(function () {
        detailBody.innerHTML = '<p class="request-detail-error">Не удалось загрузить данные.</p>';
      });
  }

  function closeDetail() {
    if (detailModal) detailModal.hidden = true;
  }

  function renderList(list, isArchive) {
    if (list.length === 0) {
      if (isArchive) {
        container.innerHTML =
          '<div class="my-requests-empty">' +
          '<p class="my-requests-empty__text">В архиве пока нет кандидатов</p>' +
          '<p class="my-requests-empty__hint">Завершённые кандидаты (принят / отказ) появятся здесь.</p>' +
          "</div>";
      } else {
        container.innerHTML =
          '<div class="my-requests-empty">' +
          '<p class="my-requests-empty__text">Кандидатов пока нет</p>' +
          '<p class="my-requests-empty__hint">Кандидаты по вашим заявкам появятся здесь.</p>' +
          "</div>";
      }
      return;
    }
    container.innerHTML = list
      .map(function (c) {
        var venue = c.request_venue || "—";
        var position = c.request_position || "—";
        var statusText = statusLabel(c.status);
        var createdStr = formatDate(c.created_at);
        var fullName = c.full_name || "—";
        var emoji = getActualStatusEmoji(c.status);
        var badgeHtml = emoji ? '<span class="my-requests-card__status" aria-hidden="true">' + emoji + "</span>" : "";
        return (
          '<div class="my-requests-card" data-id="' + c.id + '">' +
          badgeHtml +
          '<div class="my-requests-card__title">' + escapeHtml(position) + "</div>" +
          '<div class="my-requests-card__meta">' + escapeHtml(venue) + ' · ' + escapeHtml(statusText) + "</div>" +
          '<div class="my-requests-card__count">Кандидат: ' + escapeHtml(fullName) + "</div>" +
          '<div class="my-requests-card__dates">' +
          '<div class="my-requests-card__date-row">Добавлен: ' + escapeHtml(createdStr) + "</div>" +
          "</div>" +
          "</div>"
        );
      })
      .join("");
  }

  function applyCandidatesFilterAndRender() {
    updateCandidatesArchiveCalendarUI();
    var isArchive = currentCandidatesFilter === "archive";
    var filtered = isArchive
      ? lastCandidatesList.filter(function (c) { return ACTUAL_STATUSES.indexOf(normalizeStatus(c.status)) === -1; })
      : lastCandidatesList.filter(function (c) { return ACTUAL_STATUSES.indexOf(normalizeStatus(c.status)) !== -1; });
    if (isArchive) {
      ensureCandidatesArchiveCalendarState();
      filtered = filtered.filter(function (c) { return candidateDateInMonth(c, candidatesArchiveYear, candidatesArchiveMonth); });
      if (filtered.length > 0) {
        filtered = filtered.slice().sort(function (a, b) {
          var da = a.decision_date || a.created_at || "";
          var db = b.decision_date || b.created_at || "";
          return da > db ? -1 : da < db ? 1 : 0;
        });
      }
    }
    renderList(filtered, isArchive);
  }

  function updateCandidatesArchiveCalendarUI() {
    var cal = document.getElementById("candidates-archive-calendar");
    var sel = document.getElementById("candidates-archive-month");
    var prevBtn = document.getElementById("candidates-archive-prev");
    var nextBtn = document.getElementById("candidates-archive-next");
    if (!cal || !sel) return;
    if (currentCandidatesFilter !== "archive") {
      cal.hidden = true;
      return;
    }
    cal.hidden = false;
    ensureCandidatesArchiveCalendarState();
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
    sel.value = candidatesArchiveYear + "-" + (candidatesArchiveMonth < 10 ? "0" + candidatesArchiveMonth : candidatesArchiveMonth);
    if (prevBtn) prevBtn.disabled = candidatesArchiveYear <= minYear && candidatesArchiveMonth <= 1;
    if (nextBtn) nextBtn.disabled = candidatesArchiveYear >= cur.year && candidatesArchiveMonth >= cur.month;
  }

  function render() {
    container.innerHTML = '<div class="my-requests-loading">Загрузка…</div>';
    var url = window.HR_ADMIN_MODE ? "/api/admin/candidates" : "/api/candidates";
    (window.apiFetch || fetch)(url)
      .then(function (res) {
        if (!res.ok) return { candidates: [] };
        return res.json();
      })
      .then(function (data) {
        lastCandidatesList = (data && data.candidates) ? data.candidates : [];
        applyCandidatesFilterAndRender();
      })
      .catch(function () {
        container.innerHTML =
          '<div class="my-requests-empty">' +
          '<p class="my-requests-empty__text">Не удалось загрузить список</p>' +
          "</div>";
      });
  }

  (function initCandidatesFilterRadios() {
    var radios = document.querySelectorAll('input[name="candidates-filter"]');
    for (var i = 0; i < radios.length; i++) {
      radios[i].addEventListener("change", function () {
        currentCandidatesFilter = this.value;
        updateCandidatesArchiveCalendarUI();
        applyCandidatesFilterAndRender();
      });
    }
  })();

  (function initCandidatesArchiveCalendar() {
    var cal = document.getElementById("candidates-archive-calendar");
    var sel = document.getElementById("candidates-archive-month");
    var prevBtn = document.getElementById("candidates-archive-prev");
    var nextBtn = document.getElementById("candidates-archive-next");
    if (!cal || !sel) return;
    updateCandidatesArchiveCalendarUI();
    sel.addEventListener("change", function () {
      var parts = sel.value.split("-");
      if (parts.length !== 2) return;
      candidatesArchiveYear = parseInt(parts[0], 10);
      candidatesArchiveMonth = parseInt(parts[1], 10);
      applyCandidatesFilterAndRender();
      updateCandidatesArchiveCalendarUI();
    });
    if (prevBtn) prevBtn.addEventListener("click", function () {
      if (prevBtn.disabled) return;
      candidatesArchiveMonth--;
      if (candidatesArchiveMonth < 1) { candidatesArchiveMonth = 12; candidatesArchiveYear--; }
      ensureCandidatesArchiveCalendarState();
      applyCandidatesFilterAndRender();
      updateCandidatesArchiveCalendarUI();
    });
    if (nextBtn) nextBtn.addEventListener("click", function () {
      if (nextBtn.disabled) return;
      var cur = getCurrentYearMonth();
      if (candidatesArchiveYear > cur.year || (candidatesArchiveYear === cur.year && candidatesArchiveMonth >= cur.month)) return;
      candidatesArchiveMonth++;
      if (candidatesArchiveMonth > 12) { candidatesArchiveMonth = 1; candidatesArchiveYear++; }
      ensureCandidatesArchiveCalendarState();
      applyCandidatesFilterAndRender();
      updateCandidatesArchiveCalendarUI();
    });
  })();

  container.addEventListener("click", function (e) {
    var card = e.target.closest(".my-requests-card");
    if (!card) return;
    var id = card.getAttribute("data-id");
    if (id) openDetail(id, currentCandidatesFilter === "archive");
  });

  var editSentHrModal = document.getElementById("edit-sent-hr-modal");

  function setCandidateStatus(status) {
    if (currentCandidateId == null) return;
    if (status === "hired") {
      if (editSentHrModal) editSentHrModal.hidden = false;
      closeDetail();
      (window.apiFetch || fetch)("/api/candidates/" + currentCandidateId, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "hired" }),
      })
        .then(function (res) {
          if (!res.ok) {
            if (editSentHrModal) editSentHrModal.hidden = true;
            return;
          }
          if (window.CandidatesScreen && window.CandidatesScreen.render) window.CandidatesScreen.render();
        })
        .catch(function () {
          if (editSentHrModal) editSentHrModal.hidden = true;
        });
    }
  }

  function openRejectModal() {
    if (currentCandidateId == null || !rejectModal) return;
    if (rejectComment) {
      rejectComment.value = "";
      rejectComment.removeAttribute("aria-invalid");
    }
    if (rejectSubmit) rejectSubmit.disabled = true;
    closeDetail();
    rejectModal.hidden = false;
  }

  function closeRejectModal() {
    if (rejectModal) rejectModal.hidden = true;
  }

  function updateRejectSubmitState() {
    var comment = (rejectComment && rejectComment.value) ? rejectComment.value.trim() : "";
    if (rejectSubmit) rejectSubmit.disabled = comment.length === 0;
  }

  function submitReject() {
    if (currentCandidateId == null) return;
    var comment = (rejectComment && rejectComment.value) ? rejectComment.value.trim() : "";
    if (!comment) {
      if (rejectComment) {
        rejectComment.setAttribute("aria-invalid", "true");
        rejectComment.focus();
      }
      return;
    }
    if (editSentHrModal) editSentHrModal.hidden = false;
    closeRejectModal();
    (window.apiFetch || fetch)("/api/candidates/" + currentCandidateId, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "rejected", result_notes: comment }),
    })
      .then(function (res) {
        if (!res.ok) {
          if (editSentHrModal) editSentHrModal.hidden = true;
          return;
        }
        if (window.CandidatesScreen && window.CandidatesScreen.render) window.CandidatesScreen.render();
      })
      .catch(function () {
        if (editSentHrModal) editSentHrModal.hidden = true;
      });
  }

  if (detailBackdrop) detailBackdrop.addEventListener("click", closeDetail);
  if (detailCloseBtn) detailCloseBtn.addEventListener("click", closeDetail);
  if (detailBtnHired) detailBtnHired.addEventListener("click", function () { setCandidateStatus("hired"); });
  if (detailBtnReject) detailBtnReject.addEventListener("click", openRejectModal);
  if (rejectComment) rejectComment.addEventListener("input", function () {
    updateRejectSubmitState();
    if (rejectComment) rejectComment.removeAttribute("aria-invalid");
  });
  if (rejectCancel) rejectCancel.addEventListener("click", closeRejectModal);
  if (rejectSubmit) rejectSubmit.addEventListener("click", submitReject);
  if (rejectBackdrop) rejectBackdrop.addEventListener("click", closeRejectModal);
  if (rejectCloseBtn) rejectCloseBtn.addEventListener("click", closeRejectModal);

  function openRescheduleModal() {
    if (currentCandidateId == null || !rescheduleModal) return;
    var today = new Date();
    var dateStr = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0") + "-" + String(today.getDate()).padStart(2, "0");
    if (rescheduleDate) rescheduleDate.value = dateStr;
    if (rescheduleTime) rescheduleTime.value = "10:00";
    closeDetail();
    rescheduleModal.hidden = false;
  }

  function closeRescheduleModal() {
    if (rescheduleModal) rescheduleModal.hidden = true;
  }

  function submitReschedule() {
    if (currentCandidateId == null) return;
    var dateVal = rescheduleDate ? rescheduleDate.value : "";
    var timeVal = rescheduleTime ? rescheduleTime.value : "";
    if (!dateVal || !timeVal) return;
    var interviewDate = dateVal + "T" + timeVal + ":00";
    if (editSentHrModal) editSentHrModal.hidden = false;
    closeRescheduleModal();
    (window.apiFetch || fetch)("/api/candidates/" + currentCandidateId, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interview_date: interviewDate }),
    })
      .then(function (res) {
        if (!res.ok) {
          if (editSentHrModal) editSentHrModal.hidden = true;
          return;
        }
        if (window.CandidatesScreen && window.CandidatesScreen.render) window.CandidatesScreen.render();
      })
      .catch(function () {
        if (editSentHrModal) editSentHrModal.hidden = true;
      });
  }

  if (detailBtnReschedule) detailBtnReschedule.addEventListener("click", openRescheduleModal);
  if (rescheduleCancel) rescheduleCancel.addEventListener("click", closeRescheduleModal);
  if (rescheduleSubmit) rescheduleSubmit.addEventListener("click", submitReschedule);
  if (rescheduleBackdrop) rescheduleBackdrop.addEventListener("click", closeRescheduleModal);
  if (rescheduleCloseBtn) rescheduleCloseBtn.addEventListener("click", closeRescheduleModal);

  render();
  window.CandidatesScreen = { render: render };
})();
