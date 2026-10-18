document.addEventListener("DOMContentLoaded", () => {
    const message = document.querySelector("[data-contact-message]");
    const counter = document.querySelector("[data-contact-count]");

    if (!message || !counter) {
        return;
    }

    const updateCount = () => {
        counter.textContent = message.value.length;
    };

    message.addEventListener("input", updateCount);
    updateCount();
});
