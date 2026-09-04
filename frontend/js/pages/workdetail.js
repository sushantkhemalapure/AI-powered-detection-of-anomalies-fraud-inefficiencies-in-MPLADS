// Allocation record drill-down. The source has no work execution data, so this
// view presents only the source fields and the allocation-pattern review result.
const WorkDetailModal = {
  async open(workId) {
    const root = document.getElementById("modal-root");
    root.innerHTML = `<div class="modal-backdrop" id="modal-backdrop"><div class="modal"><div class="modal-body">${UI.loading()}</div></div></div>`;
    document.getElementById("modal-backdrop").addEventListener("click", e => { if (e.target.id === "modal-backdrop") WorkDetailModal.close(); });
    try { WorkDetailModal.render(await API.workDetail(workId)); }
    catch (_) { root.querySelector(".modal-body").innerHTML = UI.empty("Couldn't load this allocation record."); }
  },
  close() { document.getElementById("modal-root").innerHTML = ""; },
  render(data) {
    const w = data.work, r = data.risk, alerts = data.alerts || [];
    const reason = r?.triggered_rules?.length ? r.explanation : "The model found this allocation amount unusual compared with the other imported allocation records. Verify the source value and supporting approval.";
    document.querySelector("#modal-root .modal").innerHTML = `<div class="modal-header"><div class="titles"><h2>${Fmt.escape(w.mp_name)}</h2><div class="meta-line">Allocation record #${w.work_id} | ${Fmt.escape(w.constituency || w.district_name)}, ${Fmt.escape(w.state_name)}</div></div>${r ? UI.riskBadge(r.risk_band, r.risk_score) : UI.statusBadge("Unscored")}<button class="modal-close" id="modal-close-btn">&times;</button></div><div class="modal-body"><div class="kv-grid" style="margin-bottom:18px;"><div><div class="kv-label">Member of Parliament</div><div class="kv-value">${Fmt.escape(w.mp_name)}</div></div><div><div class="kv-label">Constituency</div><div class="kv-value">${Fmt.escape(w.district_name)}</div></div><div><div class="kv-label">State</div><div class="kv-value">${Fmt.escape(w.state_name)}</div></div><div><div class="kv-label">Allocated amount</div><div class="kv-value">${Fmt.lakh(w.sanctioned_amount_lakh)}</div></div><div><div class="kv-label">Source file</div><div class="kv-value">${Fmt.escape(w.source_file || "Bundled allocation CSV")}</div></div><div><div class="kv-label">Data type</div><div class="kv-value">Allocation record</div></div></div><div class="explanation-box ${r?.risk_band === "Low" ? "ok" : ""}"><strong>Allocation-pattern review${r ? ` (${Fmt.escape(r.risk_band)}, score ${Math.round(r.risk_score)}/100)` : ""}</strong><br>${Fmt.escape(reason)}${r?.triggered_rules?.length ? `<div style="margin-top:8px;">${UI.ruleChips(r.triggered_rules)}</div>` : ""}</div><div class="section-gap"><h3 style="font-size:14px;">Review alerts (${alerts.length})</h3>${alerts.length ? alerts.map(a => `<div class="alert-card ${a.severity}"><div class="stripe"></div><div class="body"><div class="msg">${Fmt.escape(a.message)}</div><div class="meta">${UI.sevChip(a.severity)} | ${Fmt.escape(a.status)}</div></div></div>`).join("") : UI.empty("No alert was generated for this allocation record.")}</div><div class="overview-data-note"><div class="overview-data-icon">i</div><div><strong>Data boundary</strong><span>No dates, payment, vendor, physical-progress, project-status, or geolocation fields are supplied for this record.</span></div></div></div>`;
    document.getElementById("modal-close-btn").addEventListener("click", WorkDetailModal.close);
  },
};
