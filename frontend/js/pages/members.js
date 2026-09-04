window.Pages = window.Pages || {};

Pages.members = {
  state: { page: 1, sort: "amount_desc", q: "" },
  async render(el, filters) {
    const st = Pages.members.state;
    el.innerHTML = `<div class="filters-row"><input class="search-box" id="member-search" placeholder="Search MP, constituency or state..." value="${Fmt.escape(st.q)}"><select id="member-sort"><option value="amount_desc">Highest allocation</option><option value="amount_asc">Lowest allocation</option><option value="risk_desc">Highest review score</option><option value="name_asc">Name A-Z</option></select></div><div class="card"><div id="member-table" class="table-wrap">${UI.loading()}</div><div id="member-pages" class="pagination"></div></div>`;
    document.getElementById("member-search").addEventListener("input", debounce(() => { st.q = document.getElementById("member-search").value; st.page = 1; load(); }, 300));
    document.getElementById("member-sort").addEventListener("change", e => { st.sort = e.target.value; st.page = 1; load(); });
    await load();
    async function load() {
      const table = document.getElementById("member-table"); table.innerHTML = UI.loading();
      const data = await API.members({ ...filters, page: st.page, page_size: 25, sort: st.sort, q: st.q });
      table.innerHTML = data.items.length ? `<table><thead><tr><th>Member of Parliament</th><th>Constituency</th><th>State</th><th>Allocated amount</th><th>Review score</th></tr></thead><tbody>${data.items.map(m => `<tr data-id="${m.work_id}"><td><strong>${Fmt.escape(m.mp_name)}</strong></td><td>${Fmt.escape(m.constituency)}</td><td>${Fmt.escape(m.state_name)}</td><td class="cell-amount">${Fmt.lakh(m.sanctioned_amount_lakh)}</td><td>${UI.riskBadge(m.risk_band, m.risk_score)}</td></tr>`).join("")}</tbody></table>` : UI.empty("No members match this search.");
      table.querySelectorAll("tr[data-id]").forEach(row => row.addEventListener("click", () => WorkDetailModal.open(row.dataset.id)));
      const pages = Math.max(1, Math.ceil(data.total / data.page_size));
      document.getElementById("member-pages").innerHTML = `<span>${Fmt.num(data.total)} records; page ${st.page} of ${pages}</span><button class="btn btn-sm" id="member-prev" ${st.page === 1 ? "disabled" : ""}>Previous</button><button class="btn btn-sm" id="member-next" ${st.page === pages ? "disabled" : ""}>Next</button>`;
      document.getElementById("member-prev")?.addEventListener("click", () => { st.page--; load(); });
      document.getElementById("member-next")?.addEventListener("click", () => { st.page++; load(); });
    }
  },
};
window.Pages = Pages;
