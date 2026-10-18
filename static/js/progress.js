(() => {
    const charts = [
        {id: "weightChart", data: "weightChartData", type: "line"},
        {id: "calorieChart", data: "calorieChartData", type: "bars"},
    ];

    function drawChart(chart) {
        const canvas = document.getElementById(chart.id);
        if (!canvas) return;
        const data = JSON.parse(document.getElementById(chart.data).textContent);
        const width = canvas.parentElement.clientWidth;
        const height = 210;
        const scale = window.devicePixelRatio || 1;
        canvas.width = width * scale;
        canvas.height = height * scale;
        const ctx = canvas.getContext("2d");
        ctx.scale(scale, scale);

        const styles = getComputedStyle(document.documentElement);
        const muted = styles.getPropertyValue("--muted-color").trim();
        const border = styles.getPropertyValue("--border-color").trim();
        const left = 48;
        const top = 10;
        const bottom = height - 30;
        const plotWidth = Math.max(1, width - left - 18);
        const plotHeight = bottom - top;
        const values = data.map(item => item.value);
        let minimum = 0;
        let maximum = Math.max(100, ...values);
        if (chart.type === "line" && values.length) {
            minimum = Math.min(...values) - 1;
            maximum = Math.max(...values) + 1;
        }

        ctx.font = "11px Inter, sans-serif";
        for (let tick = 0; tick <= 4; tick += 1) {
            const y = top + plotHeight * tick / 4;
            const value = maximum - (maximum - minimum) * tick / 4;
            ctx.strokeStyle = border;
            ctx.setLineDash([3, 4]);
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(width - 18, y);
            ctx.stroke();
            ctx.fillStyle = muted;
            ctx.textAlign = "right";
            ctx.fillText(chart.type === "line" ? value.toFixed(1) : Math.round(value), left - 8, y + 4);
        }
        ctx.setLineDash([]);
        if (!data.length) return;

        const points = data.map((item, index) => ({
            x: chart.type === "bars"
                ? left + plotWidth * (index + 0.5) / data.length
                : left + plotWidth * (data.length === 1 ? 0.5 : index / (data.length - 1)),
            y: bottom - (item.value - minimum) / (maximum - minimum) * plotHeight,
            label: item.label,
            value: item.value,
        }));

        if (chart.type === "line") {
            ctx.strokeStyle = "#00d4aa";
            ctx.lineWidth = 2;
            ctx.beginPath();
            points.forEach((point, index) => {
                if (index === 0) ctx.moveTo(point.x, point.y);
                else ctx.lineTo(point.x, point.y);
            });
            ctx.stroke();
            points.forEach(point => {
                ctx.fillStyle = "#00d4aa";
                ctx.beginPath();
                ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
                ctx.fill();
            });
        } else {
            const barWidth = Math.min(32, plotWidth / data.length * 0.55);
            ctx.fillStyle = "#f59e0b";
            points.forEach(point => ctx.fillRect(point.x - barWidth / 2, point.y, barWidth, bottom - point.y));
        }

        const labelStep = Math.max(1, Math.ceil(points.length / 6));
        ctx.textAlign = "center";
        ctx.fillStyle = muted;
        points.forEach((point, index) => {
            if (index % labelStep === 0 || index === points.length - 1) {
                ctx.fillText(point.label, point.x, height - 10);
            }
        });
    }

    function redraw() {
        charts.forEach(drawChart);
    }
    new ResizeObserver(redraw).observe(document.querySelector(".fitness-progress"));
    new MutationObserver(redraw).observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
    redraw();
})();
