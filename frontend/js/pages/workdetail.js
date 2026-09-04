// pages/workdetail.js - modal drill-down for a single work.
const WorkDetailModal = {
  activeTab: "financials",

  async open(workId) {
    const root = document.getElementById("modal-root");
    root.innerHTML = `<div class="modal-backdrop" id="modal-backdrop"><div class="modal">
      <div class="modal-body">${UI.loading()}</div>
    </div></div>`;
    document.getElementById("modal-backdrop").addEventListener("click", (e) => {
      if (e.target.id === "modal-backdrop") WorkDetailModal.close();
    });

    let data;
    try {
      data = await API.workDetail(workId);
    } catch (err) {
      root.querySelector(".modal-body").innerHTML = UI.empty("Couldn't load this work.");
      return;
    }
    WorkDetailModal.activeTab = "financials";
    WorkDetailModal.render(data);
  },

  close() {
    document.getElementById("modal-root").innerHTML = "";
  },

  render(data) {
    const w = data.work;
    const risk = data.risk;
    const root = document.getElementById("modal-root");

    const modal = root.querySelector(".modal");
    modal.innerHTML = `
      <div class="modal-header">
        <div class="titles">
          <h2>${Fmt.escape(w.description)}</h2>
          <div class="meta-line">Work #${w.work_id} · ${Fmt.escape(w.work_category)} · ${Fmt.escape(w.district_name)}, ${Fmt.escape(w.state_name)}</div>
        </div>
        ${risk ? UI.riskBadge(risk.risk_band, risk.risk_score) : UI.statusBadge("Unscored")}
        <button class="modal-close" id="modal-close-btn">&times;</button>
      </div>
      <div class="modal-body">

        <div class="kv-grid" style="margin-bottom:18px;">
          <div><div class="kv-label">Member of Parliament</div><div class="kv-value">${Fmt.escape(w.mp_name)} (${Fmt.escape(w.house)})</div></div>
          <div><div class="kv-label">Implementing Agency</div><div class="kv-value">${Fmt.escape(w.agency_name)}</div></div>
          <div><div class="kv-label">Status</div><div class="kv-value">${UI.statusBadge(w.status)}</div></div>
          <div><div class="kv-label">Sanctioned Amount</div><div class="kv-value">${Fmt.lakh(w.sanctioned_amount_lakh)}</div></div>
          <div><div class="kv-label">Sanction Date</div><div class="kv-value">${Fmt.date(w.sanction_date)}</div></div>
          <div><div class="kv-label">Expected Completion</div><div class="kv-value">${Fmt.date(w.expected_completion_date)}</div></div>
        </div>

        ${risk ? `
          <div class="explanation-box ${risk.risk_band === 'Low' ? 'ok' : ''}" style="margin-bottom:18px;">
            <strong>AI Risk Assessment (${risk.risk_band}, score ${Math.round(risk.risk_score)}/100):</strong><br>
            ${Fmt.escape(risk.explanation)}
            <div style="margin-top:8px;">${UI.ruleChips(risk.triggered_rules)}</div>
          </div>
        ` : ""}

        <div class="modal-tabs">
          <div class="modal-tab" data-tab="financials">Financials (${data.expenditures.length})</div>
          <div class="modal-tab" data-tab="progress">Progress Reports (${data.progress.length})</div>
          <div class="modal-tab" data-tab="alerts">Alerts (${data.alerts.length})</div>
        </div>
        <div id="modal-tab-content"></div>
      </div>
    `;

    modal.querySelector("#modal-close-btn").addEventListener("click", WorkDetailModal.close);
    modal.querySelectorAll(".modal-tab").forEach(t => {
      t.addEventListener("click", () => { WorkDetailModal.activeTab = t.dataset.tab; WorkDetailModal.renderTab(data); });
    });
    WorkDetailModal.renderTab(data);
  },

  renderTab(data) {
    const modal = document.querySelector("#modal-root .modal");
    modal.querySelectorAll(".modal-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === WorkDetailModal.activeTab));
    const box = modal.querySelector("#modal-tab-content");

    if (WorkDetailModal.activeTab === "financials") {
      const totalSpent = data.expenditures.reduce((s, e) => s + e.amount_lakh, 0);
      box.innerHTML = `
        <div style="margin-bottom:10px; font-size:12.5px;" class="text-muted">
          Total disbursed: <strong style="color:var(--ink-900)">${Fmt.lakh(totalSpent)}</strong> across ${data.expenditures.length} payment(s).
          Utilization Certificate: ${data.utilization_certificate ? `<span style="color:var(--risk-low);font-weight:700;">Filed ${Fmt.date(data.utilization_certificate.submitted_date)}</span>` : `<span style="color:var(--risk-critical);font-weight:700;">Not filed</span>`}
        </div>
        <div class="table-wrap"><table>
          <thead><tr><th>#</th><th>Date</th><th>Vendor</th><th>Amount</th><th>Mode</th><th>Voucher</th></tr></thead>
          <tbody>${data.expenditures.map(e => `
            <tr><td>${e.installment_no}</td><td>${Fmt.date(e.payment_date)}</td><td>${Fmt.escape(e.vendor_name || "—")}</td>
              <td class="cell-amount">${Fmt.lakh(e.amount_lakh)}</td><td>${Fmt.escape(e.payment_mode)}</td><td class="mono">${Fmt.escape(e.voucher_no)}</td></tr>
          `).join("") || `<tr><td colspan="6" class="text-muted">No expenditure recorded yet.</td></tr>`}</tbody>
        </table></div>
      `;
    } else if (WorkDetailModal.activeTab === "progress") {
      box.innerHTML = data.progress.length ? data.progress.map(p => `
        <div style="margin-bottom:14px;">
          <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
            <span class="text-muted">${Fmt.date(p.report_date)} — ${Fmt.escape(p.remarks || "")}</span>
          </div>
          <div style="display:flex; gap:16px; align-items:center;">
            <div style="flex:1;">
              <div style="font-size:11px; color:var(--ink-500); margin-bottom:2px;">Physical: ${Fmt.pct(p.physical_progress_pct)}</div>
              <div class="progress-track"><div class="progress-fill" style="width:${p.physical_progress_pct}%; background:#16a34a;"></div></div>
            </div>
            <div style="flex:1;">
              <div style="font-size:11px; color:var(--ink-500); margin-bottom:2px;">Financial: ${Fmt.pct(p.financial_progress_pct)}</div>
              <div class="progress-track"><div class="progress-fill" style="width:${p.financial_progress_pct}%; background:#2563eb;"></div></div>
            </div>
          </div>
        </div>
      `).join("") : UI.empty("No progress reports filed yet.");
    } else if (WorkDetailModal.activeTab === "alerts") {
      box.innerHTML = data.alerts.length ? data.alerts.map(a => `
        <div class="alert-card ${a.severity}"><div class="stripe"></div>
          <div class="body">
            <div class="msg">${Fmt.escape(a.message)}</div>
            <div class="meta">${UI.sevChip(a.severity)} &nbsp; ${RULE_LABELS[a.category] || a.category} · ${Fmt.date(a.created_at)} · Status: ${Fmt.escape(a.status)}</div>
          </div>
        </div>
      `).join("") : UI.empty("No alerts generated for this work.");
    }
  },
};
