/* FitSync light/dark theme toggle */
(function () {
    const STORAGE_KEY = "fitsync-theme";
    const root = document.documentElement;

    function getSavedTheme() {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved === "dark" ? "dark" : "light";
    }

    function updateButtons(theme) {
        document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
            const icon = button.querySelector("[data-theme-icon]");
            const isDark = theme === "dark";

            button.setAttribute("aria-pressed", isDark ? "true" : "false");
            button.setAttribute(
                "aria-label",
                isDark ? "Switch to light mode" : "Switch to dark mode"
            );
            button.setAttribute(
                "title",
                isDark ? "Switch to light mode" : "Switch to dark mode"
            );

            if (icon) {
                icon.className = isDark ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
            }
        });
    }

    function applyTheme(theme, saveTheme) {
        root.setAttribute("data-theme", theme);
        root.setAttribute("data-bs-theme", theme);

        if (document.body) {
            document.body.setAttribute("data-theme", theme);
        }

        if (saveTheme) {
            localStorage.setItem(STORAGE_KEY, theme);
        }

        updateButtons(theme);
    }

    // Apply the saved theme as early as possible.
    applyTheme(getSavedTheme(), false);

    document.addEventListener("DOMContentLoaded", function () {
        applyTheme(getSavedTheme(), false);

        document.addEventListener("click", function (event) {
            const button = event.target.closest("[data-theme-toggle]");

            if (!button) {
                return;
            }

            event.preventDefault();

            const currentTheme = root.getAttribute("data-theme") === "dark"
                ? "dark"
                : "light";
            const newTheme = currentTheme === "dark" ? "light" : "dark";

            applyTheme(newTheme, true);
        });
    });
})();
