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
