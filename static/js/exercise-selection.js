(() => {
    const checkboxes = Array.from(document.querySelectorAll('.exercise-selection-page input[name="exercise_ids"]:not(:disabled)'));
    const button = document.getElementById('addSelectedExercises');
    const count = document.getElementById('exerciseSelectionCount');
    if (!button || !count) return;

    function updateSelection() {
        const selected = checkboxes.filter(box => box.checked).length;
        count.textContent = selected + ' exercise' + (selected === 1 ? '' : 's') + ' selected';
        button.disabled = selected === 0;
    }

    checkboxes.forEach(box => box.addEventListener('change', updateSelection));
    updateSelection();
})();
