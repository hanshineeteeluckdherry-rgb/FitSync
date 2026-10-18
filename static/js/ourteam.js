(() => {
    const buttons = document.querySelectorAll('.filter-btn');
    const members = document.querySelectorAll('.team-item');

    buttons.forEach(button => {
        button.addEventListener('click', () => {
            buttons.forEach(item => {
                const selected = item === button;
                item.classList.toggle('active', selected);
                item.setAttribute('aria-pressed', String(selected));
            });
            members.forEach(member => {
                member.hidden = button.dataset.filter !== 'all' && member.dataset.category !== button.dataset.filter;
            });
        });
    });
})();
