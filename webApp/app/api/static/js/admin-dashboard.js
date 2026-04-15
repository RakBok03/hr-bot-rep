(function () {
  var root = document.getElementById("admin-dashboard");
  var hint = document.getElementById("admin-dashboard-hint");
  if (!root) return;

  function escapeHtml(str) {
    if (str == null) return "";
    var div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
  }

  function isoToday() {
    var d = new Date();
    var yyyy = d.getFullYear();
    var mm = String(d.getMonth() + 1).padStart(2, "0");
    var dd = String(d.getDate()).padStart(2, "0");
    return yyyy + "-" + mm + "-" + dd;
  }

  function isoDaysAgo(days) {
    var d = new Date();
    d.setDate(d.getDate() - days);
    var yyyy = d.getFullYear();
    var mm = String(d.getMonth() + 1).padStart(2, "0");
    var dd = String(d.getDate()).padStart(2, "0");
    return yyyy + "-" + mm + "-" + dd;
  }

  var fromInput = document.getElementById("dash-from");
  var toInput = document.getElementById("dash-to");
  var kpiEl = document.getElementById("dash-kpi");
  var chartEl = document.getElementById("dash-chart");
  var venuesEl = document.getElementById("dash-top-venues");

  var chart = null;
  function ensureChart() {
    if (!chartEl || typeof window.echarts === "undefined") return null;
    if (!chart) chart = window.echarts.init(chartEl);
    return chart;
  }

  function setVisible(isVisible) {
    root.hidden = !isVisible;
    if (hint) hint.hidden = isVisible;
  }

  function kpiCard(title, value) {
    return (
      '<div class="kpi-card">' +
      '<div class="kpi-card__title">' + escapeHtml(title) + "</div>" +
      '<div class="kpi-card__value">' + escapeHtml(String(value)) + "</div>" +
      "</div>"
    );
  }

  function renderKpi(kpi) {
    if (!kpiEl) return;
    var html = [
      kpiCard("Заявок создано", kpi.requests_created || 0),
      kpiCard("Заявок закрыто", kpi.requests_closed || 0),
      kpiCard("Заявок отменено", kpi.requests_cancelled || 0),
      kpiCard("Кандидатов добавлено", kpi.candidates_created || 0),
      kpiCard("Собеседований", kpi.interviews_scheduled || 0),
      kpiCard("Нанято", kpi.hired || 0),
      kpiCard("Отказов", kpi.rejected || 0),
    ].join("");
    kpiEl.innerHTML = html;
  }

  function renderVenues(list) {
    if (!venuesEl) return;
    if (!list || !list.length) {
      venuesEl.innerHTML = '<div class="dashboard-empty">Нет данных</div>';
      return;
    }
    venuesEl.innerHTML =
      '<div class="dash-table">' +
      list
        .map(function (row, idx) {
          return (
            '<div class="dash-table__row">' +
            '<div class="dash-table__cell dash-table__cell--idx">' + (idx + 1) + "</div>" +
            '<div class="dash-table__cell dash-table__cell--name">' + escapeHtml(row.venue || "—") + "</div>" +
            '<div class="dash-table__cell dash-table__cell--num">' + escapeHtml(String(row.count || 0)) + "</div>" +
            "</div>"
          );
        })
        .join("") +
      "</div>";
  }

  function renderChart(ts) {
    var c = ensureChart();
    if (!c) return;
    var dates = (ts || []).map(function (p) { return p.date; });
    var req = (ts || []).map(function (p) { return p.requests_created || 0; });
    var interviews = (ts || []).map(function (p) { return p.interviews_scheduled || 0; });
    var hired = (ts || []).map(function (p) { return p.hired || 0; });
    var rejected = (ts || []).map(function (p) { return p.rejected || 0; });

    c.setOption({
      tooltip: { trigger: "axis" },
      legend: {
        data: ["Заявки", "Собес", "Нанято", "Отказ"],
        top: 0,
        left: "center",
        itemWidth: 12,
        itemHeight: 8,
        itemGap: 10,
        textStyle: { fontSize: 10 },
        padding: [0, 0, 4, 0]
      },
      grid: { left: 8, right: 8, top: 36, bottom: 20, containLabel: true },
      xAxis: { type: "category", data: dates },
      yAxis: { type: "value" },
      series: [
        { name: "Заявки", type: "line", smooth: true, data: req },
        { name: "Собес", type: "line", smooth: true, data: interviews },
        { name: "Нанято", type: "line", smooth: true, data: hired },
        { name: "Отказ", type: "line", smooth: true, data: rejected },
      ],
    });
    window.addEventListener("resize", function () {
      try { c.resize(); } catch (e) {}
    });
  }

  function fetchDashboard(fromIso, toIso) {
    var url = "/api/admin/dashboard?from=" + encodeURIComponent(fromIso) + "&to=" + encodeURIComponent(toIso) + "&group_by=day";
    return (window.apiFetch || fetch)(url).then(function (r) {
      if (!r.ok) {
        console.error("Dashboard fetch failed", r.status, r.statusText);
        return Promise.reject(r);
      }
      return r.json();
    });
  }

  function applyRange(fromIso, toIso) {
    if (fromInput) fromInput.value = fromIso;
    if (toInput) toInput.value = toIso;
    if (kpiEl) kpiEl.innerHTML = '<div class="dashboard-empty">Загрузка…</div>';
    fetchDashboard(fromIso, toIso)
      .then(function (data) {
        renderKpi(data.kpi || {});
        renderChart(data.timeseries || []);
        var venues = (data.breakdowns && data.breakdowns.top_venues_requests) ? data.breakdowns.top_venues_requests : [];
        renderVenues(venues);
      })
      .catch(function (err) {
        console.error("Dashboard applyRange error", err);
        if (kpiEl) kpiEl.innerHTML = '<div class="dashboard-empty">Не удалось загрузить данные</div>';
      });
  }

  function init() {
    setVisible(!!window.HR_ADMIN_MODE);
    if (!window.HR_ADMIN_MODE) return;

    var toIso = isoToday();
    var fromIso = isoDaysAgo(29);
    applyRange(fromIso, toIso);
  }

  root.querySelectorAll(".dashboard__preset-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      root.querySelectorAll(".dashboard__preset-btn").forEach(function (b) {
        b.classList.toggle("dashboard__preset-btn--active", b === btn);
      });
      var days = parseInt(btn.getAttribute("data-range"), 10) || 30;
      var toIso = isoToday();
      var fromIso = isoDaysAgo(days - 1);
      applyRange(fromIso, toIso);
    });
  });

  function onDateChange() {
    if (!fromInput || !toInput) return;
    var fromIso = fromInput.value;
    var toIso = toInput.value;
    if (!fromIso || !toIso) return;
    applyRange(fromIso, toIso);
  }

  if (fromInput) fromInput.addEventListener("change", onDateChange);
  if (toInput) toInput.addEventListener("change", onDateChange);

  window.DashboardScreen = {
    render: init,
  };
})();

