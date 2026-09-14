/* Simple FitSync light/dark mode toggle */
document.addEventListener("DOMContentLoaded", function () {
    const root = document.documentElement;
    const themeButtons = document.querySelectorAll("[data-theme-toggle]");

    let savedTheme = localStorage.getItem("fitsync-theme");

    if (!savedTheme) {
        savedTheme = "light";
    }

    setTheme(savedTheme);

    themeButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const currentTheme = root.getAttribute("data-theme");

            if (currentTheme === "dark") {
                setTheme("light");
                localStorage.setItem("fitsync-theme", "light");
            } else {
                setTheme("dark");
                localStorage.setItem("fitsync-theme", "dark");
            }
        });
    });

    function setTheme(theme) {
        root.setAttribute("data-theme", theme);
        root.setAttribute("data-bs-theme", theme);

        themeButtons.forEach(function (button) {
            const icon = button.querySelector("[data-theme-icon]");

            if (theme === "dark") {
                button.setAttribute("aria-label", "Switch to light mode");

                if (icon) {
                    icon.className = "bi bi-sun";
                }
            } else {
                button.setAttribute("aria-label", "Switch to dark mode");

                if (icon) {
                    icon.className = "bi bi-moon-stars";
                }
            }
        });
    }
});
