// pages/model.js
window.Pages = window.Pages || {};

Pages.model = {
  async render(el) {
    const report = await API.modelEvaluation();

    el.innerHTML = `
      <div class="card">
        <div class="card-title-row"><h3>Offline Evaluation (diagnostic)</h3></div>
        ${report ? `
          <p style="font-size:12.5px; color:var(--ink-700); line-height:1.6;">
            The public MPLADS dashboard does not publish confirmed fraud cases, so this
            prototype's synthetic dataset deliberately seeds known misuse patterns
            (<code>backend/data_generator.py</code>) purely to measure how well the
            <em>unsupervised</em> detection pipeline recovers them. The pipeline itself
            never sees these labels while scoring — they are used only for this report.
          </p>
          <div class="grid grid-4 section-gap">
            ${UI.kpiCard("Precision", Fmt.pct(report.precision * 100, 1), { text: "Of works flagged High/Critical, share that were truly seeded anomalies" })}
            ${UI.kpiCard("Recall", Fmt.pct(report.recall * 100, 1), { text: "Of all seeded anomalies, share correctly flagged High/Critical" })}
            ${UI.kpiCard("F1 Score", (report.f1).toFixed(2), { text: "Harmonic mean of precision & recall" })}
            ${UI.kpiCard("Works Scored", Fmt.num(report.total_works), { text: `${Fmt.num(report.seeded_anomalies)} seeded anomalies` })}
          </div>
          <div class="table-wrap section-gap"><table>
            <thead><tr><th>True Positives</th><th>False Positives</th><th>False Negatives</th><th>True Negatives</th></tr></thead>
            <tbody><tr>
              <td>${Fmt.num(report.true_positives)}</td>
              <td>${Fmt.num(report.false_positives)}</td>
              <td>${Fmt.num(report.false_negatives)}</td>
              <td>${Fmt.num(report.true_negatives)}</td>
            </tr></tbody>
          </table></div>
        ` : UI.empty("No evaluation report found yet — run <code>python -m ml.train</code> in the backend.")}
      </div>

      <div class="card section-gap">
        <div class="card-title-row"><h3>Why precision/recall aren't near 100%</h3></div>
        <p style="font-size:12.5px; color:var(--ink-700); line-height:1.7;">
          Unsupervised anomaly detection trades off recall against false-alarm volume
          on purpose: flagging every work as high risk would give perfect recall but
          make the alert feed useless. Thresholds here are tuned so that a work
          typically needs either a strong single-rule signal (e.g. a >65% cost
          overrun) or a combination of weaker signals plus an elevated Isolation
          Forest score to reach the High/Critical band. In a real deployment, these
          thresholds would be calibrated against confirmed audit findings and
          adjusted by the Ministry / State Nodal Authorities over time, and reviewers
          can always browse every risk band (not just High/Critical) from the
          <strong>Works Explorer</strong> page.
        </p>
      </div>

      <div class="card section-gap">
        <div class="card-title-row"><h3>Detection layers</h3></div>
        <div class="grid grid-2">
          <div>
            <h4 style="margin:0 0 6px; font-size:13px;">1. Rule Engine (explainable)</h4>
            <ul style="font-size:12.5px; color:var(--ink-700); line-height:1.8; padding-left:18px; margin:0;">
              <li>Cost overrun vs. sanctioned amount</li>
              <li>Ghost / near-non-existent assets (high spend, low physical progress)</li>
              <li>Financial progress far ahead of physical progress</li>
              <li>Front-loaded payments immediately after sanction</li>
              <li>Fiscal year-end payment concentration ("fund parking")</li>
              <li>Stalled works well past expected completion</li>
              <li>Duplicate work descriptions in the same district/category</li>
              <li>Fragmentation of one large work into many small sanctions</li>
              <li>Vendor concentration risk per MP</li>
              <li>Completed works with no Utilization Certificate filed</li>
            </ul>
          </div>
          <div>
            <h4 style="margin:0 0 6px; font-size:13px;">2. Isolation Forest (statistical)</h4>
            <p style="font-size:12.5px; color:var(--ink-700); line-height:1.7;">
              Trained on ten engineered numeric features per work (cost overrun ratio,
              utilization ratio, progress gap, overdue ratio, payment concentration,
              duplicate/fragmentation group sizes, vendor share, installment count).
              It requires no fraud labels — it learns the shape of "typical" MPLADS
              works nationwide and scores how far each work sits from that shape,
              catching combinations the fixed rules don't explicitly encode.
            </p>
          </div>
        </div>
      </div>
    `;
  },
};

window.Pages = Pages;
