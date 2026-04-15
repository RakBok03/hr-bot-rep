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
