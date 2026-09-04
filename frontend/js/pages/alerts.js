// pages/alerts.js
window.Pages = window.Pages || {};

Pages.alerts = {
  state: { severity: "", status: "Open" },

  async render(el) {
    const st = Pages.alerts.state;
    el.innerHTML = `
      <div class="filters-row">
        <select id="al-severity">
          <option value="">All Severities</option>
          ${["Critical","High","Medium","Low"].map(s => `<option value="${s}" ${st.severity===s?"selected":""}>${s}</option>`).join("")}
        </select>
        <select id="al-status">
          ${["Open","Under Review","Resolved","Dismissed","All"].map(s => `<option value="${s}" ${st.status===s?"selected":""}>${s}</option>`).join("")}
        </select>
      </div>
      <div id="al-list">${UI.loading()}</div>
    `;
    document.getElementById("al-severity").addEventListener("change", (e) => { st.severity = e.target.value; load(); });
    document.getElementById("al-status").addEventListener("change", (e) => { st.status = e.target.value; load(); });
    await load();

    async function load() {
      const box = document.getElementById("al-list");
      box.innerHTML = UI.loading();
      const alerts = await API.alerts({ severity: st.severity || undefined, status: st.status, limit: 150 });
      if (!alerts.length) { box.innerHTML = UI.empty("No review alerts match this filter."); return; }
      box.innerHTML = alerts.map(a => `
        <div class="alert-card ${a.severity}" data-alert-id="${a.alert_id}">
          <div class="stripe"></div>
          <div class="body" data-work-id="${a.work_id}" style="cursor:pointer;">
            <div class="msg">${Fmt.escape(a.message)}</div>
            <div class="meta">
              ${UI.sevChip(a.severity)} &nbsp; ${RULE_LABELS[a.category] || a.category} &nbsp;·&nbsp;
              Work #${a.work_id}: ${Fmt.escape(truncate(a.description, 55))} &nbsp;·&nbsp;
              ${Fmt.escape(a.mp_name)}, ${Fmt.escape(a.district_name)} &nbsp;·&nbsp; ${Fmt.date(a.created_at)}
            </div>
          </div>
          <div class="alert-actions">
            <select class="btn btn-sm alert-status-select" data-alert-id="${a.alert_id}">
              ${["Open","Under Review","Resolved","Dismissed"].map(s => `<option value="${s}" ${a.status===s?"selected":""}>${s}</option>`).join("")}
            </select>
          </div>
        </div>
      `).join("");

      box.querySelectorAll(".body[data-work-id]").forEach(b => b.addEventListener("click", () => WorkDetailModal.open(b.dataset.workId)));
      box.querySelectorAll(".alert-status-select").forEach(sel => {
        sel.addEventListener("click", (e) => e.stopPropagation());
        sel.addEventListener("change", async (e) => {
          e.stopPropagation();
          await API.updateAlertStatus(sel.dataset.alertId, sel.value);
          load();
          refreshAlertBadge();
        });
      });
    }
  },
};

function truncate(s, n) { return s && s.length > n ? s.slice(0, n - 1) + "…" : s; }

window.Pages = Pages;
