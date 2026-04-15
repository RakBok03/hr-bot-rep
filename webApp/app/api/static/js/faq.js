document.addEventListener("DOMContentLoaded", function () {
  function escapeHtml(str) {
    if (str == null) return "";
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  var faqData = [
    { q: "Когда нужно создавать заявку на сотрудника?", a: "Заявку необходимо оформить минимум за 2 дня до планируемой даты выхода сотрудника. HR-отделу требуется 2–3 дня для подбора кандидата." },
    { q: "Можно ли оформить срочную заявку «на сегодня»?", a: "Нет. Подбор персонала требует времени. Заявки в день выхода сотрудника не обрабатываются." },
    { q: "Что делать, если кандидат уже найден самостоятельно?", a: "В этом случае необходимо сообщить HR, чтобы закрыть заявку и обновить статус." },
    { q: "Нужно ли давать обратную связь по кандидатам?", a: "Да. Если кандидат был направлен HR, необходимо сообщить результат собеседования: принят, отказ или требуется дополнительное рассмотрение. Это помогает ускорить подбор и избежать лишних приглашений." },
    { q: "Можно ли отказать кандидату без причины?", a: "Если кандидат не подходит, желательно кратко указать причину отказа. Это помогает HR корректнее подбирать следующих кандидатов." },
    { q: "Что делать, если потребность в сотруднике изменилась?", a: "Если заявка стала неактуальной или условия изменились, необходимо обновить заявку или уведомить HR." },
    { q: "Что делать, если кандидат не вышел на смену?", a: "Необходимо сообщить HR, чтобы можно было оперативно начать повторный поиск." },
    { q: "Кто отвечает за собеседование кандидата?", a: "HR организует поиск и направляет кандидатов, окончательное решение о приёме принимает площадка." },
    { q: "Где посмотреть свои заявки?", a: "Все созданные заявки можно посмотреть в разделе «Мои заявки»." },
    { q: "Возник вопрос, которого нет в списке?", a: "Свяжитесь с HR напрямую." },
  ];

  var faqList = document.getElementById("faq-list");
  if (faqList) {
    faqList.innerHTML = faqData
      .map(function (item, i) {
        return (
          '<div class="faq-item" data-faq-index="' + i + '">' +
          '<button type="button" class="faq-item__btn" aria-expanded="false" aria-controls="faq-answer-' + i + '" id="faq-btn-' + i + '">' +
          escapeHtml(item.q) +
          "</button>" +
          '<div class="faq-item__answer" id="faq-answer-' + i + '" role="region" aria-labelledby="faq-btn-' + i + '" hidden><p>' +
          escapeHtml(item.a) +
          "</p></div></div>"
        );
      })
      .join("");
    faqList.querySelectorAll(".faq-item__btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var item = btn.closest(".faq-item");
        var answer = item.querySelector(".faq-item__answer");
        var isOpen = item.classList.toggle("faq-item--open");
        btn.setAttribute("aria-expanded", isOpen);
        answer.hidden = !isOpen;
      });
    });
  }

  var helpRoleRadios = document.querySelectorAll('input[name="help-role"]');
  var HELP_ROLE_KEY = "hr-help-role";
  if (helpRoleRadios.length) {
    var savedRole = null;
    try {
      savedRole = localStorage.getItem(HELP_ROLE_KEY);
    } catch (e) {}
    if (savedRole === "employee" || savedRole === "hr" || savedRole === "admin") {
      var r = document.querySelector('input[name="help-role"][value="' + savedRole + '"]');
      if (r) r.checked = true;
    }
    helpRoleRadios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        try {
          localStorage.setItem(HELP_ROLE_KEY, this.value);
        } catch (e) {}
      });
    });
  }
});
