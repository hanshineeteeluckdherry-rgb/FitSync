document.querySelectorAll(".workout-exercise-card").forEach(card => {
    const boxes = card.querySelectorAll('.btn-check');
    const count = card.querySelector('[data-set-count]');

    function updateSets() {
        let completed = 0;
        boxes.forEach(box => {
            box.closest('.workout-set-pill').classList.toggle('is-completed', box.checked);
            if (box.checked) completed += 1;
        });
        count.textContent = completed;
    }

    boxes.forEach(box => box.addEventListener('change', updateSets));
    card.querySelectorAll('input').forEach(input => {
        input.addEventListener('invalid', () => { card.open = true; });
    });
    updateSets();
});
