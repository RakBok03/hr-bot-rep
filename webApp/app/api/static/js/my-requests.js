(function () {
  function escapeHtml(str) {
    if (str == null) return "";
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function renderMyRequests() {
    var container = document.getElementById("my-requests-content");
    if (!container) return;
    container.innerHTML = '<div class="my-requests-loading">Загрузка…</div>';
    (window.apiFetch || fetch)("/api/requests")
      .then(function (res) {
        if (!res.ok) return { requests: [] };
        return res.json();
      })
      .then(function (data) {
        var requests = (data && data.requests) ? data.requests : [];
        if (requests.length === 0) {
          container.innerHTML =
            '<div class="my-requests-empty">' +
            '<p class="my-requests-empty__text">Заявок нет</p>' +
            '<p class="my-requests-empty__hint">Создайте заявку на подбор, нажав «Создать» внизу.</p>' +
            "</div>";
        } else {
          container.innerHTML = requests
            .map(function (r) {
              var statusText = r.status === "new" ? "Новая" : (r.status === "closed" ? "Закрыта" : r.status);
              return (
                '<div class="my-requests-card" data-id="' + r.id + '">' +
                '<div class="my-requests-card__title">' + escapeHtml(r.position || "Заявка") + "</div>" +
                '<div class="my-requests-card__meta">' + escapeHtml(r.venue || "") + " · " + escapeHtml(statusText) + "</div>" +
                "</div>"
              );
            })
            .join("");
        }
      })
      .catch(function () {
        container.innerHTML =
          '<div class="my-requests-empty">' +
          '<p class="my-requests-empty__text">Заявок нет</p>' +
          '<p class="my-requests-empty__hint">Создайте заявку на подбор, нажав «Создать» внизу.</p>' +
          "</div>";
      });
  }

  window.renderMyRequests = renderMyRequests;
})();
