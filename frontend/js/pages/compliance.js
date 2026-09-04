Pages = window.Pages || {};

Pages.compliance = {
  async render(container, filters) {
    const data = await API.compliance(filters);
    const s = data.summary || {};
    const checks = [
      ["Works open > 1 year", s.one_year_overdue, data.one_year_overdue, "Check completion timeline and unblock execution."],
      ["Completed works missing UC", s.missing_uc, data.missing_uc, "Obtain Utilization Certificate and supporting closure records."],
      ["Recommendations pending > 90 days", s.pending_sanction, data.pending_sanction, "Review sanction decision and communicate the outcome."],
      ["Expenditure over sanction", s.expenditure_over_sanction, data.expenditure_over_sanction, "Validate approvals before settling further bills."],
      ["Stale progress reporting", s.stale_progress, data.stale_progress, "Request geo-tagged progress update from the agency."],
    ];
    container.innerHTML = `<div class="info-banner"><strong>Automated guideline checks.</strong> This monitor is designed to make documentation and process exceptions visible early; each item should be reviewed by the responsible authority.</div><div class="compliance-grid section-gap">${checks.map((c, i) => `<button class="compliance-tile ${c[1] ? "has-issues" : ""}" data-check="${i}"><span>${c[0]}</span><strong>${Fmt.num(c[1] || 0)}</strong><small>${c[3]}</small></button>`).join("")}</div><div class="section-gap" id="compliance-detail"></div>`;
    const show = index => {
      const [title, count, rows, action] = checks[index];
      document.getElementById("compliance-detail").innerHTML = UI.cardWrap(`${title} (${count || 0})`, complianceTable(rows || [], action));
      document.querySelectorAll(".compliance-work").forEach(row => row.addEventListener("click", () => WorkDetailModal.open(row.dataset.id)));
    };
    document.querySelectorAll(".compliance-tile").forEach(tile => tile.addEventListener("click", () => show(Number(tile.dataset.check))));
    show(0);
  },
};

function complianceTable(rows, action) {
  if (!rows.length) return UI.empty("No exceptions in this check for the selected scope.");
  return `<div class="table-wrap"><table><thead><tr><th>Work</th><th>Location / owner</th><th>Amount</th><th>Suggested action</th></tr></thead><tbody>${rows.map(w => `<tr class="compliance-work" data-id="${w.work_id}"><td class="cell-desc"><div class="primary">${Fmt.escape(w.description)}</div><div class="secondary">${Fmt.escape(w.status || "")}</div></td><td>${Fmt.escape(w.district_name || "")}<div class="secondary">${Fmt.escape(w.state_name || "")} · ${Fmt.escape(w.mp_name || "")}</div></td><td class="cell-amount">${Fmt.lakh(w.excess_lakh || w.spent_lakh || w.sanctioned_amount_lakh)}</td><td>${action}</td></tr>`).join("")}</tbody></table></div>`;
}
