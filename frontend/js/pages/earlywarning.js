Pages = window.Pages || {};

Pages.earlywarning = {
  async render(container, filters) {
    const rows = await API.earlyWarning(filters);
    const high = rows.filter(r => (r.early_warning_score || 0) >= 65);
    container.innerHTML = `<div class="info-banner"><strong>Preventive queue, not a fraud list.</strong> These works are likely to delay or overrun based on their current pattern, allowing authorities to intervene before a formal exception occurs.</div>
      <div class="grid grid-3 section-gap">${UI.kpiCard("Active watchlist", Fmt.num(rows.length), { text: "Open works with predictive signals" })}${UI.kpiCard("Urgent intervention", Fmt.num(high.length), { cls: "up", text: "Early-warning score of 65 or above" })}${UI.kpiCard("Suggested owner", AppState.role === "ministry" ? "State Nodal" : AppState.role === "state" ? "District" : "Implementing Agency", { text: "Escalate with a dated recovery plan" })}</div>
      <div class="section-gap">${UI.cardWrap("At-risk works", earlyTable(rows))}</div>`;
    document.querySelectorAll(".early-work").forEach(row => row.addEventListener("click", () => WorkDetailModal.open(row.dataset.id)));
  },
};

function earlyTable(rows) {
  if (!rows.length) return UI.empty("No early-warning signals for the selected scope.");
  return `<div class="table-wrap"><table><thead><tr><th>Priority</th><th>Work</th><th>Delay / overrun likelihood</th><th>Status</th><th>Recommended action</th></tr></thead><tbody>${rows.map(w => `<tr class="early-work" data-id="${w.work_id}"><td><div class="priority-score">${Math.round(w.early_warning_score || 0)}</div></td><td class="cell-desc"><div class="primary">${Fmt.escape(w.description)}</div><div class="secondary">${Fmt.escape(w.work_category)} · ${Fmt.escape(w.district_name)}, ${Fmt.escape(w.state_name)}</div></td><td><strong>${Math.round((w.delay_probability || 0) * 100)}% / ${Math.round((w.overrun_probability || 0) * 100)}%</strong><div class="secondary">Current risk: ${Fmt.escape(w.risk_band)}</div></td><td>${UI.statusBadge(w.status)}</td><td class="cell-desc">${Fmt.escape(w.recommended_action || "Request a catch-up plan and updated progress report.")}</td></tr>`).join("")}</tbody></table></div>`;
}
