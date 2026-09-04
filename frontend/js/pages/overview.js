// pages/overview.js
window.Pages = window.Pages || {};

Pages.overview = {
  async render(container, filters) {
    const [summary, rankings, anomalies, report] = await Promise.all([
      API.dashboardSummary(filters),
      API.stateRanking(filters),
      API.anomalies({ ...filters, limit: 6 }),
      API.modelEvaluation(),
    ]);

    const totals = summary.totals || {};
    const riskMap = Object.fromEntries((summary.risk_breakdown || []).map(row => [row.risk_band, row.count]));
    const highCritical = (riskMap.High || 0) + (riskMap.Critical || 0);
    const records = totals.total_works || 0;
    const allocated = totals.total_sanctioned_lakh || 0;
    const priority = anomalies.filter(row => ["High", "Critical"].includes(row.risk_band)).slice(0, 5);
    const topStates = rankings.slice(0, 8);

    container.innerHTML = `
      <section class="overview-hero">
        <div>
          <div class="eyebrow">MPLADS ALLOCATION MONITOR</div>
          <h2>Allocation risk review, made clear.</h2>
          <p>Review unusual MP allocation amounts, focus on the highest-priority records, and compare risk across states. All findings are review prompts—not findings of fraud.</p>
        </div>
        <div class="overview-hero-stats">
          <div><strong>${Fmt.num(highCritical)}</strong><span>High / Critical reviews</span></div>
          <div><strong>${Fmt.num(summary.open_alerts || 0)}</strong><span>Open alerts</span></div>
        </div>
      </section>

      <div class="grid grid-4 section-gap">
        ${UI.kpiCard("Allocation records", Fmt.num(records), { text: "Imported MP allocation records" })}
        ${UI.kpiCard("Total allocated", Fmt.lakh(allocated), { text: "Across the current selected scope" })}
        ${UI.kpiCard("Priority reviews", Fmt.num(highCritical), { text: `${Fmt.num(riskMap.Critical || 0)} Critical and ${Fmt.num(riskMap.High || 0)} High`, cls: highCritical ? "up" : "ok" })}
        ${UI.kpiCard("States covered", Fmt.num(rankings.length), { text: "State and constituency coverage" })}
      </div>

      <div class="overview-data-note section-gap">
        <div class="overview-data-icon">i</div>
        <div>
          <strong>Current data coverage: allocation records only</strong>
          <span>The imported CSV includes State, MP, Constituency and Allocated Amount. It does not include payments, utilization, vendors, sectors, work progress or dates; those checks remain unavailable until their real source data is added.</span>
        </div>
        <a href="#model" class="btn btn-sm">Data & model details</a>
      </div>

      <div class="grid grid-2 section-gap">
        ${UI.cardWrap("Risk distribution", `
          <div class="overview-risk-layout">
            <div class="chart-box"><canvas id="chart-risk-donut"></canvas></div>
            <div class="risk-breakdown-list">
              ${riskRows(riskMap)}
            </div>
          </div>`, `<a href="#anomalies" class="btn btn-sm btn-ghost">View all reviews</a>`)}

        ${UI.cardWrap("Highest-priority allocation reviews", priority.length ? `
          <div class="priority-list">
            ${priority.map(row => `
              <button class="priority-row" data-work-id="${row.work_id}">
                <span class="priority-marker ${row.risk_band}"></span>
                <span class="priority-main">
                  <strong>${Fmt.escape(row.mp_name)}</strong>
                  <small>${Fmt.escape(row.constituency || row.district_name)}, ${Fmt.escape(row.state_name)}</small>
                </span>
                <span class="priority-side">${UI.riskBadge(row.risk_band, row.risk_score)}<small>${Fmt.lakh(row.sanctioned_amount_lakh)}</small></span>
              </button>`).join("")}
          </div>` : UI.empty("No High or Critical records in the selected scope."), `<a href="#alerts" class="btn btn-sm btn-ghost">Open alerts</a>`)}
      </div>

      <div class="grid grid-2 section-gap">
        ${UI.cardWrap("States with the highest average risk", `
          <div class="chart-box" style="height:290px;"><canvas id="chart-state-risk-overview"></canvas></div>`,
          `<a href="#rankings" class="btn btn-sm btn-ghost">All state rankings</a>`)}

        ${UI.cardWrap("What the AI is checking", `
          <div class="check-list">
            <div><b>1</b><span><strong>Allocation outliers</strong><small>Flags allocation amounts that differ materially from the imported national pattern.</small></span></div>
            <div><b>2</b><span><strong>Risk prioritisation</strong><small>Ranks records into Low, Medium, High and Critical review bands.</small></span></div>
            <div><b>3</b><span><strong>Explainable alerts</strong><small>Creates review alerts with the amount, MP and location needed for follow-up.</small></span></div>
          </div>
          <div class="overview-model-note">${Fmt.escape(report?.data_note || "Train the model to generate the latest risk summary.")}</div>`)}
      </div>

      <div class="card section-gap">
        <div class="card-title-row">
          <div><h3>Review queue</h3><span class="text-muted" style="font-size:12px;">Highest-scoring allocation records in the selected scope</span></div>
          <a href="#anomalies" class="btn btn-sm btn-primary">Review all anomalies</a>
        </div>
        ${renderReviewTable(anomalies)}
      </div>
    `;

    Charts.riskDonut("chart-risk-donut", summary.risk_breakdown || []);
    Charts.bar(
      "chart-state-risk-overview",
      topStates.map(row => row.state_name),
      topStates.map(row => row.avg_risk_score || 0),
      { horizontal: true, color: topStates.map(row => Charts.RISK_COLORS[bandForRisk(row.avg_risk_score)]) },
    );

    container.querySelectorAll("[data-work-id]").forEach(element => {
      element.addEventListener("click", () => WorkDetailModal.open(element.dataset.workId));
    });
  },
};

function riskRows(riskMap) {
  return ["Critical", "High", "Medium", "Low"].map(band => `
    <div class="risk-breakdown-row">
      <span><i style="background:${Charts.RISK_COLORS[band]}"></i>${band}</span>
      <strong>${Fmt.num(riskMap[band] || 0)}</strong>
    </div>`).join("");
}

function renderReviewTable(rows) {
  if (!rows.length) return UI.empty("No scored records are available in this scope.");
  return `
    <div class="table-wrap"><table>
      <thead><tr><th>MP / Allocation record</th><th>State & constituency</th><th>Allocated amount</th><th>Risk</th><th>Review reason</th></tr></thead>
      <tbody>
        ${rows.map(row => `
          <tr data-work-id="${row.work_id}">
            <td class="cell-desc"><div class="primary">${Fmt.escape(row.mp_name)}</div><div class="secondary">${Fmt.escape(row.description)}</div></td>
            <td>${Fmt.escape(row.state_name)}<div class="secondary">${Fmt.escape(row.constituency || row.district_name)}</div></td>
            <td class="cell-amount">${Fmt.lakh(row.sanctioned_amount_lakh)}</td>
            <td>${UI.riskBadge(row.risk_band, row.risk_score)}${UI.riskScoreBar(row.risk_score, row.risk_band)}</td>
            <td class="text-muted" style="max-width:310px;">${Fmt.escape(reviewReason(row))}</td>
          </tr>`).join("")}
      </tbody>
    </table></div>`;
}

function reviewReason(row) {
  if (row.triggered_rules?.length) return row.explanation || "Rule-based review signal detected.";
  return "Allocation amount is statistically unusual compared with the imported records; verify the source value and approval.";
}

function bandForRisk(score) {
  if (score >= 68) return "Critical";
  if (score >= 45) return "High";
  if (score >= 25) return "Medium";
  return "Low";
}
