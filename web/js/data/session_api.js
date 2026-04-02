import { fetchJson, fetchText } from "./http.js";

const NO_STORE = { cache: "no-store" };

export async function fetchAnalysisSettings() {
  return fetchJson("/analysis_settings.json", NO_STORE);
}

export async function saveAnalysisReportSettings(reportSettingsUpdate) {
  const payload = reportSettingsUpdate && typeof reportSettingsUpdate === "object"
    ? reportSettingsUpdate
    : {};
  return fetchJson("/analysis_report_settings.json", {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function fetchCommodityLinks() {
  return fetchJson("/commodity_links.json", NO_STORE);
}

export async function fetchSessionFile(filename) {
  const safeName = encodeURIComponent(String(filename || ""));
  return fetchJson(`/session_data/${safeName}`, NO_STORE);
}

export async function fetchSessionDirectoryListing() {
  return fetchText("/session_data/", NO_STORE);
}

export async function fetchProspectedAsteroidSummary() {
  return fetchText("/session_data/prospected_asteroid_summary.jsonl", NO_STORE);
}

export async function fetchFavoriteRings() {
  return fetchJson("/config/hotspot_favorite_rings.json", NO_STORE);
}
