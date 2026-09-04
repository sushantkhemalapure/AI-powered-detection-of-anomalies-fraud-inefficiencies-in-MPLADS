// pages/overview.js
Pages = window.Pages || {};

Pages.overview = {
  async render(container, filters) {
    const [summary, trend] = await Promise.all([
      API.dashboardSummary(filters),
      API.dashboardTrend(filters),
    ]);

    const t = summary.totals || {};
    const totalWorks = t.total_works || 0;
    const sanctioned = t.total_sanctioned_lakh || 0;
    const expenditure = t.total_expenditure_lakh || 0;
    const utilPct = sanctioned ? (expenditure / sanctioned * 100) : 0;

    const riskMap = Object.fromEntries((summary.risk_breakdown || []).map(r => [r.risk_band, r.count]));
    const highCritical = (riskMap["High"] || 0) + (riskMap["Critical"] || 0);

    container.innerHTML = `
      <div class="grid grid-4">
        ${UI.kpiCard("Total Works", Fmt.num(totalWorks), { text: `${Fmt.num(t.completed_works||0)} completed · ${Fmt.num(t.inprogress_works||0)} in progress · ${Fmt.num(t.delayed_works||0)} delayed` })}
        ${UI.kpiCard("Sanctioned Amount", Fmt.lakh(sanctioned), { text: "Across all recommended works" })}
        ${UI.kpiCard("Funds Utilized", Fmt.lakh(expenditure), { text: `${utilPct.toFixed(1)}% of sanctioned amount drawn`, cls: utilPct > 95 ? "up" : "" })}
        ${UI.kpiCard("Open Alerts", Fmt.num(summary.open_alerts || 0), { text: `${Fmt.num(highCritical)} works flagged High / Critical risk`, cls: highCritical > 0 ? "up" : "ok" })}
      </div>

      <div class="grid grid-2 section-gap">
        ${UI.cardWrap("AI Risk Distribution", `<div class="chart-box"><canvas id="chart-risk-donut"></canvas></div>`,
          `<a href="#anomalies" class="btn btn-sm btn-ghost">View anomalies →</a>`)}
        ${UI.cardWrap("Top Work Categories by Sanctioned Value", `<div class="chart-box"><canvas id="chart-categories"></canvas></div>`)}
      </div>

      <div class="section-gap">
        ${UI.cardWrap("Fund Flow Trend — Sanctioned vs. Expenditure (monthly, ₹ lakh)",
          `<div class="chart-box"><canvas id="chart-trend"></canvas></div>`)}
      </div>

      <div id="ministry-extra"></div>
    `;

    Charts.riskDonut("chart-risk-donut", summary.risk_breakdown || []);

    const cats = summary.top_categories || [];
    Charts.bar("chart-categories",
      cats.map(c => c.work_category.length > 18 ? c.work_category.slice(0, 16) + "…" : c.work_category),
      cats.map(c => Math.round(c.total_lakh)),
      { horizontal: true, color: "#2563eb" });

    Charts.line("chart-trend", trend.map(r => r.month), [
      { label: "Sanctioned (₹L)", data: trend.map(r => Math.round(r.sanctioned_lakh || 0)), color: "#2563eb" },
      { label: "Expenditure (₹L)", data: trend.map(r => Math.round(r.expenditure_lakh || 0)), color: "#ea580c", fill: false },
    ]);

    if (AppState.role === "ministry") {
      await renderMinistryExtra(document.getElementById("ministry-extra"));
    }
  },
};

async function renderMinistryExtra(el) {
  const ranking = await API.stateRanking();
  const top5 = ranking.slice(0, 5);
  el.innerHTML = `
    <div class="section-gap">
      ${UI.cardWrap("States Needing Attention (highest average risk score)",
        `<div class="table-wrap"><table>
          <thead><tr><th>State</th><th>Total Works</th><th>Avg. Risk Score</th><th>High/Critical Works</th><th>Sanctioned</th></tr></thead>
          <tbody>
            ${top5.map(r => `<tr>
              <td><strong>${Fmt.escape(r.state_name)}</strong></td>
              <td>${Fmt.num(r.total_works)}</td>
              <td>${UI.riskScoreBar(r.avg_risk_score || 0, r.avg_risk_score > 55 ? "Critical" : r.avg_risk_score > 40 ? "High" : "Low")} <span class="mono">${(r.avg_risk_score||0).toFixed(1)}</span></td>
              <td>${Fmt.num(r.high_risk_works)}</td>
              <td>${Fmt.lakh(r.total_sanctioned_lakh)}</td>
            </tr>`).join("")}
          </tbody>
        </table></div>`,
        `<a href="#rankings" class="btn btn-sm btn-ghost">Full ranking →</a>`)}
    </div>
  `;
}
