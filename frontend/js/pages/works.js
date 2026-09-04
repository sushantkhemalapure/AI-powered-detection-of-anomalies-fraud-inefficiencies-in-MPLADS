// pages/works.js
window.Pages = window.Pages || {};

Pages.works = {
  state: { page: 1, sort: "risk_score_desc", risk_band: "", status: "", category: "", q: "" },

  async render(el, filters) {
    const categories = await API.categories();
    const st = Pages.works.state;

    el.innerHTML = `
      <div class="filters-row">
        <input type="text" class="search-box" id="w-search" placeholder="Search description or MP name…" value="${Fmt.escape(st.q)}">
        <select id="w-risk">
          <option value="">All Risk Bands</option>
          ${["Critical","High","Medium","Low","Unscored"].map(b => `<option value="${b}" ${st.risk_band===b?"selected":""}>${b}</option>`).join("")}
        </select>
        <select id="w-status">
          <option value="">All Statuses</option>
          ${["Recommended","Sanctioned","InProgress","Delayed","Completed","Dropped"].map(s => `<option value="${s}" ${st.status===s?"selected":""}>${s}</option>`).join("")}
        </select>
        <select id="w-category">
          <option value="">All Categories</option>
          ${categories.map(c => `<option value="${Fmt.escape(c)}" ${st.category===c?"selected":""}>${Fmt.escape(c)}</option>`).join("")}
        </select>
        <select id="w-sort">
          <option value="risk_score_desc" ${st.sort==="risk_score_desc"?"selected":""}>Highest Risk First</option>
          <option value="risk_score_asc" ${st.sort==="risk_score_asc"?"selected":""}>Lowest Risk First</option>
          <option value="amount_desc" ${st.sort==="amount_desc"?"selected":""}>Highest Amount First</option>
          <option value="date_desc" ${st.sort==="date_desc"?"selected":""}>Most Recent</option>
        </select>
      </div>
      <div class="card">
        <div id="w-table-wrap" class="table-wrap">${UI.loading()}</div>
        <div class="pagination" id="w-pagination"></div>
      </div>
    `;

    const bindAndReload = () => { Pages.works.state.page = 1; loadTable(filters); };
    document.getElementById("w-search").addEventListener("input", debounce(() => { Pages.works.state.q = document.getElementById("w-search").value; bindAndReload(); }, 350));
    document.getElementById("w-risk").addEventListener("change", (e) => { Pages.works.state.risk_band = e.target.value; bindAndReload(); });
    document.getElementById("w-status").addEventListener("change", (e) => { Pages.works.state.status = e.target.value; bindAndReload(); });
    document.getElementById("w-category").addEventListener("change", (e) => { Pages.works.state.category = e.target.value; bindAndReload(); });
    document.getElementById("w-sort").addEventListener("change", (e) => { Pages.works.state.sort = e.target.value; bindAndReload(); });

    await loadTable(filters);

    async function loadTable(baseFilters) {
      const wrap = document.getElementById("w-table-wrap");
      wrap.innerHTML = UI.loading();
      const s = Pages.works.state;
      const data = await API.works({
        ...baseFilters, page: s.page, page_size: 25, sort: s.sort,
        risk_band: s.risk_band, status: s.status, category: s.category, q: s.q,
      });

      if (!data.items.length) { wrap.innerHTML = UI.empty("No works match these filters."); document.getElementById("w-pagination").innerHTML = ""; return; }

      wrap.innerHTML = `
        <table>
          <thead><tr>
            <th>Work</th><th>MP</th><th>Location</th><th>Category</th><th>Amount</th><th>Status</th><th>Risk</th>
          </tr></thead>
          <tbody>
            ${data.items.map(w => `
              <tr data-id="${w.work_id}">
                <td class="cell-desc"><div class="primary">${Fmt.escape(truncate(w.description, 70))}</div><div class="secondary">ID #${w.work_id}</div></td>
                <td>${Fmt.escape(w.mp_name)}</td>
                <td>${Fmt.escape(w.district_name)}<div class="secondary">${Fmt.escape(w.state_name)}</div></td>
                <td>${Fmt.escape(w.work_category)}</td>
                <td class="cell-amount">${Fmt.lakh(w.sanctioned_amount_lakh)}</td>
                <td>${UI.statusBadge(w.status)}</td>
                <td>${UI.riskBadge(w.risk_band, w.risk_score)}${UI.riskScoreBar(w.risk_score, w.risk_band)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      wrap.querySelectorAll("tbody tr").forEach(tr => {
        tr.addEventListener("click", () => WorkDetailModal.open(tr.dataset.id));
      });

      const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
      const pag = document.getElementById("w-pagination");
      pag.innerHTML = `
        <span>${Fmt.num(data.total)} works · Page ${s.page} of ${totalPages}</span>
        <button class="btn btn-sm" id="w-prev" ${s.page<=1?"disabled":""}>&larr; Prev</button>
        <button class="btn btn-sm" id="w-next" ${s.page>=totalPages?"disabled":""}>Next &rarr;</button>
      `;
      const prevBtn = document.getElementById("w-prev");
      const nextBtn = document.getElementById("w-next");
      if (prevBtn) prevBtn.addEventListener("click", () => { s.page--; loadTable(baseFilters); });
      if (nextBtn) nextBtn.addEventListener("click", () => { s.page++; loadTable(baseFilters); });
    }
  },
};

function truncate(s, n) { return s && s.length > n ? s.slice(0, n - 1) + "…" : s; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

window.Pages = Pages;
