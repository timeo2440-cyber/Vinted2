const statsView = (() => {
  let chartData = [];

  function init() {
    loadStats();
  }

  async function loadStats() {
    try {
      const [summary, timeline] = await Promise.all([api.getStats(), api.getTimeline()]);
      renderSummary(summary);
      chartData = timeline.timeline || [];
      renderChart(chartData);
    } catch (e) {
      toast.show('Erreur stats : ' + e.message, 'error');
    }
  }

  function renderSummary(s) {
    setText('s-total-seen', s.total_seen ?? 0);
    setText('s-matched',    s.successful_purchases ?? 0);
    setText('s-bought',     s.successful_purchases ?? 0);
    setText('s-spend',      (s.spend_24h ?? 0).toFixed(2) + '€');
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function renderChart(data) {
    const canvas = document.getElementById('timeline-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.offsetWidth || 600;
    const H = 200;
    canvas.width  = W;
    canvas.height = H;

    const counts = data.map(d => d.count);
    const labels = data.map(d => d.hour);
    const max    = Math.max(...counts, 1);
    const PAD    = { top: 20, right: 16, bottom: 36, left: 40 };
    const plotW  = W - PAD.left - PAD.right;
    const plotH  = H - PAD.top - PAD.bottom;
    const barW   = Math.max(4, plotW / data.length - 3);

    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = 'rgba(46,51,72,0.8)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = PAD.top + plotH - (i / 4) * plotH;
      ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + plotW, y); ctx.stroke();
      ctx.fillStyle = 'rgba(139,144,168,0.7)';
      ctx.font = '10px system-ui';
      ctx.textAlign = 'right';
      ctx.fillText(Math.round(max * i / 4), PAD.left - 4, y + 3);
    }

    // Bars
    data.forEach((d, i) => {
      const x   = PAD.left + i * (plotW / data.length) + (plotW / data.length - barW) / 2;
      const bH  = (d.count / max) * plotH;
      const y   = PAD.top + plotH - bH;

      const grad = ctx.createLinearGradient(0, y, 0, y + bH);
      grad.addColorStop(0, 'rgba(108,99,255,0.9)');
      grad.addColorStop(1, 'rgba(108,99,255,0.2)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barW, bH, [3, 3, 0, 0]);
      ctx.fill();
    });

    // X labels — show every 4 hours
    ctx.fillStyle = 'rgba(139,144,168,0.7)';
    ctx.font = '10px system-ui';
    ctx.textAlign = 'center';
    data.forEach((d, i) => {
      if (i % 4 === 0) {
        const x = PAD.left + i * (plotW / data.length) + (plotW / data.length) / 2;
        ctx.fillText(d.hour, x, H - 8);
      }
    });
  }

  return { init, reload: loadStats };
})();
