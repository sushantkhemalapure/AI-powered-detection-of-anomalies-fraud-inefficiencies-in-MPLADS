// pages/anomalies.js
window.Pages = window.Pages || {};

Pages.anomalies = {
  state: { category: "" },

  async render(el, filters) {
    const [ruleFreq, anomalies] = await Promise.all([
      API.anomalyRuleFrequency(),
      API.anomalies({ limit: 60, category: Pages.anomalies.state.category || undefined }),
    ]);

    el.innerHTML = `
      <div class="grid grid-3">
        <div class="card" style="grid-column: span 1;">
          <div class="card-title-row"><h3>Detection Rules Triggered (frequency)</h3></div>
          <div class="chart-box short"><canvas id="chart-rule-freq"></canvas></div>
        </div>
        <div class="card" style="grid-column: span 2;">
          <div class="card-title-row">
            <h3>How the AI Detection Pipeline Works</h3>
          </div>
          <div style="font-size:12.5px; line-height:1.7; color:var(--ink-700);">
            Every work is scored 0–100 by blending two layers:
            <strong>(1) a rule engine</strong> encoding known MPLADS misuse patterns
            (cost overruns, ghost assets, duplicate/fragmented works, front-loaded or
            year-end payments, vendor concentration, stalled projects, missing
            utilization certificates), and
            <strong>(2) an unsupervised Isolation Forest</strong> trained on every
            work's financial and progress features, which flags statistical outliers
            even when no fixed rule fires. Rules make the score explainable;
            the ML layer catches novel patterns rules don't anticipate.
          </div>
        </div>
      </div>

      <div class="card section-gap">
        <div class="card-title-row">
          <h3>Top Anomalous Works</h3>
          <select id="a-category">
            <option value="">All Rule Types</option>
            ${Object.entries(RULE_LABELS).map(([code, label]) => `<option value="${code}" ${Pages.anomalies.state.category===code?"selected":""}>${label}</option>`).join("")}
          </select>
        </div>
        <div id="a-list">${renderList(anomalies)}</div>
      </div>
    `;

    Charts.bar("chart-rule-freq", ruleFreq.map(r => RULE_LABELS[r.rule] || r.rule), ruleFreq.map(r => r.count), { horizontal: true, color: "#dc2626" });

    document.getElementById("a-category").addEventListener("change", async (e) => {
      Pages.anomalies.state.category = e.target.value;
      const listBox = document.getElementById("a-list");
      listBox.innerHTML = UI.loading();
      const data = await API.anomalies({ limit: 60, category: e.target.value || undefined });
      listBox.innerHTML = renderList(data);
      bindRowClicks();
    });

    bindRowClicks();

    function bindRowClicks() {
      document.querySelectorAll("#a-list tbody tr").forEach(tr => {
        tr.addEventListener("click", () => WorkDetailModal.open(tr.dataset.id));
      });
    }

    function renderList(items) {
      if (!items.length) return UI.empty("No anomalies match this filter.");
      return `
        <div class="table-wrap"><table>
          <thead><tr><th>Work</th><th>MP / Location</th><th>Amount</th><th>Risk</th><th>Triggered Rules</th></tr></thead>
          <tbody>
            ${items.map(a => `
              <tr data-id="${a.work_id}">
                <td class="cell-desc"><div class="primary">${Fmt.escape(truncate(a.description, 60))}</div><div class="secondary">ID #${a.work_id} · ${Fmt.escape(a.work_category)}</div></td>
                <td>${Fmt.escape(a.mp_name)}<div class="secondary">${Fmt.escape(a.district_name)}, ${Fmt.escape(a.state_name)}</div></td>
                <td class="cell-amount">${Fmt.lakh(a.sanctioned_amount_lakh)}</td>
                <td>${UI.riskBadge(a.risk_band, a.risk_score)}</td>
                <td style="max-width:280px;">${UI.ruleChips(a.triggered_rules)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table></div>
      `;
    }
  },
};

window.Pages = Pages;
