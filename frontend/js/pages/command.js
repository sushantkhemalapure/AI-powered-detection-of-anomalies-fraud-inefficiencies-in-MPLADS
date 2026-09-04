// pages/command.js - decision-support briefing with a safe offline fallback.
Pages = window.Pages || {};

Pages.command = {
  async render(container, filters) {
    const briefingFilters = { ...filters, role: AppState.role };
    const [summary, briefing, warnings] = await Promise.all([
      API.dashboardSummary(filters), API.briefing(briefingFilters), API.earlyWarning(filters),
    ]);
    const t = summary.totals || {};
    const risk = Object.fromEntries((summary.risk_breakdown || []).map(x => [x.risk_band, x.count]));
    container.innerHTML = `
      <div class="command-hero">
        <div><span class="eyebrow">LIVE DECISION SUPPORT</span><h2>What needs attention now?</h2><p>Prioritised from explainable risk rules, statistical outliers and predictive early-warning signals.</p></div>
        <div class="command-meta"><span class="status-pulse"></span>${briefing.source === "template" ? "Offline insight mode" : "AI insight mode"}<br><small>Scoped to your selected authority</small></div>
      </div>
      <div class="grid grid-4 section-gap">
        ${UI.kpiCard("Critical works", Fmt.num(risk.Critical || 0), { cls: "up", text: "Require immediate verification" })}
        ${UI.kpiCard("Open alerts", Fmt.num(summary.open_alerts || 0), { cls: "up", text: "Unresolved exceptions" })}
        ${UI.kpiCard("Prevention queue", Fmt.num(summary.early_warning_count || 0), { text: "At-risk works not yet high-risk" })}
        ${UI.kpiCard("Fund exposure", Fmt.lakh(t.total_sanctioned_lakh || 0), { text: "Sanctioned works in current scope" })}
      </div>
      <div class="grid grid-command section-gap">
        ${UI.cardWrap("AI Situation Report", `<div class="briefing-text">${Fmt.escape(briefing.text || "Briefing unavailable.")}</div><div class="briefing-note">${briefing.source === "template" ? "No external AI key is required for this deterministic, auditable briefing." : "Generated from the live dashboard context."}</div>`) }
        ${UI.cardWrap("Next best actions", `<div class="action-list">
          <div><b>1</b><span><strong>Freeze escalation checks</strong><small>Review critical cases before the next payment release.</small></span></div>
          <div><b>2</b><span><strong>Request evidence</strong><small>Ask implementing agencies for geo-tagged progress and UC records.</small></span></div>
          <div><b>3</b><span><strong>Prevent slippage</strong><small>Assign catch-up plans to the prevention queue.</small></span></div>
        </div><button class="btn btn-primary" id="go-early">Open prevention queue</button>`) }
      </div>
      <div class="section-gap">${UI.cardWrap("Highest-priority prevention signals", commandTable(warnings.slice(0, 6)), `<a href="#earlywarning" class="btn btn-sm btn-ghost">View all →</a>`)}</div>
      <div class="section-gap question-card"><label for="command-question">Ask Sentinel about this scope</label><div><input id="command-question" placeholder="e.g. What should the District Authority do first?"/><button class="btn btn-primary" id="command-ask">Ask</button></div><div id="command-answer"></div></div>`;
    document.getElementById("go-early").addEventListener("click", () => window.location.hash = "earlywarning");
    document.querySelectorAll(".command-work").forEach(row => row.addEventListener("click", () => WorkDetailModal.open(row.dataset.id)));
    document.getElementById("command-ask").addEventListener("click", async () => {
      const question = document.getElementById("command-question").value.trim();
      if (!question) return;
      const answer = document.getElementById("command-answer"); answer.innerHTML = UI.loading();
      try { const result = await API.ask(question, filters); answer.innerHTML = `<div class="answer-box">${Fmt.escape(result.answer)}</div>`; }
      catch (_) { answer.innerHTML = `<div class="answer-box">Unable to generate an answer right now.</div>`; }
    });
  },
};

function commandTable(rows) {
  if (!rows.length) return UI.empty("No active early-warning cases in this scope.");
  return `<div class="table-wrap"><table><thead><tr><th>Work</th><th>Risk signal</th><th>Recommended action</th></tr></thead><tbody>${rows.map(w => `<tr class="command-work" data-id="${w.work_id}"><td class="cell-desc"><div class="primary">${Fmt.escape(w.description)}</div><div class="secondary">${Fmt.escape(w.district_name)}, ${Fmt.escape(w.state_name)}</div></td><td><strong>${Math.round(w.early_warning_score || 0)}/100</strong><div class="secondary">Delay ${Math.round((w.delay_probability || 0) * 100)}% · Overrun ${Math.round((w.overrun_probability || 0) * 100)}%</div></td><td>${Fmt.escape(w.recommended_action || "Request a corrective action plan.")}</td></tr>`).join("")}</tbody></table></div>`;
}
