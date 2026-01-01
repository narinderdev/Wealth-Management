document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.querySelector(".visibility-toggle");
  const passwordField = document.querySelector("#password");
  if (!toggleBtn || !passwordField) return;

  toggleBtn.addEventListener("click", () => {
    const isPassword = passwordField.getAttribute("type") === "password";
    passwordField.setAttribute("type", isPassword ? "text" : "password");
    toggleBtn.setAttribute("aria-pressed", String(isPassword));
  });
});
