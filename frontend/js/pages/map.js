Pages = window.Pages || {};

Pages.map = {
  async render(container, filters) {
    const [works, allWorks] = await Promise.all([API.mapWorks(filters), API.mapWorks({ ...filters, risk_band: "Critical" })]);
    const groups = Object.values(works.reduce((out, w) => { const key = w.state_name; (out[key] ||= []).push(w); return out; }, {})).sort((a, b) => avgRisk(b) - avgRisk(a));
    container.innerHTML = `<div class="geo-summary"><div><span class="eyebrow">FIELD VERIFICATION VIEW</span><h2>${Fmt.num(works.length)} mappable works in scope</h2><p>Prioritise site inspections using location, risk score and execution status. This lightweight view works without a third-party map dependency.</p></div><div class="geo-stat"><strong>${Fmt.num(allWorks.length)}</strong><span>Critical locations</span></div></div><div class="section-gap geo-grid">${groups.map(group => geoCluster(group)).join("")}</div>`;
    document.querySelectorAll(".geo-work").forEach(item => item.addEventListener("click", () => WorkDetailModal.open(item.dataset.id)));
  },
};

function avgRisk(items) { return items.reduce((sum, x) => sum + (x.risk_score || 0), 0) / (items.length || 1); }
function geoCluster(items) {
  const state = items[0].state_name;
  const top = items.sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0)).slice(0, 5);
  return `<section class="geo-cluster"><div class="geo-cluster-head"><div><h3>${Fmt.escape(state)}</h3><span>${items.length} works · Avg. risk ${avgRisk(items).toFixed(0)}</span></div><span class="geo-dot"></span></div>${top.map(w => `<button class="geo-work" data-id="${w.work_id}"><span class="geo-pin ${Fmt.escape(w.risk_band)}"></span><span><strong>${Fmt.escape(w.description)}</strong><small>${Fmt.escape(w.district_name)} · ${Fmt.escape(w.status)}</small></span><b>${Math.round(w.risk_score || 0)}</b></button>`).join("")}</section>`;
}
