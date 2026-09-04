// app.js - app shell: hash routing, role switcher, scoping filters that
// get passed down to every page module.

const AppState = {
  role: "ministry",           // ministry | state | district | mp
  state_id: null,
  district_id: null,
  mp_id: null,
  metaStates: [],
  metaDistrictsCache: {},     // state_id -> [districts]
  metaMpsCache: {},           // state_id -> [mps]
};

const ROUTES = {
  overview:  { title: "Overview",            subtitle: () => scopeLabel(), render: (el, f) => Pages.overview.render(el, f) },
  works:     { title: "Works Explorer",       subtitle: () => "Browse, filter and drill into every recommended work", render: (el, f) => Pages.works.render(el, f) },
  anomalies: { title: "AI Anomaly Explorer",  subtitle: () => "Machine-learning + rule-based risk detection across all works", render: (el, f) => Pages.anomalies.render(el, f) },
  alerts:    { title: "Alerts",               subtitle: () => "Actionable, explainable alerts requiring attention", render: (el, f) => Pages.alerts.render(el, f) },
  command:   { title: "AI Command Centre",    subtitle: () => "An explainable situation report and decision workspace", render: (el, f) => Pages.command.render(el, f) },
  earlywarning: { title: "Early Warning",     subtitle: () => "Prevent delays and overruns before they become audit exceptions", render: (el, f) => Pages.earlywarning.render(el, f) },
  compliance: { title: "Compliance Monitor",  subtitle: () => "Guideline checks, documentation gaps and closure readiness", render: (el, f) => Pages.compliance.render(el, f) },
  map:       { title: "Geo Risk Monitor",     subtitle: () => "Location-aware prioritisation of works needing field verification", render: (el, f) => Pages.map.render(el, f) },
  rankings:  { title: "State Rankings",       subtitle: () => "Comparative risk & utilization across states", render: (el, f) => Pages.rankings.render(el, f) },
  model:     { title: "Model Performance",    subtitle: () => "How the detection pipeline is evaluated", render: (el, f) => Pages.model.render(el, f) },
};

function scopeLabel() {
  if (AppState.role === "mp") return "Scoped to selected Member of Parliament";
  if (AppState.role === "district") return "Scoped to selected district";
  if (AppState.role === "state") return "Scoped to selected state";
  return "National summary — all states";
}

function currentFilters() {
  const f = {};
  if (AppState.role === "mp" && AppState.mp_id) f.mp_id = AppState.mp_id;
  else if (AppState.role === "district" && AppState.district_id) f.district_id = AppState.district_id;
  else if (AppState.role === "state" && AppState.state_id) f.state_id = AppState.state_id;
  return f;
}

async function renderTopbarFilters() {
  const box = document.getElementById("topbar-filters");
  if (AppState.role === "ministry") { box.innerHTML = ""; return; }

  if (!AppState.metaStates.length) AppState.metaStates = await API.states();

  let html = `<select id="filter-state"><option value="">Select State…</option>` +
    AppState.metaStates.map(s => `<option value="${s.state_id}" ${AppState.state_id == s.state_id ? "selected" : ""}>${Fmt.escape(s.name)}</option>`).join("") +
    `</select>`;

  if (AppState.role === "district") {
    let districts = [];
    if (AppState.state_id) {
      districts = AppState.metaDistrictsCache[AppState.state_id] ||
        (AppState.metaDistrictsCache[AppState.state_id] = await API.districts(AppState.state_id));
    }
    html += `<select id="filter-district" ${!AppState.state_id ? "disabled" : ""}>
      <option value="">Select District…</option>
      ${districts.map(d => `<option value="${d.district_id}" ${AppState.district_id == d.district_id ? "selected" : ""}>${Fmt.escape(d.name)}</option>`).join("")}
    </select>`;
  }

  if (AppState.role === "mp") {
    let mps = [];
    if (AppState.state_id) {
      mps = AppState.metaMpsCache[AppState.state_id] ||
        (AppState.metaMpsCache[AppState.state_id] = await API.mps(AppState.state_id));
    }
    html += `<select id="filter-mp" ${!AppState.state_id ? "disabled" : ""}>
      <option value="">Select MP…</option>
      ${mps.map(m => `<option value="${m.mp_id}" ${AppState.mp_id == m.mp_id ? "selected" : ""}>${Fmt.escape(m.name)} (${Fmt.escape(m.constituency || m.state_name)})</option>`).join("")}
    </select>`;
  }

  box.innerHTML = html;

  const stateSel = document.getElementById("filter-state");
  if (stateSel) stateSel.addEventListener("change", (e) => {
    AppState.state_id = e.target.value || null;
    AppState.district_id = null;
    AppState.mp_id = null;
    renderTopbarFilters().then(navigate);
  });
  const distSel = document.getElementById("filter-district");
  if (distSel) distSel.addEventListener("change", (e) => { AppState.district_id = e.target.value || null; navigate(); });
  const mpSel = document.getElementById("filter-mp");
  if (mpSel) mpSel.addEventListener("change", (e) => { AppState.mp_id = e.target.value || null; navigate(); });
}

function setupRoleSwitcher() {
  document.getElementById("role-switcher").addEventListener("click", (e) => {
    const btn = e.target.closest(".role-pill");
    if (!btn) return;
    document.querySelectorAll(".role-pill").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    AppState.role = btn.dataset.role;
    AppState.state_id = null; AppState.district_id = null; AppState.mp_id = null;
    renderTopbarFilters().then(navigate);
  });
}

function setupNav() {
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", () => { window.location.hash = link.dataset.route; });
  });
}

async function refreshAlertBadge() {
  try {
    const alerts = await API.alerts({ severity: "Critical", status: "Open", limit: 500 });
    const el = document.getElementById("nav-alert-count");
    if (alerts.length > 0) { el.style.display = "inline-block"; el.textContent = alerts.length; }
    else { el.style.display = "none"; }
  } catch (e) { /* non-fatal */ }
}

async function navigate() {
  let route = (window.location.hash || "#overview").slice(1);
  if (!ROUTES[route]) route = "overview";

  document.querySelectorAll(".nav-link").forEach(l => l.classList.toggle("active", l.dataset.route === route));

  const cfg = ROUTES[route];
  document.getElementById("page-title").textContent = cfg.title;
  document.getElementById("page-subtitle").textContent = typeof cfg.subtitle === "function" ? cfg.subtitle() : cfg.subtitle;

  const content = document.getElementById("content");
  content.innerHTML = UI.loading();

  // Guard: scoped roles need a selection before we hit the API
  if (AppState.role !== "ministry") {
    const needsMore =
      (AppState.role === "state" && !AppState.state_id) ||
      (AppState.role === "district" && !AppState.district_id) ||
      (AppState.role === "mp" && !AppState.mp_id);
    if (needsMore) {
      content.innerHTML = UI.empty(`Select a ${AppState.role === "mp" ? "state, then a Member of Parliament" : AppState.role} above to view this dashboard.`);
      return;
    }
  }

  try {
    await cfg.render(content, currentFilters());
  } catch (err) {
    console.error(err);
    content.innerHTML = UI.empty(`Couldn't load this page. ${Fmt.escape(err.message || "")}<br><span style="font-size:11px;">Make sure the backend has been seeded: <code>python data_generator.py && python -m ml.train</code></span>`);
  }
}

window.addEventListener("hashchange", navigate);

document.addEventListener("DOMContentLoaded", async () => {
  setupRoleSwitcher();
  setupNav();
  await renderTopbarFilters();
  await navigate();
  refreshAlertBadge();
  setInterval(refreshAlertBadge, 60000);
});
