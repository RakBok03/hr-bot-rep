(function () {
  var bottomNav = document.getElementById("bottom-nav");
  var navItems = bottomNav ? bottomNav.querySelectorAll(".bottom-nav__item") : [];

  function setActiveNavItem(targetScreen, view) {
    if (!navItems.length) return;
    for (var i = 0; i < navItems.length; i++) {
      var btn = navItems[i];
      var t = btn.getAttribute("data-target");
      var v = btn.getAttribute("data-view");
      var active = t === targetScreen && (view == null ? !v : v === view);
      btn.classList.toggle("bottom-nav__item--active", !!active);
    }
  }

  function init(callbacks) {
    if (!bottomNav || !callbacks) return;
    var showScreen = callbacks.showScreen;
    var showRequestsView = callbacks.showRequestsView;
    var getWizardEl = callbacks.getWizardEl;
    for (var i = 0; i < navItems.length; i++) {
      (function (item) {
        item.addEventListener("click", function () {
          var target = item.getAttribute("data-target");
          var view = item.getAttribute("data-view");
          if (!target) return;
          showScreen(target);
          if (target === "requests" && view) {
            showRequestsView(view);
          } else if (target === "requests" && !view && getWizardEl && getWizardEl()) {
            showRequestsView("create");
          } else {
            setActiveNavItem(target, null);
          }
        });
      })(navItems[i]);
    }
  }

  window.BottomNav = { init: init, setActiveNavItem: setActiveNavItem };
})();
