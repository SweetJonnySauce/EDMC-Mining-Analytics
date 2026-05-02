import { DEFAULT_THEME_ID, THEME_OPTIONS } from "../shared/theme.js";

const VALID_THEME_IDS = new Set(THEME_OPTIONS.map((option) => option.id));

export function normalizePersistedCompareThemeId(themeId, fallback = DEFAULT_THEME_ID) {
  const candidate = String(themeId || "").trim();
  if (VALID_THEME_IDS.has(candidate)) {
    return candidate;
  }
  return VALID_THEME_IDS.has(fallback) ? fallback : DEFAULT_THEME_ID;
}

export function buildPersistedCompareThemeUpdate(themeId) {
  return {
    compare: {
      compareThemeId: normalizePersistedCompareThemeId(themeId),
    },
  };
}

export function readPersistedCompareThemeId(payload, fallback = DEFAULT_THEME_ID) {
  const reportSettings = payload && typeof payload === "object" && payload.report_settings && typeof payload.report_settings === "object"
    ? payload.report_settings
    : null;
  const compareSettings = reportSettings && reportSettings.compare && typeof reportSettings.compare === "object"
    ? reportSettings.compare
    : null;
  return normalizePersistedCompareThemeId(compareSettings && compareSettings.compareThemeId, fallback);
}
