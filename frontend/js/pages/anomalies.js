window.Pages = window.Pages || {};
Pages.anomalies = {
  async render(el, filters) {
    const records = await API.anomalies({ ...filters, limit: 80 });
    el.innerHTML = `<div class="grid grid-2"><div class="card"><div class="card-title-row"><h3>What this review means</h3></div><p style="font-size:12.5px;line-height:1.7;color:var(--ink-700);">The source contains allocation limits only. An unsupervised model compares each amount with the imported national pattern and prioritises unusual records for source verification. It cannot identify delivery failures, payments, vendors, progress, or fraud.</p></div><div class="card"><div class="card-title-row"><h3>Review workflow</h3></div><div class="check-list"><div><b>1</b><span><strong>Verify the source row</strong><small>Check amount, MP, constituency and state against the sanctioned record.</small></span></div><div><b>2</b><span><strong>Check the supporting approval</strong><small>Confirm that the amount and allocation period are documented.</small></span></div><div><b>3</b><span><strong>Record the outcome</strong><small>Use Review Alerts to mark each prompt as under review, resolved, or dismissed.</small></span></div></div></div></div><div class="card section-gap"><div class="card-title-row"><h3>Allocation records for review</h3><span class="text-muted" style="font-size:12px;">Ordered by allocation-pattern review score</span></div>${renderOutlierTable(records)}</div>`;
    el.querySelectorAll("tr[data-id]").forEach(row => row.addEventListener("click", () => WorkDetailModal.open(row.dataset.id)));
  },
};
function renderOutlierTable(rows) {
  if (!rows.length) return UI.empty("No scored allocation records are available in this scope.");
  return `<div class="table-wrap"><table><thead><tr><th>MP</th><th>State / constituency</th><th>Allocated amount</th><th>Review score</th><th>Review basis</th></tr></thead><tbody>${rows.map(r => `<tr data-id="${r.work_id}"><td><strong>${Fmt.escape(r.mp_name)}</strong></td><td>${Fmt.escape(r.state_name)}<div class="secondary">${Fmt.escape(r.district_name)}</div></td><td class="cell-amount">${Fmt.lakh(r.sanctioned_amount_lakh)}</td><td>${UI.riskBadge(r.risk_band, r.risk_score)}${UI.riskScoreBar(r.risk_score, r.risk_band)}</td><td class="text-muted">${r.triggered_rules?.length ? UI.ruleChips(r.triggered_rules) : "Statistical allocation outlier"}</td></tr>`).join("")}</tbody></table></div>`;
}
window.Pages = Pages;
