(function () {
  var tg = typeof window !== "undefined" && window.Telegram && window.Telegram.WebApp;
  if (!tg) {
    window.HRTelegramWebApp = {
      isAvailable: false,
      initData: function () { return ""; },
      getApiHeaders: function () { return {}; },
      haptic: function () {},
    };
    return;
  }

  tg.ready();
  tg.expand();

  if (tg.themeParams) {
    tg.setHeaderColor("#0a1428");
    tg.setBackgroundColor("#050d1f");
  }

  tg.enableClosingConfirmation();

  function haptic(type) {
    try {
      var h = tg.HapticFeedback;
      if (!h) return;
      if (type === "notificationOccurred") {
        if (typeof h.notificationOccurred === "function") {
          var p = h.notificationOccurred("success");
          if (p && typeof p.catch === "function") p.catch(function () {});
        }
        return;
      }
      if (typeof h[type] === "function") {
        var q = h[type]();
        if (q && typeof q.catch === "function") q.catch(function () {});
      }
    } catch (e) {}
  }

  window.HRTelegramWebApp = {
    isAvailable: true,
    tg: tg,
    initData: function () {
      return tg.initData || "";
    },
    getApiHeaders: function () {
      var data = tg.initData || "";
      if (!data) return {};
      return { "X-Telegram-Init-Data": data };
    },
    haptic: haptic,
    close: function () {
      if (tg.close) tg.close();
    },
  };
})();
