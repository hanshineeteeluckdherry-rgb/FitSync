// Small mobile navigation toggle for the standalone Figma-style homepage.
document.addEventListener("DOMContentLoaded", function () {
    const button = document.querySelector(".home-nav-toggle");
    const links = document.querySelector(".home-nav-links");

    if (!button || !links) {
        return;
    }

    button.addEventListener("click", function () {
        const isOpen = links.classList.toggle("show");
        button.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
});
