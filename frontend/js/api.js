// api.js - thin wrappers around the Flask JSON API.
// The frontend is served by the same Flask app, so relative paths work
// both in local dev and in any deployment that keeps them together.

const API = {
  async _get(path, params) {
    const url = new URL(path, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
      });
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
    return res.json();
  },

  async _post(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
    return res.json();
  },

  states: () => API._get("/api/meta/states"),
  districts: (state_id) => API._get("/api/meta/districts", { state_id }),
  mps: (state_id) => API._get("/api/meta/mps", { state_id }),
  categories: () => API._get("/api/meta/categories"),

  dashboardSummary: (filters) => API._get("/api/dashboard/summary", filters),
  dashboardTrend: (filters) => API._get("/api/dashboard/trend", filters),
  stateRanking: (filters) => API._get("/api/dashboard/state-ranking", filters),

  works: (filters) => API._get("/api/works", filters),
  workDetail: (id) => API._get(`/api/works/${id}`),

  anomalies: (filters) => API._get("/api/anomalies", filters),
  anomalyRuleFrequency: (filters) => API._get("/api/anomalies/rule-frequency", filters),
  modelEvaluation: () => API._get("/api/model/evaluation"),

  alerts: (filters) => API._get("/api/alerts", filters),
  updateAlertStatus: (id, status) => API._post(`/api/alerts/${id}/status`, { status }),
  briefing: (filters) => API._get("/api/insights/briefing", filters),
  ask: (question, filters = {}) => API._post(`/api/insights/ask?${new URLSearchParams(filters).toString()}`, { question }),
  earlyWarning: (filters) => API._get("/api/insights/early-warning", filters),
  compliance: (filters) => API._get("/api/insights/compliance", filters),
  mapWorks: (filters) => API._get("/api/map/works", filters),
};
