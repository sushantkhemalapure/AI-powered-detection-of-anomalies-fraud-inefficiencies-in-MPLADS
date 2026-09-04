// pages/rankings.js
window.Pages = window.Pages || {};

Pages.rankings = {
  async render(el, filters) {
    const rows = await API.stateRanking(filters);
    el.innerHTML = `
      <div class="grid grid-2">
        <div class="card" style="grid-column: span 2;">
          <div class="card-title-row"><h3>Average allocation-pattern review score by state</h3></div>
          <div class="chart-box" style="height:340px;"><canvas id="chart-state-risk"></canvas></div>
        </div>
      </div>
      <div class="card section-gap">
        <div class="card-title-row"><h3>State allocation summary (ranked by average review score)</h3></div>
        <div class="table-wrap"><table>
          <thead><tr><th>#</th><th>State</th><th>Allocation records</th><th>Total allocated</th><th>Avg. review score</th><th>High/Critical reviews</th></tr></thead>
          <tbody>
            ${rows.map((r, i) => `
              <tr>
                <td>${i + 1}</td>
                <td><strong>${Fmt.escape(r.state_name)}</strong></td>
                <td>${Fmt.num(r.total_works)}</td>
                <td class="cell-amount">${Fmt.lakh(r.total_sanctioned_lakh)}</td>
                <td>${UI.riskScoreBar(r.avg_risk_score || 0, bandFor(r.avg_risk_score))} <span style="font-size:12px;">${r.avg_risk_score ?? "—"}</span></td>
                <td>${Fmt.num(r.high_risk_works)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table></div>
      </div>
    `;

    Charts.bar("chart-state-risk", rows.map(r => r.state_name), rows.map(r => r.avg_risk_score || 0),
      { horizontal: true, color: rows.map(r => Charts.RISK_COLORS[bandFor(r.avg_risk_score)]) });
    // Chart.js bar with per-bar colors needs array background; rebuild manually for color array support:
    Charts.destroy("chart-state-risk");
    const ctx = document.getElementById("chart-state-risk");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: rows.map(r => r.state_name),
        datasets: [{ data: rows.map(r => r.avg_risk_score || 0), backgroundColor: rows.map(r => Charts.RISK_COLORS[bandFor(r.avg_risk_score)]), borderRadius: 5 }],
      },
      options: {
        indexAxis: "y",
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { max: 100, ticks: { font: { size: 10.5 } } }, y: { ticks: { font: { size: 10 } } } },
      },
    });
  },
};

function bandFor(score) {
  if (score === null || score === undefined) return "Unscored";
  if (score < 25) return "Low";
  if (score < 45) return "Medium";
  if (score < 68) return "High";
  return "Critical";
}

window.Pages = Pages;
