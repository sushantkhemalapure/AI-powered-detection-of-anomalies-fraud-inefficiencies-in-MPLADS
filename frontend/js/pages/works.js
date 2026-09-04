window.Pages = window.Pages || {};

Pages.works = {
  state: { page: 1, sort: "risk_score_desc", risk_band: "", q: "" },
  async render(el, filters) {
    const st = Pages.works.state;
    el.innerHTML = `<div class="filters-row"><input type="text" class="search-box" id="record-search" placeholder="Search MP or allocation record..." value="${Fmt.escape(st.q)}"><select id="record-risk"><option value="">All review bands</option>${["Critical", "High", "Medium", "Low"].map(b => `<option value="${b}" ${st.risk_band === b ? "selected" : ""}>${b}</option>`).join("")}</select><select id="record-sort"><option value="risk_score_desc">Highest review score</option><option value="amount_desc">Highest allocation</option><option value="risk_score_asc">Lowest review score</option></select><a class="btn btn-sm" href="/api/export/allocations.csv">Download CSV</a></div><div class="card"><div id="record-table" class="table-wrap">${UI.loading()}</div><div class="pagination" id="record-pagination"></div></div>`;
    document.getElementById("record-search").addEventListener("input", debounce(() => { st.q = document.getElementById("record-search").value; st.page = 1; load(); }, 300));
    document.getElementById("record-risk").addEventListener("change", e => { st.risk_band = e.target.value; st.page = 1; load(); });
    document.getElementById("record-sort").addEventListener("change", e => { st.sort = e.target.value; st.page = 1; load(); });
    await load();
    async function load() {
      const table = document.getElementById("record-table"); table.innerHTML = UI.loading();
      const data = await API.works({ ...filters, page: st.page, page_size: 25, sort: st.sort, risk_band: st.risk_band, q: st.q });
      if (!data.items.length) { table.innerHTML = UI.empty("No allocation records match these filters."); return; }
      table.innerHTML = `<table><thead><tr><th>MP</th><th>State</th><th>Constituency</th><th>Allocated amount</th><th>Review score</th></tr></thead><tbody>${data.items.map(row => `<tr data-id="${row.work_id}"><td><strong>${Fmt.escape(row.mp_name)}</strong></td><td>${Fmt.escape(row.state_name)}</td><td>${Fmt.escape(row.district_name)}</td><td class="cell-amount">${Fmt.lakh(row.sanctioned_amount_lakh)}</td><td>${UI.riskBadge(row.risk_band, row.risk_score)}${UI.riskScoreBar(row.risk_score, row.risk_band)}</td></tr>`).join("")}</tbody></table>`;
      table.querySelectorAll("tr[data-id]").forEach(row => row.addEventListener("click", () => WorkDetailModal.open(row.dataset.id)));
      const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
      document.getElementById("record-pagination").innerHTML = `<span>${Fmt.num(data.total)} records; page ${st.page} of ${totalPages}</span><button class="btn btn-sm" id="record-prev" ${st.page === 1 ? "disabled" : ""}>Previous</button><button class="btn btn-sm" id="record-next" ${st.page === totalPages ? "disabled" : ""}>Next</button>`;
      document.getElementById("record-prev")?.addEventListener("click", () => { st.page--; load(); });
      document.getElementById("record-next")?.addEventListener("click", () => { st.page++; load(); });
    }
  },
};

function debounce(fn, ms) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); }; }
window.Pages = Pages;
