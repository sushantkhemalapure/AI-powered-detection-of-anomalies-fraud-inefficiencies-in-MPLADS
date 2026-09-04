// Shared formatting and small HTML helpers.
const Fmt = {
  lakh(value) {
    if (value === null || value === undefined) return "—";
    const amount = Number(value);
    if (Math.abs(amount) >= 100) return `₹${(amount / 100).toFixed(2)} Cr`;
    return `₹${amount.toFixed(1)} L`;
  },
  num(value) {
    if (value === null || value === undefined) return "—";
    return Number(value).toLocaleString("en-IN");
  },
  pct(value, digits = 0) {
    if (value === null || value === undefined) return "—";
    return `${Number(value).toFixed(digits)}%`;
  },
  date(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  },
  escape(value) {
    if (value === null || value === undefined) return "";
    return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  },
};

const UI = {
  riskBadge(band, score) {
    const scoreText = score !== undefined && score !== null ? ` ${Math.round(score)}` : "";
    return `<span class="badge badge-${band}"><span class="badge-dot"></span>${band}${scoreText}</span>`;
  },
  statusBadge(status) { return `<span class="badge badge-status">${Fmt.escape(status)}</span>`; },
  sevChip(severity) { return `<span class="sev-chip ${severity}">${severity}</span>`; },
  ruleChips(rules) {
    if (!rules || !rules.length) return `<span class="text-muted" style="font-size:12px;">No rule triggered</span>`;
    return rules.map(rule => `<span class="rule-chip">${RULE_LABELS[rule] || rule}</span>`).join("");
  },
  kpiCard(title, value, delta) {
    return `<div class="card"><h3>${title}</h3><div class="value">${value}</div>${delta ? `<div class="delta ${delta.cls || ""}">${delta.text}</div>` : ""}</div>`;
  },
  cardWrap(title, innerHtml, extraHeader = "") {
    return `<div class="card"><div class="card-title-row"><h3>${title}</h3>${extraHeader}</div>${innerHtml}</div>`;
  },
  empty(message) { return `<div class="empty-state">${message}</div>`; },
  loading() { return `<div class="loading-state"><div class="spinner"></div>Loading…</div>`; },
  riskScoreBar(score, band) {
    const color = Charts.RISK_COLORS[band] || "#94a3b8";
    return `<div class="risk-score-bar"><div style="width:${Math.min(100, score)}%; background:${color};"></div></div>`;
  },
};

const RULE_LABELS = {
  COST_OVERRUN: "Cost Overrun", GHOST_ASSET: "Ghost Asset", PROGRESS_MISMATCH: "Progress Mismatch",
  FRONT_LOADED_PAYMENT: "Front-loaded Payment", YEAR_END_RUSH: "Year-end Rush", STALLED_OVERDUE: "Stalled / Overdue",
  DUPLICATE_WORK: "Duplicate Work", FRAGMENTATION: "Fragmentation", VENDOR_CONCENTRATION: "Vendor Concentration",
  MISSING_UC: "Missing Utilization Certificate", STATISTICAL_OUTLIER: "Statistical Outlier (AI)",
};
