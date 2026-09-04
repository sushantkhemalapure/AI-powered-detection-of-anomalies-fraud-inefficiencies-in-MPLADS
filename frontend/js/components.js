const Fmt = {
  lakh(value) { if (value === null || value === undefined) return "-"; const amount = Number(value); return Math.abs(amount) >= 100 ? `Rs. ${(amount / 100).toFixed(2)} Cr` : `Rs. ${amount.toFixed(1)} L`; },
  num(value) { return value === null || value === undefined ? "-" : Number(value).toLocaleString("en-IN"); },
  pct(value, digits = 0) { return value === null || value === undefined ? "-" : `${Number(value).toFixed(digits)}%`; },
  date(value) { if (!value) return "-"; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }); },
  escape(value) { return value === null || value === undefined ? "" : String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])); },
};
const UI = {
  riskBadge(band, score) { const text = score !== undefined && score !== null ? ` ${Math.round(score)}` : ""; return `<span class="badge badge-${band}"><span class="badge-dot"></span>${band}${text}</span>`; },
  statusBadge(status) { return `<span class="badge badge-status">${Fmt.escape(status)}</span>`; },
  sevChip(severity) { return `<span class="sev-chip ${severity}">${severity}</span>`; },
  ruleChips(rules) { return !rules?.length ? `<span class="text-muted" style="font-size:12px;">Statistical allocation outlier</span>` : rules.map(rule => `<span class="rule-chip">${RULE_LABELS[rule] || rule}</span>`).join(""); },
  kpiCard(title, value, delta) { return `<div class="card"><h3>${title}</h3><div class="value">${value}</div>${delta ? `<div class="delta ${delta.cls || ""}">${delta.text}</div>` : ""}</div>`; },
  cardWrap(title, innerHtml, extraHeader = "") { return `<div class="card"><div class="card-title-row"><h3>${title}</h3>${extraHeader}</div>${innerHtml}</div>`; },
  empty(message) { return `<div class="empty-state">${message}</div>`; },
  loading() { return `<div class="loading-state"><div class="spinner"></div>Loading...</div>`; },
  riskScoreBar(score, band) { return `<div class="risk-score-bar"><div style="width:${Math.min(100, score || 0)}%; background:${Charts.RISK_COLORS[band] || "#94a3b8"};"></div></div>`; },
};
const RULE_LABELS = { STATISTICAL_OUTLIER: "Statistical allocation outlier" };
