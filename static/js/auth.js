// Small helpers for the Figma-style authentication pages.
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            var input = button.closest(".password-field").querySelector("input");
            var icon = button.querySelector("i");
            var showPassword = input.type === "password";

            input.type = showPassword ? "text" : "password";
            icon.className = showPassword ? "bi bi-eye-slash" : "bi bi-eye";
            button.setAttribute("aria-label", showPassword ? "Hide password" : "Show password");
        });
    });

    var registerScreen = document.querySelector("[data-register-screen]");
    if (!registerScreen) {
        return;
    }

    var stepOne = registerScreen.querySelector('[data-register-step="1"]');
    var stepTwo = registerScreen.querySelector('[data-register-step="2"]');
    var indicators = registerScreen.querySelectorAll("[data-step-indicator]");
    var currentStep = parseInt(registerScreen.dataset.startStep || "1", 10);

    function showStep(step) {
        currentStep = step;
        stepOne.hidden = step !== 1;
        stepTwo.hidden = step !== 2;

        indicators.forEach(function (indicator) {
            var indicatorStep = parseInt(indicator.dataset.stepIndicator, 10);
            indicator.classList.toggle("is-active", indicatorStep === step);
            indicator.classList.toggle("is-complete", indicatorStep < step);
        });
    }

    var nextButton = registerScreen.querySelector("[data-next-step]");
    var previousButton = registerScreen.querySelector("[data-previous-step]");

    nextButton.addEventListener("click", function () {
        // Browser validation keeps the first step simple for the user.
        var firstStepInputs = stepOne.querySelectorAll("input");
        var firstInvalidInput = Array.from(firstStepInputs).find(function (input) {
            return !input.checkValidity();
        });

        if (firstInvalidInput) {
            firstInvalidInput.reportValidity();
            return;
        }
        showStep(2);
    });

    previousButton.addEventListener("click", function () {
        showStep(1);
    });

    var goalIcons = {
        "Build Muscle": "💪",
        "Lose Weight": "🔥",
        "Improve Endurance": "🏃",
        "Body Recomposition": "⚡",
        "Increase Strength": "🏋️",
        "General Wellness": "🧘"
    };

    registerScreen.querySelectorAll("[data-goal-icon]").forEach(function (icon) {
        icon.textContent = goalIcons[icon.dataset.goalIcon] || "•";
    });

    showStep(currentStep === 2 ? 2 : 1);
});
