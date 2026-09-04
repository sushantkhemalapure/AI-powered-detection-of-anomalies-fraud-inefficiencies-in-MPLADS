// Application shell: routing and source-compatible geographic/member scopes.
const AppState = { role: "ministry", state_id: null, district_id: null, mp_id: null, metaStates: [], metaDistrictsCache: {}, metaMpsCache: {} };

const ROUTES = {
  overview: { title: "Overview", subtitle: () => scopeLabel(), render: (el, f) => Pages.overview.render(el, f) },
  works: { title: "Allocation Records", subtitle: () => "Every MP allocation record in the supplied CSV", render: (el, f) => Pages.works.render(el, f) },
  members: { title: "MP Directory", subtitle: () => "Search and compare allocation records by Member of Parliament", render: (el, f) => Pages.members.render(el, f) },
  rankings: { title: "State Analysis", subtitle: () => "Compare allocation totals and allocation-pattern review scores", render: (el, f) => Pages.rankings.render(el, f) },
  anomalies: { title: "Outlier Review", subtitle: () => "Statistically unusual allocation amounts requiring source verification", render: (el, f) => Pages.anomalies.render(el, f) },
  alerts: { title: "Review Alerts", subtitle: () => "Track the status of allocation-pattern review prompts", render: (el, f) => Pages.alerts.render(el, f) },
  quality: { title: "Data Coverage", subtitle: () => "What the imported file contains and what it cannot support", render: (el, f) => Pages.quality.render(el, f) },
  model: { title: "Methodology", subtitle: () => "How allocation-pattern review scores are calculated", render: (el, f) => Pages.model.render(el, f) },
};

function scopeLabel() {
  if (AppState.role === "mp") return "Selected Member of Parliament";
  if (AppState.role === "district") return "Selected constituency";
  if (AppState.role === "state") return "Selected state";
  return "National allocation summary";
}

function currentFilters() {
  if (AppState.role === "mp" && AppState.mp_id) return { mp_id: AppState.mp_id };
  if (AppState.role === "district" && AppState.district_id) return { district_id: AppState.district_id };
  if (AppState.role === "state" && AppState.state_id) return { state_id: AppState.state_id };
  return {};
}

async function renderTopbarFilters() {
  const box = document.getElementById("topbar-filters");
  if (AppState.role === "ministry") { box.innerHTML = ""; return; }
  if (!AppState.metaStates.length) AppState.metaStates = await API.states();
  let html = `<select id="filter-state"><option value="">Select state...</option>${AppState.metaStates.map(s => `<option value="${s.state_id}" ${AppState.state_id == s.state_id ? "selected" : ""}>${Fmt.escape(s.name)}</option>`).join("")}</select>`;
  if (AppState.role === "district") {
    const districts = AppState.state_id ? (AppState.metaDistrictsCache[AppState.state_id] || (AppState.metaDistrictsCache[AppState.state_id] = await API.districts(AppState.state_id))) : [];
    html += `<select id="filter-district" ${!AppState.state_id ? "disabled" : ""}><option value="">Select constituency...</option>${districts.map(d => `<option value="${d.district_id}" ${AppState.district_id == d.district_id ? "selected" : ""}>${Fmt.escape(d.name)}</option>`).join("")}</select>`;
  }
  if (AppState.role === "mp") {
    const mps = AppState.state_id ? (AppState.metaMpsCache[AppState.state_id] || (AppState.metaMpsCache[AppState.state_id] = await API.mps(AppState.state_id))) : [];
    html += `<select id="filter-mp" ${!AppState.state_id ? "disabled" : ""}><option value="">Select MP...</option>${mps.map(m => `<option value="${m.mp_id}" ${AppState.mp_id == m.mp_id ? "selected" : ""}>${Fmt.escape(m.name)} (${Fmt.escape(m.constituency || m.state_name)})</option>`).join("")}</select>`;
  }
  box.innerHTML = html;
  document.getElementById("filter-state")?.addEventListener("change", e => { AppState.state_id = e.target.value || null; AppState.district_id = null; AppState.mp_id = null; renderTopbarFilters().then(navigate); });
  document.getElementById("filter-district")?.addEventListener("change", e => { AppState.district_id = e.target.value || null; navigate(); });
  document.getElementById("filter-mp")?.addEventListener("change", e => { AppState.mp_id = e.target.value || null; navigate(); });
}

function setupRoleSwitcher() {
  document.getElementById("role-switcher").addEventListener("click", e => {
    const button = e.target.closest(".role-pill");
    if (!button) return;
    document.querySelectorAll(".role-pill").forEach(b => b.classList.toggle("active", b === button));
    AppState.role = button.dataset.role;
    AppState.state_id = AppState.district_id = AppState.mp_id = null;
    renderTopbarFilters().then(navigate);
  });
}

function setupNav() { document.querySelectorAll(".nav-link").forEach(link => link.addEventListener("click", () => { window.location.hash = link.dataset.route; })); }

async function refreshAlertBadge() {
  try {
    const alerts = await API.alerts({ status: "Open", limit: 500 });
    const badge = document.getElementById("nav-alert-count");
    badge.style.display = alerts.length ? "inline-block" : "none";
    badge.textContent = alerts.length || "";
  } catch (_) { /* A missing database should not prevent navigation. */ }
}

async function navigate() {
  const route = ROUTES[(window.location.hash || "#overview").slice(1)] ? (window.location.hash || "#overview").slice(1) : "overview";
  document.querySelectorAll(".nav-link").forEach(link => link.classList.toggle("active", link.dataset.route === route));
  const cfg = ROUTES[route];
  document.getElementById("page-title").textContent = cfg.title;
  document.getElementById("page-subtitle").textContent = typeof cfg.subtitle === "function" ? cfg.subtitle() : cfg.subtitle;
  const content = document.getElementById("content"); content.innerHTML = UI.loading();
  const missing = (AppState.role === "state" && !AppState.state_id) || (AppState.role === "district" && !AppState.district_id) || (AppState.role === "mp" && !AppState.mp_id);
  if (missing) { content.innerHTML = UI.empty(`Select ${AppState.role === "mp" ? "a state, then an MP" : `a ${AppState.role}`} above to view this scope.`); return; }
  try { await cfg.render(content, currentFilters()); }
  catch (err) { console.error(err); content.innerHTML = UI.empty(`Couldn't load this page. ${Fmt.escape(err.message || "")}`); }
}

window.addEventListener("hashchange", navigate);
document.addEventListener("DOMContentLoaded", async () => { setupRoleSwitcher(); setupNav(); await renderTopbarFilters(); await navigate(); refreshAlertBadge(); setInterval(refreshAlertBadge, 60000); });
