(function () {
  var STORAGE_KEY = "hr-admin-mode";
  var btn = document.getElementById("header-admin-btn");
  if (!btn) return;

  function setBtnState(enabled) {
    btn.hidden = false;
    btn.classList.toggle("app-header__admin-btn--on", !!enabled);
    btn.setAttribute("aria-pressed", enabled ? "true" : "false");
    btn.textContent = enabled ? "Админ: Вкл" : "Админ: Выкл";
  }

  function setNavAdmin(enabled) {
    var nav = document.getElementById("bottom-nav");
    if (!nav) return;
    var items = nav.querySelectorAll(".bottom-nav__item");
    if (items.length < 4) return;

    window.HR_ADMIN_MODE = !!enabled;

    if (enabled) {
      items[0].setAttribute("data-target", "dashboard");
      items[0].removeAttribute("data-view");
      var label0 = items[0].querySelector(".bottom-nav__label");
      if (label0) label0.textContent = "Отчеты";

      items[1].setAttribute("data-target", "requests");
      items[1].setAttribute("data-view", "list");
      var label1 = items[1].querySelector(".bottom-nav__label");
      if (label1) label1.textContent = "Все заявки";

      items[2].setAttribute("data-target", "candidates");
      items[2].removeAttribute("data-view");
      var label2 = items[2].querySelector(".bottom-nav__label");
      if (label2) label2.textContent = "Все кандидаты";


      items[3].style.display = "none";
    } else {

      items[0].setAttribute("data-target", "requests");
      items[0].setAttribute("data-view", "list");
      var label0d = items[0].querySelector(".bottom-nav__label");
      if (label0d) label0d.textContent = "Мои заявки";

      items[1].setAttribute("data-target", "requests");
      items[1].setAttribute("data-view", "create");
      var label1d = items[1].querySelector(".bottom-nav__label");
      if (label1d) label1d.textContent = "Создать";

      items[2].setAttribute("data-target", "candidates");
      items[2].removeAttribute("data-view");
      var label2d = items[2].querySelector(".bottom-nav__label");
      if (label2d) label2d.textContent = "Кандидаты";

      items[3].style.display = "";
      var label3d = items[3].querySelector(".bottom-nav__label");
      if (label3d) label3d.textContent = "Помощь";
    }

    var reqTitle = document.querySelector('#requests-list-view .screen-title');
    if (reqTitle) reqTitle.textContent = enabled ? "Все заявки" : "Мои заявки";
  }

  function refreshScreens() {
    if (window.DashboardScreen && typeof window.DashboardScreen.render === "function") {
      window.DashboardScreen.render();
    }
    if (window.RequestsScreen && typeof window.RequestsScreen.render === "function") {
      window.RequestsScreen.render();
    }
    if (window.CandidatesScreen && typeof window.CandidatesScreen.render === "function") {
      window.CandidatesScreen.render();
    }
  }

  function apply(enabled) {
    setBtnState(enabled);
    setNavAdmin(enabled);
    refreshScreens();
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
    } catch (e) {}

    var nav = document.getElementById("bottom-nav");
    if (nav) {
      var items = nav.querySelectorAll(".bottom-nav__item");
      if (items && items.length) {
        if (enabled) {
          items[0].click();
        } else {
          items[0].click();
        }
      }
    }
  }

  (window.apiFetch || fetch)("/api/me")
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (me) {
      if (!me || me.is_admin !== true) return;

      var enabled = true;
      try {
        var stored = localStorage.getItem(STORAGE_KEY);
        enabled = stored == null ? true : stored === "1";
      } catch (e) {}
      apply(enabled);

      btn.addEventListener("click", function () {
        enabled = !enabled;
        apply(enabled);
      });
    })
    .catch(function () {});
})();

