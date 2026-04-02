import { applyAdaptiveBinLabels as applyAdaptiveBinLabelsShared } from "../shared/labels.js";
import { normalizeTextKey as normalizeTextKeyShared, normalizeCommodityKey as normalizeCommodityKeyShared } from "../shared/normalize.js";
import { asNumber as asNumberShared } from "../shared/number.js";
import { buildSmoothLinePath as buildSmoothLinePathShared } from "../shared/svg.js";
import { DEFAULT_THEME_ID, THEME_OPTIONS, createThemeController } from "../shared/theme.js";
import { createTooltipController } from "../shared/tooltip.js";
import {
  buildProspectHistogramModel as buildProspectHistogramModelExtracted,
  buildProspectCumulativeFrequencyModel as buildProspectCumulativeFrequencyModelExtracted,
  parseProspectedAsteroidSummaryText,
  resolveSessionRingLabel,
} from "./models/prospect_model.js";
import { buildMaterialPercentAmountModel as buildMaterialPercentAmountModelExtracted } from "./models/material_percent_model.js";
import { buildCumulativeCommoditySeries as buildCumulativeCommoditySeriesExtracted } from "./models/cumulative_commodity_model.js";
import { renderProspectHistogramSelection } from "./charts/prospect_histogram.js";
import { renderProspectCumulativeFrequencyChart } from "./charts/prospect_cumulative.js";
import { renderMaterialPercentAmountChart } from "./charts/material_percent.js";
import {
  normalizeTimelinePoints as normalizeTimelinePointsExtracted,
  buildTimelineBins as buildTimelineBinsExtracted,
  computeTimelinePeak as computeTimelinePeakExtracted,
  renderTimelineChart as renderTimelineChartExtracted,
} from "./charts/timeline.js";
import { renderCumulativeCommoditiesChart } from "./charts/cumulative_commodities.js";
import { wireDisplaySettingsControls } from "./ui/display_controls.js";
import { wireTimelineCheckboxFilters } from "./ui/timeline_filters.js";
import { createEventJournalController } from "./ui/event_journal.js";
import { createIndexStore } from "./state/store.js";
import { createIndexStateController } from "./state/controller.js";
import {
  fetchAnalysisSettings,
  saveAnalysisReportSettings,
  fetchCommodityLinks,
  fetchProspectedAsteroidSummary,
  fetchSessionDirectoryListing,
  fetchSessionFile,
} from "../data/session_api.js";

    (function () {
      const sessionSelect = document.getElementById("session-select");
      const compareRingsButton = document.getElementById("compare-rings-button");
      const sessionStatus = document.getElementById("session-status");
      const analysisStatus = document.getElementById("analysis-status");
      const analysisMetrics = document.getElementById("analysis-metrics");
      const chartCommodityTons = document.getElementById("chart-commodity-tons");
      const chartCommodityTph = document.getElementById("chart-commodity-tph");
      const chartContentMix = document.getElementById("chart-content-mix");
      const chartProspectHistogram = document.getElementById("chart-prospect-histogram");
      const prospectHistogramHeaderControls = document.getElementById("prospect-histogram-header-controls");
      const chartMaterialPercentAmount = document.getElementById("chart-material-percent-amount");
      const materialPercentCard = chartMaterialPercentAmount ? chartMaterialPercentAmount.closest(".chart-card") : null;
      const materialPercentShowCollectedInput = document.getElementById("material-percent-show-collected");
      const materialPercentShowGridlinesInput = document.getElementById("material-percent-show-gridlines");
      const materialPercentIncludeDuplicatesInput = document.getElementById("material-percent-include-duplicates");
      const materialPercentReverseCumulativeInput = document.getElementById("material-percent-reverse-cumulative");
      const materialPercentIntervalInputs = document.querySelectorAll("input[name=\"material-percent-interval\"]");
      const materialPercentYieldPopulationInputs = document.querySelectorAll("input[name=\"material-percent-yield-mode\"]");
      const chartProspectCumulativeFrequency = document.getElementById("chart-prospect-cumulative-frequency");
      const chartEvents = document.getElementById("chart-events");
      const chartRefinements = document.getElementById("chart-refinements");
      const chartCumulativeCommodities = document.getElementById("chart-cumulative-commodities");
      const cumulativeHeaderControls = document.getElementById("cumulative-header-controls");
      const prospectFrequencyHeaderControls = document.getElementById("prospect-frequency-header-controls");
      const prospectFrequencyTitle = document.getElementById("prospect-frequency-title");
      const commodityHistogramFilters = document.getElementById("commodity-histogram-filters");
      const refinementFilters = document.getElementById("refinement-filters");
      const eventFilters = document.getElementById("event-filters");
      const eventJournal = document.getElementById("event-journal");
      const estimatedProfitDetails = document.getElementById("estimated-profit-details");
      const rootElement = document.documentElement;
      const themeToggle = document.getElementById("theme-toggle");
      const themeMenu = document.getElementById("theme-menu");
      const THEME_STORAGE_KEY = "edmcma.analysis.theme";
      let runtimeAnalysisSettings = {};
      let activeThemeId = DEFAULT_THEME_ID;
      let selectedHistogramCommodity = "";
      let materialPercentHighlightedCommodityKey = "";
      let histogramSelectionClearedByMaterial = false;
      let activeSessionData = null;
      let activeSessionFilename = "";
      let materialPercentShowOnlyCollected = false;
      let materialPercentShowGridlines = true;
      let histogramShowOnlyCollected = false;
      let commodityLinkMap = new Map();
      let commodityAbbreviationMap = new Map();
      let commodityLinkLoadPromise = null;
      let prospectSummaryRecords = null;
      let prospectSummaryLoadPromise = null;
      let prospectFrequencyBinSize = 5;
      let prospectFrequencyIncludeDuplicates = true;
      let prospectFrequencyShowAverageReference = true;
      let prospectFrequencyReverseCumulative = false;
      let selectedYieldPopulationMode = "all";
      let prospectFrequencyRenderToken = 0;
      let adaptiveLabelResizeTimer = null;
      let sessionListRenderToken = 0;
      let hasAppliedPersistedIndexReportSettings = false;
      let indexReportSettingsSaveTimer = null;
      let allRefinementEntries = [];
      let refinementTimelineOptions = null;
      let refinementSelection = {};
      let cumulativeCommoditySelection = {};
      let cumulativeRenderMode = "line";
      let cumulativeValueMode = "quantity";
      let allEventEntries = [];
      let eventTimelineOptions = null;
      let eventTypeSelection = {};
      let histogramHoverContext = {
        commodityKey: "",
        binSize: 10,
        bars: []
      };
      let materialPercentHoverContext = {
        commodityKey: "",
        dots: []
      };
      let cumulativeHoverContext = {
        commodityKey: "",
        points: [],
        showLinkedCrosshair: null,
        hideLinkedCrosshair: null
      };
      let crossChartHighlightLinks = [];
      const indexStore = createIndexStore({
        runtimeAnalysisSettings,
        selectedHistogramCommodity,
        materialPercentHighlightedCommodityKey,
        histogramSelectionClearedByMaterial,
        activeSessionData,
        activeSessionFilename,
        materialPercentShowOnlyCollected,
        materialPercentShowGridlines,
        histogramShowOnlyCollected,
        prospectFrequencyBinSize,
        prospectFrequencyIncludeDuplicates,
        prospectFrequencyShowAverageReference,
        prospectFrequencyReverseCumulative,
        selectedYieldPopulationMode
      });
      const indexStateController = createIndexStateController(indexStore);
      const syncIndexStateMirrors = (nextState) => {
        const state = nextState && typeof nextState === "object" ? nextState : {};
        runtimeAnalysisSettings = state.runtimeAnalysisSettings && typeof state.runtimeAnalysisSettings === "object"
          ? state.runtimeAnalysisSettings
          : {};
        selectedHistogramCommodity = typeof state.selectedHistogramCommodity === "string"
          ? state.selectedHistogramCommodity
          : "";
        materialPercentHighlightedCommodityKey = typeof state.materialPercentHighlightedCommodityKey === "string"
          ? state.materialPercentHighlightedCommodityKey
          : "";
        histogramSelectionClearedByMaterial = !!state.histogramSelectionClearedByMaterial;
        activeSessionData = state.activeSessionData || null;
        activeSessionFilename = typeof state.activeSessionFilename === "string"
          ? state.activeSessionFilename
          : "";
        materialPercentShowOnlyCollected = !!state.materialPercentShowOnlyCollected;
        materialPercentShowGridlines = state.materialPercentShowGridlines !== false;
        histogramShowOnlyCollected = !!state.histogramShowOnlyCollected;
        prospectFrequencyBinSize = Number(state.prospectFrequencyBinSize) === 10 ? 10 : 5;
        prospectFrequencyIncludeDuplicates = state.prospectFrequencyIncludeDuplicates !== false;
        prospectFrequencyShowAverageReference = state.prospectFrequencyShowAverageReference !== false;
        prospectFrequencyReverseCumulative = !!state.prospectFrequencyReverseCumulative;
        selectedYieldPopulationMode = String(state.selectedYieldPopulationMode || "").trim().toLowerCase() === "present"
          ? "present"
          : "all";
      };
      syncIndexStateMirrors(indexStateController.getState());
      indexStateController.subscribe((nextState) => {
        syncIndexStateMirrors(nextState);
      });

      function getIndexRenderState() {
        const state = indexStateController.getState();
        return {
          runtimeAnalysisSettings: state && typeof state.runtimeAnalysisSettings === "object"
            ? state.runtimeAnalysisSettings
            : {},
          selectedHistogramCommodity: typeof (state && state.selectedHistogramCommodity) === "string"
            ? state.selectedHistogramCommodity
            : "",
          materialPercentHighlightedCommodityKey: typeof (state && state.materialPercentHighlightedCommodityKey) === "string"
            ? state.materialPercentHighlightedCommodityKey
            : "",
          histogramSelectionClearedByMaterial: !!(state && state.histogramSelectionClearedByMaterial),
          activeSessionData: (state && state.activeSessionData) || null,
          activeSessionFilename: typeof (state && state.activeSessionFilename) === "string"
            ? state.activeSessionFilename
            : "",
          materialPercentShowOnlyCollected: !!(state && state.materialPercentShowOnlyCollected),
          materialPercentShowGridlines: !(state && state.materialPercentShowGridlines === false),
          histogramShowOnlyCollected: !!(state && state.histogramShowOnlyCollected),
          prospectFrequencyBinSize: Number(state && state.prospectFrequencyBinSize) === 10 ? 10 : 5,
          prospectFrequencyIncludeDuplicates: !(state && state.prospectFrequencyIncludeDuplicates === false),
          prospectFrequencyShowAverageReference: !(state && state.prospectFrequencyShowAverageReference === false),
          prospectFrequencyReverseCumulative: !!(state && state.prospectFrequencyReverseCumulative),
          selectedYieldPopulationMode: String(state && state.selectedYieldPopulationMode || "").trim().toLowerCase() === "present"
            ? "present"
            : "all",
          activeThemeId
        };
      }

      const tooltipController = createTooltipController();
      const themeController = createThemeController({
        rootElement,
        themeToggle,
        themeMenu,
        storageKey: THEME_STORAGE_KEY,
        defaultThemeId: DEFAULT_THEME_ID,
        themeOptions: THEME_OPTIONS,
        onThemeChange: (themeId) => {
          activeThemeId = themeId;
        }
      });

      function applyFocusTokenToTitle() {
        try {
          const params = new URLSearchParams(window.location.search || "");
          const token = (params.get("edmcma_focus_token") || "").trim();
          if (token) {
            document.title = `${document.title} [${token}]`;
          }
        } catch (_err) {
          // Keep default title if URL parsing fails.
        }
      }

      function initializeThemeControl() {
        themeController.initialize();
      }

      function setStatus(target, text, level) {
        target.textContent = text;
        target.classList.remove("ok", "warn", "bad");
        if (level) {
          target.classList.add(level);
        }
      }

      function ensureCursorTooltip() {
        return tooltipController.ensure();
      }

      function showCursorTooltip(text, event) {
        ensureCursorTooltip();
        tooltipController.show(text, event);
      }

      function hideCursorTooltip() {
        tooltipController.hide();
      }

      function trackCrossChartHighlight(element, className) {
        if (!element || !className) {
          return;
        }
        const alreadyTracked = crossChartHighlightLinks.some((entry) => (
          entry.element === element && entry.className === className
        ));
        if (alreadyTracked) {
          return;
        }
        element.classList.add(className);
        crossChartHighlightLinks.push({ element, className });
      }

      function clearCrossChartHoverHighlights() {
        if (!crossChartHighlightLinks.length) {
          if (typeof cumulativeHoverContext.hideLinkedCrosshair === "function") {
            cumulativeHoverContext.hideLinkedCrosshair();
          }
          return;
        }
        crossChartHighlightLinks.forEach((entry) => {
          if (entry && entry.element && entry.className) {
            entry.element.classList.remove(entry.className);
          }
        });
        crossChartHighlightLinks = [];
        if (typeof cumulativeHoverContext.hideLinkedCrosshair === "function") {
          cumulativeHoverContext.hideLinkedCrosshair();
        }
      }

      function resetCrossChartHoverContexts() {
        clearCrossChartHoverHighlights();
        histogramHoverContext = {
          commodityKey: "",
          binSize: 10,
          bars: []
        };
        materialPercentHoverContext = {
          commodityKey: "",
          dots: []
        };
        cumulativeHoverContext = {
          commodityKey: "",
          points: [],
          showLinkedCrosshair: null,
          hideLinkedCrosshair: null
        };
      }

      function showLinkedCumulativeCrosshair(pointEntryOrEntries) {
        if (typeof cumulativeHoverContext.showLinkedCrosshair !== "function") {
          return;
        }
        cumulativeHoverContext.showLinkedCrosshair(pointEntryOrEntries);
      }

      function pointEntryHasCurrentDot(pointEntry) {
        return !!(
          pointEntry
          && Array.isArray(pointEntry.currentDots)
          && pointEntry.currentDots.length > 0
        );
      }

      function rangeContainsValue(start, end, isLast, value) {
        const s = Number(start);
        const e = Number(end);
        const v = Number(value);
        if (!Number.isFinite(s) || !Number.isFinite(e) || !Number.isFinite(v)) {
          return false;
        }
        if (v < s) {
          return false;
        }
        if (isLast) {
          return v <= (e + 1e-9);
        }
        return v < e;
      }

      function rangesOverlap(startA, endA, isLastA, startB, endB, isLastB) {
        const aStart = Number(startA);
        const aEnd = Number(endA);
        const bStart = Number(startB);
        const bEnd = Number(endB);
        if (![aStart, aEnd, bStart, bEnd].every((value) => Number.isFinite(value))) {
          return false;
        }
        const left = Math.max(aStart, bStart);
        const right = Math.min(aEnd, bEnd);
        if (left < right) {
          return true;
        }
        if (Math.abs(left - right) > 1e-9) {
          return false;
        }
        const touchingAEnd = Math.abs(left - aEnd) <= 1e-9;
        const touchingBEnd = Math.abs(left - bEnd) <= 1e-9;
        if (touchingAEnd && !isLastA) {
          return false;
        }
        if (touchingBEnd && !isLastB) {
          return false;
        }
        return true;
      }

      function getHistogramBarIndexForPercentage(percentage) {
        const bars = Array.isArray(histogramHoverContext.bars) ? histogramHoverContext.bars : [];
        if (!bars.length) {
          return null;
        }
        const raw = Number(percentage);
        if (!Number.isFinite(raw)) {
          return null;
        }
        const pct = Math.max(0, raw);
        for (let index = 0; index < bars.length; index += 1) {
          const barEntry = bars[index];
          if (!barEntry) {
            continue;
          }
          if (rangeContainsValue(barEntry.rangeStart, barEntry.rangeEnd, barEntry.isLast, pct)) {
            return index;
          }
        }
        return null;
      }

      function highlightCumulativePointEntry(pointEntry, currentOnly) {
        if (!pointEntry) {
          return;
        }
        const dots = currentOnly
          ? (Array.isArray(pointEntry.currentDots) ? pointEntry.currentDots : [])
          : (Array.isArray(pointEntry.dots) ? pointEntry.dots : []);
        dots.forEach((dot) => {
          trackCrossChartHighlight(dot, "prospect-frequency-dot--linked");
        });
      }

      function highlightFromHistogramBarEntry(barEntry) {
        clearCrossChartHoverHighlights();
        if (!barEntry || !barEntry.element) {
          return;
        }
        trackCrossChartHighlight(barEntry.element, "histogram-bar--linked");

        const selectedKey = normalizeCommodityKey(histogramHoverContext.commodityKey);
        if (!selectedKey) {
          return;
        }

        materialPercentHoverContext.dots.forEach((dotEntry) => {
          if (!dotEntry || !dotEntry.element) {
            return;
          }
          if (normalizeCommodityKey(dotEntry.commodityKey) !== selectedKey) {
            return;
          }
          if (!rangeContainsValue(barEntry.rangeStart, barEntry.rangeEnd, barEntry.isLast, dotEntry.percentage)) {
            return;
          }
          trackCrossChartHighlight(dotEntry.element, "material-percent-dot--linked");
        });

        if (normalizeCommodityKey(cumulativeHoverContext.commodityKey) !== selectedKey) {
          return;
        }
        const linkedCrosshairPoints = [];
        cumulativeHoverContext.points.forEach((pointEntry) => {
          if (!pointEntry) {
            return;
          }
          if (
            !rangesOverlap(
              barEntry.rangeStart,
              barEntry.rangeEnd,
              barEntry.isLast,
              pointEntry.intervalStart,
              pointEntry.intervalEnd,
              pointEntry.isLast,
            )
          ) {
            return;
          }
          highlightCumulativePointEntry(pointEntry, true);
          if (pointEntryHasCurrentDot(pointEntry)) {
            linkedCrosshairPoints.push(pointEntry);
          }
        });
        if (linkedCrosshairPoints.length) {
          showLinkedCumulativeCrosshair(linkedCrosshairPoints);
        }
      }

      function highlightFromMaterialPercentDotEntry(dotEntry) {
        clearCrossChartHoverHighlights();
        if (!dotEntry || !dotEntry.element) {
          return;
        }
        trackCrossChartHighlight(dotEntry.element, "material-percent-dot--linked");

        const selectedKey = normalizeCommodityKey(histogramHoverContext.commodityKey);
        if (!selectedKey) {
          return;
        }
        if (normalizeCommodityKey(dotEntry.commodityKey) !== selectedKey) {
          return;
        }

        const barIndex = getHistogramBarIndexForPercentage(dotEntry.percentage);
        if (barIndex !== null) {
          const barEntry = histogramHoverContext.bars[barIndex];
          if (barEntry && barEntry.element) {
            trackCrossChartHighlight(barEntry.element, "histogram-bar--linked");
          }
        }

        if (normalizeCommodityKey(cumulativeHoverContext.commodityKey) !== selectedKey) {
          return;
        }
        const linkedCrosshairPoints = [];
        cumulativeHoverContext.points.forEach((pointEntry) => {
          if (!pointEntry) {
            return;
          }
          if (!rangeContainsValue(pointEntry.intervalStart, pointEntry.intervalEnd, pointEntry.isLast, dotEntry.percentage)) {
            return;
          }
          highlightCumulativePointEntry(pointEntry, true);
          if (pointEntryHasCurrentDot(pointEntry)) {
            linkedCrosshairPoints.push(pointEntry);
          }
        });
        if (linkedCrosshairPoints.length) {
          showLinkedCumulativeCrosshair(linkedCrosshairPoints);
        }
      }

      function highlightFromCumulativePointEntry(pointEntry) {
        clearCrossChartHoverHighlights();
        if (!pointEntry) {
          return;
        }
        highlightCumulativePointEntry(pointEntry);

        const selectedKey = normalizeCommodityKey(histogramHoverContext.commodityKey);
        if (!selectedKey) {
          return;
        }
        if (normalizeCommodityKey(cumulativeHoverContext.commodityKey) !== selectedKey) {
          return;
        }

        histogramHoverContext.bars.forEach((barEntry) => {
          if (!barEntry || !barEntry.element) {
            return;
          }
          if (
            !rangesOverlap(
              barEntry.rangeStart,
              barEntry.rangeEnd,
              barEntry.isLast,
              pointEntry.intervalStart,
              pointEntry.intervalEnd,
              pointEntry.isLast,
            )
          ) {
            return;
          }
          trackCrossChartHighlight(barEntry.element, "histogram-bar--linked");
        });

        materialPercentHoverContext.dots.forEach((dotEntry) => {
          if (!dotEntry || !dotEntry.element) {
            return;
          }
          if (normalizeCommodityKey(dotEntry.commodityKey) !== selectedKey) {
            return;
          }
          if (!rangeContainsValue(pointEntry.intervalStart, pointEntry.intervalEnd, pointEntry.isLast, dotEntry.percentage)) {
            return;
          }
          trackCrossChartHighlight(dotEntry.element, "material-percent-dot--linked");
        });
      }

      async function refreshAnalysisSettings() {
        try {
          const result = await fetchAnalysisSettings();
          if (!result.ok) {
            return;
          }
          const payload = result.data;
          if (!payload || typeof payload !== "object") {
            return;
          }
          indexStateController.setRuntimeAnalysisSettings(payload);
          if (!hasAppliedPersistedIndexReportSettings) {
            const reportSettings = payload.report_settings && typeof payload.report_settings === "object"
              ? payload.report_settings
              : {};
            const indexReportSettings = reportSettings.index && typeof reportSettings.index === "object"
              ? reportSettings.index
              : null;
            if (indexReportSettings) {
              applyPersistedIndexReportSettings(indexReportSettings);
              syncDisplaySettingInputs(getIndexRenderState());
            }
            hasAppliedPersistedIndexReportSettings = true;
          }
        } catch (_error) {
          // Keep defaults when settings endpoint is unavailable.
        }
      }

      function coerceInaraCommodityId(raw) {
        if (Number.isFinite(Number(raw))) {
          const value = Math.trunc(Number(raw));
          return value > 0 ? value : null;
        }
        if (raw && typeof raw === "object") {
          const nested = raw.id ?? raw.inara_id;
          if (Number.isFinite(Number(nested))) {
            const value = Math.trunc(Number(nested));
            return value > 0 ? value : null;
          }
        }
        return null;
      }

      function coerceCommodityAbbreviation(raw) {
        if (!raw || typeof raw !== "object") {
          return "";
        }
        const candidate = (
          (typeof raw.abbr === "string" && raw.abbr.trim())
          || (typeof raw.abbreviation === "string" && raw.abbreviation.trim())
          || ""
        );
        return String(candidate || "");
      }

      async function ensureCommodityLinkMap() {
        if (commodityLinkMap.size > 0) {
          return;
        }
        if (!commodityLinkLoadPromise) {
          commodityLinkLoadPromise = (async () => {
            try {
              const result = await fetchCommodityLinks();
              if (!result.ok) {
                return;
              }
              const payload = result.data;
              if (!payload || typeof payload !== "object") {
                return;
              }
              const nextMap = new Map();
              const nextAbbreviations = new Map();
              Object.entries(payload).forEach(([key, value]) => {
                const normalized = normalizeCommodityKey(key);
                if (!normalized) {
                  return;
                }
                const id = coerceInaraCommodityId(value);
                if (id !== null) {
                  nextMap.set(normalized, id);
                }
                const abbreviation = coerceCommodityAbbreviation(value);
                if (abbreviation) {
                  nextAbbreviations.set(normalized, abbreviation);
                }
              });
              commodityLinkMap = nextMap;
              commodityAbbreviationMap = nextAbbreviations;
            } catch (_error) {
              commodityLinkMap = new Map();
              commodityAbbreviationMap = new Map();
            } finally {
              commodityLinkLoadPromise = null;
            }
          })();
        }
        await commodityLinkLoadPromise;
      }

      function parseBooleanLike(value, fallback) {
        if (value === true || value === false) {
          return value;
        }
        if (value === 1 || value === "1" || value === "true") {
          return true;
        }
        if (value === 0 || value === "0" || value === "false") {
          return false;
        }
        return fallback;
      }

      function parsePositiveNumber(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric) || numeric <= 0) {
          return null;
        }
        return numeric;
      }

      function normalizeBooleanSetting(value, fallback) {
        if (value === true || value === false) {
          return value;
        }
        if (value === 1 || value === "1" || value === "true") {
          return true;
        }
        if (value === 0 || value === "0" || value === "false") {
          return false;
        }
        return !!fallback;
      }

      function normalizeBinSizeSetting(value, fallback) {
        const numeric = Number(value);
        if (numeric === 10 || numeric === 5) {
          return numeric;
        }
        return Number(fallback) === 10 ? 10 : 5;
      }

      function normalizeCumulativeRenderModeSetting(value, fallback) {
        const text = String(value || "").trim().toLowerCase();
        if (text === "line" || text === "stacked-area") {
          return text;
        }
        return String(fallback || "").trim().toLowerCase() === "stacked-area" ? "stacked-area" : "line";
      }

      function normalizeCumulativeValueModeSetting(value, fallback) {
        const text = String(value || "").trim().toLowerCase();
        if (text === "quantity" || text === "profit") {
          return text;
        }
        return String(fallback || "").trim().toLowerCase() === "profit" ? "profit" : "quantity";
      }

      function normalizeYieldPopulationModeSetting(value, fallback) {
        const text = String(value || "").trim().toLowerCase();
        if (text === "all" || text === "present") {
          return text;
        }
        return String(fallback || "").trim().toLowerCase() === "present" ? "present" : "all";
      }

      function buildPersistedIndexReportSettings(stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        return {
          materialPercentShowOnlyCollected: !!renderState.materialPercentShowOnlyCollected,
          materialPercentShowGridlines: renderState.materialPercentShowGridlines !== false,
          prospectFrequencyIncludeDuplicates: renderState.prospectFrequencyIncludeDuplicates !== false,
          prospectFrequencyBinSize: Number(renderState.prospectFrequencyBinSize) === 10 ? 10 : 5,
          prospectFrequencyReverseCumulative: !!renderState.prospectFrequencyReverseCumulative,
          prospectFrequencyShowAverageReference: renderState.prospectFrequencyShowAverageReference !== false,
          selectedYieldPopulationMode: normalizeYieldPopulationModeSetting(
            renderState.selectedYieldPopulationMode,
            "all"
          ),
          cumulativeRenderMode: normalizeCumulativeRenderModeSetting(cumulativeRenderMode, "line"),
          cumulativeValueMode: normalizeCumulativeValueModeSetting(cumulativeValueMode, "quantity"),
        };
      }

      function applyPersistedIndexReportSettings(rawSettings) {
        const defaults = buildPersistedIndexReportSettings(getIndexRenderState());
        const source = rawSettings && typeof rawSettings === "object" ? rawSettings : {};
        indexStateController.setMaterialPercentCollectedMode(
          normalizeBooleanSetting(source.materialPercentShowOnlyCollected, defaults.materialPercentShowOnlyCollected)
        );
        indexStateController.setMaterialPercentGridlines(
          normalizeBooleanSetting(source.materialPercentShowGridlines, defaults.materialPercentShowGridlines)
        );
        indexStateController.setProspectFrequencyIncludeDuplicates(
          normalizeBooleanSetting(source.prospectFrequencyIncludeDuplicates, defaults.prospectFrequencyIncludeDuplicates)
        );
        indexStateController.setProspectFrequencyBinSize(
          normalizeBinSizeSetting(source.prospectFrequencyBinSize, defaults.prospectFrequencyBinSize)
        );
        indexStateController.setProspectFrequencyReverseCumulative(
          normalizeBooleanSetting(source.prospectFrequencyReverseCumulative, defaults.prospectFrequencyReverseCumulative)
        );
        indexStateController.setProspectFrequencyShowAverageReference(
          normalizeBooleanSetting(
            source.prospectFrequencyShowAverageReference,
            defaults.prospectFrequencyShowAverageReference
          )
        );
        indexStateController.setSelectedYieldPopulationMode(
          normalizeYieldPopulationModeSetting(
            source.selectedYieldPopulationMode,
            defaults.selectedYieldPopulationMode
          )
        );
        cumulativeRenderMode = normalizeCumulativeRenderModeSetting(
          source.cumulativeRenderMode,
          defaults.cumulativeRenderMode
        );
        cumulativeValueMode = normalizeCumulativeValueModeSetting(
          source.cumulativeValueMode,
          defaults.cumulativeValueMode
        );
      }

      function syncDisplaySettingInputs(stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        if (materialPercentShowCollectedInput) {
          materialPercentShowCollectedInput.checked = !!renderState.materialPercentShowOnlyCollected;
        }
        if (materialPercentShowGridlinesInput) {
          materialPercentShowGridlinesInput.checked = renderState.materialPercentShowGridlines !== false;
        }
        if (materialPercentIncludeDuplicatesInput) {
          materialPercentIncludeDuplicatesInput.checked = renderState.prospectFrequencyIncludeDuplicates !== false;
        }
        if (materialPercentReverseCumulativeInput) {
          materialPercentReverseCumulativeInput.checked = !!renderState.prospectFrequencyReverseCumulative;
        }
        if (materialPercentIntervalInputs && materialPercentIntervalInputs.length) {
          const selectedBinSize = Number(renderState.prospectFrequencyBinSize) === 10 ? 10 : 5;
          materialPercentIntervalInputs.forEach((input) => {
            if (!(input instanceof HTMLInputElement)) {
              return;
            }
            input.checked = Number(input.value) === selectedBinSize;
          });
        }
        if (materialPercentYieldPopulationInputs && materialPercentYieldPopulationInputs.length) {
          const selectedMode = renderState.selectedYieldPopulationMode === "present" ? "present" : "all";
          materialPercentYieldPopulationInputs.forEach((input) => {
            if (!(input instanceof HTMLInputElement)) {
              return;
            }
            input.checked = String(input.value || "").trim().toLowerCase() === selectedMode;
          });
        }
      }

      function schedulePersistIndexReportSettings() {
        if (indexReportSettingsSaveTimer !== null) {
          window.clearTimeout(indexReportSettingsSaveTimer);
        }
        indexReportSettingsSaveTimer = window.setTimeout(async () => {
          indexReportSettingsSaveTimer = null;
          try {
            await saveAnalysisReportSettings({
              index: buildPersistedIndexReportSettings(getIndexRenderState()),
            });
          } catch (_error) {
            // Keep the UI responsive if saving settings fails.
          }
        }, 350);
      }

      function buildInaraCommoditySearchUrl(options) {
        const source = options && typeof options === "object" ? options : {};
        const key = normalizeCommodityKey(source.commodityKey);
        const commodityId = commodityLinkMap.get(key);
        if (!Number.isFinite(commodityId)) {
          return null;
        }

        const referenceSystemRaw = String(source.referenceSystem || "").trim();
        if (!referenceSystemRaw) {
          return null;
        }

        const sortMode = String(source.sortMode || "best_price").trim().toLowerCase();
        const includeCarriers = parseBooleanLike(source.includeCarriers, true);
        const includeSurface = parseBooleanLike(source.includeSurface, true);
        const hasLargePad = parseBooleanLike(source.hasLargePad, false);

        const query = new URLSearchParams();
        query.set("formbrief", "1");
        query.set("pi1", "2");
        query.append("pa1[]", String(Math.trunc(commodityId)));
        query.set("ps1", referenceSystemRaw);
        query.set("pi10", sortMode === "nearest" ? "3" : "1");
        query.set("pi4", includeSurface ? "1" : "0");
        query.set("pi8", includeCarriers ? "1" : "0");
        query.set("pi13", "0");
        query.set("pi12", "0");
        query.set("pi14", "0");
        query.set("ps3", "");

        const distanceLy = parsePositiveNumber(source.distanceLy);
        if (distanceLy !== null) {
          query.set("pi11", String(Math.trunc(distanceLy)));
        }
        if (hasLargePad) {
          query.set("pi3", "3");
        }
        const distanceLs = parsePositiveNumber(source.distanceLs);
        if (distanceLs !== null) {
          query.set("pi9", String(Math.trunc(distanceLs)));
        }
        const minDemand = parsePositiveNumber(source.minDemand);
        if (minDemand !== null) {
          query.set("pi7", String(Math.trunc(minDemand)));
        }
        const ageDays = parsePositiveNumber(source.ageDays);
        if (ageDays !== null) {
          query.set("pi5", String(Math.trunc(ageDays) * 24));
        }

        return `https://inara.cz/elite/commodities/?${query.toString()}`;
      }

      function createInaraLinkButton(url, commodityLabel) {
        const label = String(commodityLabel || "commodity");
        if (typeof url !== "string" || !url.trim()) {
          const disabled = document.createElement("span");
          disabled.className = "estimated-profit-inara-link estimated-profit-inara-link--disabled";
          disabled.textContent = "Inara";
          disabled.setAttribute("title", `No Inara mapping available for ${label}.`);
          return disabled;
        }
        const link = document.createElement("a");
        link.className = "estimated-profit-inara-link";
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Inara";
        link.setAttribute("title", `Open Inara search for ${label}`);
        link.setAttribute("aria-label", `Open Inara search for ${label}`);
        return link;
      }

      function formatSessionDateTimeFromFilename(filename) {
        const match = /^session_data_(\d+)\.json$/.exec(filename || "");
        if (!match) {
          return {
            dateLabel: filename || "Unknown session",
            timeLabel: ""
          };
        }
        const epochSeconds = Number(match[1]);
        if (!Number.isFinite(epochSeconds)) {
          return {
            dateLabel: filename,
            timeLabel: ""
          };
        }
        const stamp = new Date(epochSeconds * 1000);
        return {
          dateLabel: stamp.toLocaleDateString(),
          timeLabel: stamp.toLocaleTimeString()
        };
      }

      function resolveSessionAsteroidCount(sessionData) {
        const meta = sessionData && typeof sessionData === "object" ? (sessionData.meta || {}) : {};
        const prospected = meta && typeof meta === "object" ? (meta.prospected || {}) : {};
        const rawTotal = Number(prospected.total);
        if (Number.isFinite(rawTotal) && rawTotal >= 0) {
          return Math.floor(rawTotal);
        }
        const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
        const counted = events.reduce((count, event) => (
          event && event.type === "prospected_asteroid" ? count + 1 : count
        ), 0);
        return counted > 0 ? counted : null;
      }

      function resolveSessionMostCollectedCommodity(sessionData) {
        const root = sessionData && typeof sessionData === "object" ? sessionData : {};
        const commodities = root.commodities && typeof root.commodities === "object" ? root.commodities : {};
        const commodityEntries = Object.entries(commodities)
          .map(([name, details]) => {
            const payload = details && typeof details === "object" ? details : {};
            const gathered = payload.gathered && typeof payload.gathered === "object" ? payload.gathered : {};
            const tons = Number(gathered.tons);
            const asteroids = Number(payload.asteroids_prospected);
            return {
              name: String(name || "").trim(),
              tons: Number.isFinite(tons) ? tons : 0,
              asteroids: Number.isFinite(asteroids) ? asteroids : 0
            };
          })
          .filter((entry) => !!entry.name);
        if (commodityEntries.length) {
          commodityEntries.sort((left, right) => {
            if (right.tons !== left.tons) {
              return right.tons - left.tons;
            }
            if (right.asteroids !== left.asteroids) {
              return right.asteroids - left.asteroids;
            }
            return left.name.localeCompare(right.name);
          });
          if (commodityEntries[0].tons > 0) {
            return commodityEntries[0].name;
          }
        }

        const events = Array.isArray(root.events) ? root.events : [];
        const refinedCounts = new Map();
        events.forEach((event) => {
          if (!event || event.type !== "mining_refined") {
            return;
          }
          const details = event.details && typeof event.details === "object" ? event.details : {};
          const localized = typeof details.type_localised === "string" ? details.type_localised.trim() : "";
          const rawType = typeof details.type === "string" ? details.type.trim() : "";
          const name = localized || rawType
            .replace(/^\$/, "")
            .replace(/;$/, "")
            .replace(/_name$/i, "")
            .replace(/_/g, " ")
            .trim();
          if (!name) {
            return;
          }
          refinedCounts.set(name, (refinedCounts.get(name) || 0) + 1);
        });
        if (refinedCounts.size > 0) {
          const ranked = Array.from(refinedCounts.entries()).sort((left, right) => {
            if (right[1] !== left[1]) {
              return right[1] - left[1];
            }
            return left[0].localeCompare(right[0]);
          });
          return ranked[0][0];
        }

        return "";
      }

      function formatSessionOptionLabel(filename, ringLabel, asteroidCount, commodityLabel) {
        const when = formatSessionDateTimeFromFilename(filename);
        const ring = typeof ringLabel === "string" && ringLabel.trim() ? ringLabel.trim() : "Unknown";
        const asteroidText = Number.isFinite(asteroidCount)
          ? formatNumber(Math.max(0, Math.floor(asteroidCount)), 0)
          : "--";
        const commodityText = typeof commodityLabel === "string" && commodityLabel.trim()
          ? commodityLabel.trim()
          : "--";
        if (!when.timeLabel) {
          return `${when.dateLabel}, ${ring}, (Asteroids: ${asteroidText}, ${commodityText})`;
        }
        return `${when.dateLabel}, ${when.timeLabel}, ${ring}, (Asteroids: ${asteroidText}, ${commodityText})`;
      }

      async function fetchSessionOptionDetails(filename) {
        if (!filename) {
          return { ringLabel: "", asteroidCount: null, commodityLabel: "" };
        }
        try {
          const result = await fetchSessionFile(filename);
          if (!result.ok) {
            return { ringLabel: "", asteroidCount: null, commodityLabel: "" };
          }
          const payload = result.data;
          const ring = String(resolveSessionRingLabel(payload) || "").trim();
          return {
            ringLabel: ring && ring !== "Unknown" ? ring : "",
            asteroidCount: resolveSessionAsteroidCount(payload),
            commodityLabel: resolveSessionMostCollectedCommodity(payload)
          };
        } catch (_error) {
          return { ringLabel: "", asteroidCount: null, commodityLabel: "" };
        }
      }

      function pickFilename(href) {
        if (!href) {
          return null;
        }
        const clean = href.split("?")[0].split("#")[0];
        const file = clean.split("/").pop() || "";
        if (/^session_data_\d+\.json$/.test(file)) {
          return file;
        }
        return null;
      }

      async function copyTextToClipboard(text) {
        const value = String(text ?? "");
        if (!value.trim()) {
          return false;
        }
        try {
          if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            await navigator.clipboard.writeText(value);
            return true;
          }
        } catch (_error) {
          // Fall back to execCommand path.
        }

        try {
          const textarea = document.createElement("textarea");
          textarea.value = value;
          textarea.setAttribute("readonly", "readonly");
          textarea.style.position = "fixed";
          textarea.style.opacity = "0";
          textarea.style.left = "-9999px";
          document.body.appendChild(textarea);
          textarea.focus();
          textarea.select();
          const copied = document.execCommand("copy");
          document.body.removeChild(textarea);
          return !!copied;
        } catch (_error) {
          return false;
        }
      }

      function createCopyButton(copyValue, options) {
        const text = String(copyValue ?? "");
        if (!text.trim()) {
          return null;
        }
        const settings = options && typeof options === "object" ? options : {};
        const button = document.createElement("button");
        button.type = "button";
        button.className = "metric-copy-btn";
        button.setAttribute("aria-label", String(settings.ariaLabel || "Copy"));
        button.setAttribute("title", String(settings.title || "Copy"));
        button.setAttribute("data-tooltip", String(settings.tooltip || "Copied!"));
        button.innerHTML = "<svg viewBox='0 0 16 16' aria-hidden='true'><rect x='6' y='2.5' width='7' height='9' rx='1.2'></rect><rect x='3' y='5.5' width='7' height='9' rx='1.2'></rect></svg>";

        let copiedTimer = null;
        button.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          const copied = await copyTextToClipboard(text);
          if (!copied) {
            setStatus(analysisStatus, String(settings.failMessage || "Unable to copy text."), "warn");
            return;
          }
          if (copiedTimer) {
            window.clearTimeout(copiedTimer);
          }
          button.classList.add("metric-copy-btn--copied");
          copiedTimer = window.setTimeout(() => {
            button.classList.remove("metric-copy-btn--copied");
            copiedTimer = null;
          }, 1000);
        });

        return button;
      }

      function renderMetrics(entries) {
        analysisMetrics.innerHTML = "";

        // Width lock: keep existing summary pill widths stable.
        // New pills can be added without changing these widths; they default to "s" unless explicitly mapped.
        const metricSizeByLabel = Object.freeze({
          file: "l",
          start: "l",
          end: "l",
          ship: "l",
          system: "l",
          "body/ring": "l",
          tons: "s",
          "tons collected": "s",
          "duration (hours)": "s",
          "tons/hour": "s",
          "total est. profit": "s",
          asteroids: "s",
          "asteroids prospected": "s",
          prospected: "s",
          "prospectors launched": "s",
          "collectors launched": "s",
          "collectors abandoned": "s",
          "duplicate prospectors": "s",
          "prospectors lost": "s",
          "limpet dumps": "s",
          "highest yield (refined)": "l",
          "commodity types": "s",
          "commodities ignored": "s",
          cargo: "s"
        });
        const metricTooltipByLabel = {
          "limpet dumps": "Limpet dump count based on configured threshold."
        };

        for (const [label, value, tooltipOverride] of entries) {
          const normalizedLabel = String(label || "").trim().toLowerCase();
          const size = metricSizeByLabel[normalizedLabel] || "s";
          const metricTooltip = String(tooltipOverride || metricTooltipByLabel[normalizedLabel] || "");
          const card = document.createElement("article");
          card.className = `metric metric--${size}`;
          if (metricTooltip) {
            card.title = metricTooltip;
          }

          const heading = document.createElement("div");
          heading.className = "label";
          heading.textContent = label;
          heading.title = metricTooltip || String(label);

          const body = document.createElement("div");
          body.className = "value";
          const valueText = String(value ?? "--");
          if (normalizedLabel === "system" && valueText && valueText !== "--") {
            body.classList.add("value--copyable");

            const valueSpan = document.createElement("span");
            valueSpan.className = "metric-value-text";
            valueSpan.textContent = valueText;
            valueSpan.title = metricTooltip ? `${valueText}\n${metricTooltip}` : valueText;

            const copyButton = createCopyButton(valueText, {
              ariaLabel: "Copy system name",
              title: "Copy system name",
              failMessage: "Unable to copy system name."
            });

            body.appendChild(valueSpan);
            if (copyButton) {
              body.appendChild(copyButton);
            }
          } else {
            body.textContent = valueText;
            body.title = metricTooltip ? `${valueText}\n${metricTooltip}` : valueText;
          }

          card.appendChild(heading);
          card.appendChild(body);
          analysisMetrics.appendChild(card);
        }
      }

      function asNumber(value) {
        return asNumberShared(value);
      }

      function renderProspectFrequencyTitle(sessionData, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        if (!prospectFrequencyTitle) {
          return;
        }
        const commodity = String(renderState.selectedHistogramCommodity || "").trim();
        const ringLabel = sessionData ? String(resolveSessionRingLabel(sessionData) || "").trim() : "";
        let baseTitle = "Cumulative Frequency";
        if (commodity && ringLabel && ringLabel !== "Unknown") {
          baseTitle = `Cumulative Frequency (${commodity} - ${ringLabel})`;
        } else if (commodity) {
          baseTitle = `Cumulative Frequency (${commodity})`;
        }
        prospectFrequencyTitle.textContent = renderState.prospectFrequencyReverseCumulative
          ? `${baseTitle} - Reversed`
          : baseTitle;
      }

      function openCompareRingsPage(stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        const params = new URLSearchParams();
        params.set("theme", renderState.activeThemeId || DEFAULT_THEME_ID);
        const selectedCommodity = String(renderState.selectedHistogramCommodity || "").trim();
        if (selectedCommodity) {
          const commodityKey = selectedCommodity.toLowerCase().replace(/[^a-z0-9]+/g, "");
          if (commodityKey) {
            params.set("commodity", commodityKey);
          }
        }
        const url = `/web/compare.html?${params.toString()}`;
        window.open(url, "_blank", "noopener");
      }

      function applyMaterialPercentCommoditySelection(commodityName, commodityKey, isCollected) {
        const applied = indexStateController.applyMaterialCommoditySelection(
          commodityName,
          commodityKey,
          isCollected,
          normalizeCommodityKey
        );
        if (!applied) {
          return;
        }
        const renderState = getIndexRenderState();
        if (renderState.activeSessionData) {
          renderProspectHistogram(renderState.activeSessionData, renderState);
          renderMaterialPercentAmount(renderState.activeSessionData, renderState);
        }
      }

      function clearCharts(message) {
        hideCursorTooltip();
        resetCrossChartHoverContexts();
        const text = message || "No chart data available.";
        if (eventFilters) {
          eventFilters.innerHTML = "";
        }
        if (commodityHistogramFilters) {
          commodityHistogramFilters.innerHTML = "";
        }
        if (refinementFilters) {
          refinementFilters.innerHTML = "";
        }
        if (eventJournal) {
          eventJournal.innerHTML = "";
        }
        if (estimatedProfitDetails) {
          estimatedProfitDetails.innerHTML = "";
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = text;
          estimatedProfitDetails.appendChild(note);
        }
        if (cumulativeHeaderControls) {
          cumulativeHeaderControls.innerHTML = "";
        }
        if (prospectFrequencyHeaderControls) {
          prospectFrequencyHeaderControls.innerHTML = "";
        }
        indexStateController.clearHistogramCommoditySelection();
        indexStateController.clearActiveSession();
        const renderState = getIndexRenderState();
        renderProspectFrequencyTitle(null, renderState);
        prospectFrequencyRenderToken += 1;
        allRefinementEntries = [];
        refinementTimelineOptions = null;
        refinementSelection = {};
        cumulativeCommoditySelection = {};
        allEventEntries = [];
        eventTimelineOptions = null;
        eventTypeSelection = {};
        eventJournalController.reset();
        [chartCommodityTons, chartCommodityTph, chartContentMix, chartProspectHistogram, chartProspectCumulativeFrequency, chartRefinements, chartCumulativeCommodities, chartEvents].forEach((container) => {
          container.innerHTML = "";
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = text;
          container.appendChild(note);
        });
      }

      function formatNumber(value, decimals) {
        const amount = asNumber(value);
        return amount.toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals
        });
      }

      function formatLocalClock(ms) {
        if (!Number.isFinite(ms)) {
          return "--";
        }
        return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      }

      function formatLocalDateTime(value) {
        if (typeof value !== "string" || !value.trim()) {
          return "--";
        }
        const stamp = Date.parse(value);
        if (!Number.isFinite(stamp)) {
          return value;
        }
        return new Date(stamp).toLocaleString([], {
          year: "numeric",
          month: "short",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        });
      }

      function formatCredits(value, decimals) {
        const amount = Number(value);
        if (!Number.isFinite(amount)) {
          return "--";
        }
        const digits = Number.isInteger(decimals) ? decimals : 0;
        return `${formatNumber(amount, digits)} CR`;
      }

      function computeEstimatedSellTotalValue(sessionData, estimatedSell) {
        const model = buildCumulativeCommoditySeries(sessionData);
        if (model && Array.isArray(model.series) && model.series.length) {
          return model.series.reduce((sum, item) => {
            if (!item || !Array.isArray(item.points) || !item.points.length) {
              return sum;
            }
            const lastPoint = item.points[item.points.length - 1] || {};
            const profit = Number(lastPoint.profit);
            return Number.isFinite(profit) ? (sum + profit) : sum;
          }, 0);
        }
        const byCommodity = Array.isArray(estimatedSell && estimatedSell.by_commodity)
          ? estimatedSell.by_commodity
          : [];
        return byCommodity.reduce((sum, entry) => {
          if (!entry || typeof entry !== "object") {
            return sum;
          }
          const explicitValue = Number(entry.estimated_value_cr);
          if (Number.isFinite(explicitValue)) {
            return sum + explicitValue;
          }
          const tons = Number(entry.tons);
          const sellPrice = Number(entry.sell_price);
          if (Number.isFinite(tons) && tons >= 0 && Number.isFinite(sellPrice) && sellPrice >= 0) {
            return sum + (tons * sellPrice);
          }
          return sum;
        }, 0);
      }

      function renderEstimatedProfitDetails(sessionData, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        if (!estimatedProfitDetails) {
          return;
        }
        estimatedProfitDetails.innerHTML = "";
        const meta = sessionData && typeof sessionData === "object" ? (sessionData.meta || {}) : {};
        const estimatedSell = meta && typeof meta.estimated_sell === "object" ? meta.estimated_sell : null;
        if (!estimatedSell) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "No estimated profit snapshot available for this session.";
          estimatedProfitDetails.appendChild(note);
          return;
        }

        const normalizeSortMode = (value) => {
          const text = String(value || "").trim().toLowerCase();
          if (text === "nearest") {
            return "Nearest";
          }
          if (text === "best_price") {
            return "Best Price";
          }
          return value || "--";
        };
        const formatYesNo = (value) => {
          if (value === true) {
            return "Yes";
          }
          if (value === false) {
            return "No";
          }
          return "--";
        };
        const formatDistance = (value, unit) => {
          const numeric = Number(value);
          if (!Number.isFinite(numeric) || numeric < 0) {
            return unit === "ls" ? "Any" : "--";
          }
          return `${formatNumber(numeric, 1)} ${unit}`;
        };

        const sessionCriteria = estimatedSell.search_criteria && typeof estimatedSell.search_criteria === "object"
          ? estimatedSell.search_criteria
          : {};
        const runtimeSettings = renderState.runtimeAnalysisSettings
          && typeof renderState.runtimeAnalysisSettings === "object"
          ? renderState.runtimeAnalysisSettings
          : {};
        const runtimeCriteria = runtimeSettings.market_search_criteria
          && typeof runtimeSettings.market_search_criteria === "object"
          ? runtimeSettings.market_search_criteria
          : {};
        const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
        const readCriteria = (key, fallbackValue) => {
          if (hasOwn(sessionCriteria, key)) {
            return sessionCriteria[key];
          }
          if (hasOwn(runtimeCriteria, key)) {
            return runtimeCriteria[key];
          }
          return fallbackValue;
        };
        const criteriaSource = Object.keys(sessionCriteria).length ? "Session Snapshot" : "Current Settings";

        const coverageRatioRaw = Number(estimatedSell.coverage_ratio);
        const coverageRatio = Number.isFinite(coverageRatioRaw)
          ? `${formatNumber(coverageRatioRaw * 100, 1)}%`
          : "--";
        const pricedTonsRaw = Number(estimatedSell.priced_tons);
        const totalTonsRaw = Number(estimatedSell.total_tons);
        const coverageTons = Number.isFinite(pricedTonsRaw) && Number.isFinite(totalTonsRaw)
          ? `${formatNumber(pricedTonsRaw, 0)} / ${formatNumber(totalTonsRaw, 0)} t`
          : "--";
        const pricedCommodities = Number(estimatedSell.priced_commodities);
        const unpricedCommodities = Number(estimatedSell.unpriced_commodities);

        const totalEstimatedProfit = computeEstimatedSellTotalValue(sessionData, estimatedSell);
        const settingsRows = [
          ["Total Estimated Profit", formatCredits(totalEstimatedProfit, 0)],
          ["Captured", formatLocalDateTime(estimatedSell.captured_at)],
          ["Criteria Source", criteriaSource],
          ["Search Sort Mode", normalizeSortMode(readCriteria("sort_mode", estimatedSell.sort_mode))],
          ["Reference System", String(readCriteria("reference_system", (meta.location && meta.location.system) || "--") || "--")],
          ["Large Pad Only", formatYesNo(readCriteria("has_large_pad", null))],
          ["Include Fleet Carriers", formatYesNo(readCriteria("include_carriers", null))],
          ["Include Surface Stations", formatYesNo(readCriteria("include_surface", null))],
          ["Minimum Demand", formatNumber(Number(readCriteria("min_demand", 0)), 0)],
          ["Market Data Max Age", `${formatNumber(Number(readCriteria("age_days", 0)), 0)} days`],
          ["Search Radius", formatDistance(readCriteria("distance_ly", null), "ly")],
          ["Max Arrival Distance", formatDistance(readCriteria("distance_ls", null), "ls")],
          ["Coverage", `${coverageRatio} (${coverageTons})`],
          [
            "Priced Commodities",
            `${formatNumber(pricedCommodities, 0)} priced / ${formatNumber(unpricedCommodities, 0)} unpriced`
          ]
        ];

        const settingsGrid = document.createElement("div");
        settingsGrid.className = "estimated-profit-settings";
        settingsRows.forEach(([label, value]) => {
          const card = document.createElement("div");
          card.className = "estimated-profit-setting";
          const labelNode = document.createElement("div");
          labelNode.className = "estimated-profit-setting-label";
          labelNode.textContent = String(label);
          const valueNode = document.createElement("div");
          valueNode.className = "estimated-profit-setting-value";
          valueNode.textContent = String(value);
          card.appendChild(labelNode);
          card.appendChild(valueNode);
          settingsGrid.appendChild(card);
        });
        estimatedProfitDetails.appendChild(settingsGrid);

        const byCommodity = Array.isArray(estimatedSell.by_commodity) ? estimatedSell.by_commodity : [];
        if (!byCommodity.length) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "No per-commodity pricing details available.";
          estimatedProfitDetails.appendChild(note);
          return;
        }

        const list = document.createElement("ul");
        list.className = "estimated-profit-list";
        byCommodity.forEach((entry) => {
          if (!entry || typeof entry !== "object") {
            return;
          }
          const item = document.createElement("li");
          item.className = "estimated-profit-item";

          const header = document.createElement("div");
          header.className = "estimated-profit-item-header";
          const name = document.createElement("span");
          name.className = "estimated-profit-item-name";
          name.textContent = String(entry.name || entry.key || "Unknown");
          const value = document.createElement("span");
          value.className = "estimated-profit-item-value";
          value.textContent = formatCredits(entry.estimated_value_cr, 0);
          header.appendChild(name);
          header.appendChild(value);

          const tons = Number(entry.tons);
          const sellPrice = Number(entry.sell_price);
          const pricingMeta = document.createElement("div");
          pricingMeta.className = "estimated-profit-item-meta";
          if (Number.isFinite(tons) && Number.isFinite(sellPrice)) {
            pricingMeta.textContent = `${formatNumber(tons, 0)} t × ${formatCredits(sellPrice, 0)} = ${formatCredits(entry.estimated_value_cr, 0)}`;
          } else if (Number.isFinite(tons)) {
            pricingMeta.textContent = `${formatNumber(tons, 0)} t | Price unavailable`;
          } else {
            pricingMeta.textContent = "Price unavailable";
          }

          const source = entry.price_source && typeof entry.price_source === "object" ? entry.price_source : null;
          const commodityKey = normalizeCommodityKey(entry.key || entry.name);
          const referenceSystem = String(
            readCriteria("reference_system", (meta.location && meta.location.system) || "")
          ).trim();
          const inaraUrl = buildInaraCommoditySearchUrl({
            commodityKey,
            referenceSystem,
            sortMode: readCriteria("sort_mode", estimatedSell.sort_mode),
            hasLargePad: readCriteria("has_large_pad", null),
            includeCarriers: readCriteria("include_carriers", true),
            includeSurface: readCriteria("include_surface", true),
            minDemand: readCriteria("min_demand", 0),
            ageDays: readCriteria("age_days", 0),
            distanceLy: readCriteria("distance_ly", null),
            distanceLs: readCriteria("distance_ls", null)
          });

          const where = document.createElement("div");
          where.className = "estimated-profit-item-meta";
          if (source) {
            const station = typeof source.station_name === "string" && source.station_name.trim()
              ? source.station_name.trim()
              : "Unknown station";
            const system = typeof source.system_name === "string" && source.system_name.trim()
              ? source.system_name.trim()
              : "Unknown system";
            const distanceLy = Number(source.distance_ly);
            const arrivalLs = Number(source.distance_to_arrival);
            const distanceBits = [];
            if (Number.isFinite(distanceLy)) {
              distanceBits.push(`${formatNumber(distanceLy, 1)} ly`);
            }
            if (Number.isFinite(arrivalLs)) {
              distanceBits.push(`${formatNumber(arrivalLs, 1)} ls`);
            }
            const marketUpdated = formatLocalDateTime(source.market_updated_at);
            const distanceText = distanceBits.length ? ` | ${distanceBits.join(" | ")}` : "";
            const copyButton = createCopyButton(system, {
              ariaLabel: `Copy system name ${system}`,
              title: "Copy system name",
              failMessage: "Unable to copy system name."
            });
            if (copyButton) {
              where.appendChild(document.createTextNode(`Sell at ${station} (`));
              where.appendChild(document.createTextNode(system));
              copyButton.setAttribute("aria-label", `Copy system name ${system}`);
              copyButton.setAttribute("title", "Copy system name");
              copyButton.classList.add("estimated-profit-inline-copy-btn");
              where.appendChild(copyButton);
              where.appendChild(document.createTextNode(`)${distanceText} | Market updated: ${marketUpdated}`));
            } else {
              where.textContent = `Sell at ${station} (${system})${distanceText} | Market updated: ${marketUpdated}`;
            }
          } else {
            where.textContent = "Sell location unavailable.";
          }

          item.appendChild(header);
          item.appendChild(pricingMeta);
          const lastRow = document.createElement("div");
          lastRow.className = "estimated-profit-item-last-row";
          lastRow.appendChild(where);
          lastRow.appendChild(createInaraLinkButton(inaraUrl, entry.name || entry.key));
          item.appendChild(lastRow);
          list.appendChild(item);
        });
        estimatedProfitDetails.appendChild(list);
      }

      function formatDurationWithHours(seconds) {
        const rawSeconds = Number(seconds);
        if (!Number.isFinite(rawSeconds) || rawSeconds < 0) {
          return "--";
        }
        const totalSeconds = Math.max(0, Math.round(rawSeconds));
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const secs = totalSeconds % 60;
        const hh = String(hours).padStart(2, "0");
        const mm = String(minutes).padStart(2, "0");
        const ss = String(secs).padStart(2, "0");
        const decimalHours = (totalSeconds / 3600).toFixed(2);
        return `${hh}:${mm}:${ss} (${decimalHours} hr)`;
      }

      function buildCommodityRows(sessionData) {
        const source = sessionData && typeof sessionData === "object" ? (sessionData.commodities || {}) : {};
        return Object.entries(source).map(([name, details]) => {
          const payload = details && typeof details === "object" ? details : {};
          const gathered = payload.gathered && typeof payload.gathered === "object" ? payload.gathered : {};
          return {
            name: String(name),
            tons: asNumber(gathered.tons),
            tph: asNumber(payload.tons_per_hour),
            asteroids: asNumber(payload.asteroids_prospected)
          };
        }).filter((row) => row.tons > 0 || row.tph > 0 || row.asteroids > 0);
      }

      function renderBarChart(container, rows, getValue, formatValue, coolColors) {
        container.innerHTML = "";
        if (!rows.length) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "No commodity data in this session.";
          container.appendChild(note);
          return;
        }

        const maxValue = Math.max(...rows.map((row) => Math.max(0, getValue(row))), 0);
        if (maxValue <= 0) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "Values are zero for this chart.";
          container.appendChild(note);
          return;
        }

        const list = document.createElement("div");
        list.className = "bar-list";

        rows.forEach((row) => {
          const value = Math.max(0, getValue(row));
          const ratio = maxValue > 0 ? value / maxValue : 0;

          const rowEl = document.createElement("div");
          rowEl.className = "bar-row";

          const meta = document.createElement("div");
          meta.className = "bar-meta";

          const label = document.createElement("span");
          label.className = "bar-label";
          label.textContent = row.name;
          label.title = row.name;

          const valueEl = document.createElement("span");
          valueEl.className = "bar-value";
          valueEl.textContent = formatValue(value);

          meta.appendChild(label);
          meta.appendChild(valueEl);

          const track = document.createElement("div");
          track.className = "bar-track";

          const fill = document.createElement("div");
          fill.className = coolColors ? "bar-fill cool" : "bar-fill";
          fill.style.width = `${Math.max(2, ratio * 100)}%`;
          fill.title = `${row.name}: ${formatValue(value)}`;

          track.appendChild(fill);
          rowEl.appendChild(meta);
          rowEl.appendChild(track);
          list.appendChild(rowEl);
        });

        container.appendChild(list);
      }

      function renderContentMix(sessionData) {
        chartContentMix.innerHTML = "";
        const meta = sessionData && typeof sessionData === "object" ? (sessionData.meta || {}) : {};
        const summary = meta.content_summary && typeof meta.content_summary === "object" ? meta.content_summary : {};
        const entries = [
          { name: "Low", color: "#f25f5c", count: asNumber(summary.Low) },
          { name: "Medium", color: "#f7c948", count: asNumber(summary.Medium) },
          { name: "High", color: "#2ecc71", count: asNumber(summary.High) }
        ];
        const total = entries.reduce((sum, item) => sum + item.count, 0);
        const materials = Array.isArray(meta.materials)
          ? meta.materials
              .map((entry) => {
                const payload = entry && typeof entry === "object" ? entry : {};
                const name = typeof payload.name === "string" ? payload.name.trim() : "";
                const count = Math.max(0, Math.floor(asNumber(payload.count)));
                return { name, count };
              })
              .filter((entry) => !!entry.name && entry.count > 0)
              .sort((left, right) => {
                if (right.count !== left.count) {
                  return right.count - left.count;
                }
                return left.name.localeCompare(right.name);
              })
          : [];

        if (total <= 0 && !materials.length) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "No material summary found in this session.";
          chartContentMix.appendChild(note);
          return;
        }

        const wrapper = document.createElement("div");
        wrapper.className = "mix-layout";

        if (total > 0) {
          const bar = document.createElement("div");
          bar.className = "mix-bar";
          bar.title = `Total prospected asteroids: ${total.toLocaleString()}`;

          entries.forEach((entry) => {
            if (entry.count <= 0) {
              return;
            }
            const ratio = entry.count / total;
            const segment = document.createElement("div");
            segment.className = "mix-segment";
            segment.style.width = `${Math.max(1.5, ratio * 100)}%`;
            segment.style.background = entry.color;
            segment.title = `${entry.name}: ${entry.count.toLocaleString()} (${(ratio * 100).toFixed(1)}%)`;
            bar.appendChild(segment);
          });

          wrapper.appendChild(bar);
        } else {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.style.margin = "0";
          note.textContent = "No High/Medium/Low content summary in this session.";
          wrapper.appendChild(note);
        }

        const legend = document.createElement("div");
        legend.className = "mix-legend";

        entries.forEach((entry) => {
          const ratio = total > 0 ? (entry.count / total) * 100 : 0;
          const row = document.createElement("div");
          row.className = "mix-item";

          const left = document.createElement("span");
          left.className = "left";

          const dot = document.createElement("span");
          dot.className = "mix-dot";
          dot.style.background = entry.color;

          const label = document.createElement("span");
          label.textContent = `${entry.name} (${ratio.toFixed(1)}%)`;

          left.appendChild(dot);
          left.appendChild(label);

          const count = document.createElement("span");
          count.className = "mix-count";
          count.textContent = entry.count.toLocaleString();

          row.appendChild(left);
          row.appendChild(count);
          legend.appendChild(row);
        });
        wrapper.appendChild(legend);

        const matsWrap = document.createElement("div");
        matsWrap.className = "mix-mats";
        const matsTitle = document.createElement("p");
        matsTitle.className = "mix-mats-title";
        matsTitle.textContent = "Collected Materials";
        matsWrap.appendChild(matsTitle);

        if (!materials.length) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.style.margin = "0";
          note.textContent = "No engineering materials were recorded.";
          matsWrap.appendChild(note);
        } else {
          const matsList = document.createElement("div");
          matsList.className = "mix-mats-list";
          materials.forEach((entry) => {
            const item = document.createElement("span");
            item.className = "mix-mat";
            const name = document.createElement("span");
            name.textContent = entry.name;
            const qty = document.createElement("span");
            qty.className = "mix-mat-qty";
            qty.textContent = `x${entry.count}`;
            item.appendChild(name);
            item.appendChild(qty);
            matsList.appendChild(item);
          });
          matsWrap.appendChild(matsList);
        }
        wrapper.appendChild(matsWrap);

        chartContentMix.appendChild(wrapper);
      }

      function collectRefinedCommodityKeys(events) {
        const keys = new Set();
        if (!Array.isArray(events)) {
          return keys;
        }
        events.forEach((event) => {
          if (!event || event.type !== "mining_refined") {
            return;
          }
          const details = event.details && typeof event.details === "object" ? event.details : {};
          const localized = typeof details.type_localised === "string" ? details.type_localised.trim() : "";
          const rawType = typeof details.type === "string" ? details.type.trim() : "";
          const display = localized || rawType
            .replace(/^\$/, "")
            .replace(/;$/, "")
            .replace(/_name$/i, "")
            .replace(/_/g, " ");
          const key = normalizeCommodityKey(display) || normalizeTextKey(display);
          if (key) {
            keys.add(key);
          }
        });
        return keys;
      }

      function buildMaterialPercentAmountModel(sessionData, showOnlyCollected, includeDuplicates) {
        return buildMaterialPercentAmountModelExtracted({
          sessionData,
          showOnlyCollected,
          includeDuplicates,
          collectRefinedCommodityKeys,
          normalizeCommodityKey,
          normalizeTextKey,
        });
      }

      function renderMaterialPercentAmount(sessionData, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        const model = buildMaterialPercentAmountModel(
          sessionData,
          renderState.materialPercentShowOnlyCollected,
          renderState.prospectFrequencyIncludeDuplicates
        );
        const renderResult = renderMaterialPercentAmountChart({
          chartMaterialPercentAmount,
          materialPercentCard,
          model,
          materialPercentShowOnlyCollected: renderState.materialPercentShowOnlyCollected,
          materialPercentShowGridlines: renderState.materialPercentShowGridlines,
          activeThemeId: renderState.activeThemeId,
          commodityAbbreviationMap,
          selectedHistogramCommodity: renderState.selectedHistogramCommodity,
          materialPercentHighlightedCommodityKey: renderState.materialPercentHighlightedCommodityKey,
          normalizeCommodityKey,
          asNumber,
          formatNumber,
          showCursorTooltip,
          hideCursorTooltip,
          highlightFromMaterialPercentDotEntry,
          clearCrossChartHoverHighlights,
          applyMaterialPercentCommoditySelection,
        });
        materialPercentHoverContext = renderResult && renderResult.hoverContext
          ? renderResult.hoverContext
          : {
              commodityKey: "",
              dots: []
            };
      }

      function applyAdaptiveBinLabels(labelsContainer, labelTexts, minGapPx) {
        return applyAdaptiveBinLabelsShared(labelsContainer, labelTexts, minGapPx);
      }

      function shouldReverseProspectHistogram(stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        return !!renderState.prospectFrequencyReverseCumulative;
      }

      function buildProspectHistogramModel(sessionData, includeDuplicates, showOnlyCollected, histogramBinSizeOverride, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        return buildProspectHistogramModelExtracted({
          sessionData,
          includeDuplicates,
          showOnlyCollected,
          histogramBinSizeOverride,
          selectedYieldPopulationMode: renderState.selectedYieldPopulationMode,
          runtimeAnalysisSettings: renderState.runtimeAnalysisSettings,
          collectRefinedCommodityKeys,
          normalizeCommodityKey,
          normalizeTextKey,
        });
      }

      function normalizeTextKey(value) {
        return normalizeTextKeyShared(value);
      }

      function normalizeCommodityKey(value) {
        return normalizeCommodityKeyShared(value);
      }

      async function loadProspectedAsteroidSummaryRecords() {
        if (Array.isArray(prospectSummaryRecords)) {
          return prospectSummaryRecords;
        }
        if (prospectSummaryLoadPromise) {
          return prospectSummaryLoadPromise;
        }
        prospectSummaryLoadPromise = (async () => {
          try {
            const result = await fetchProspectedAsteroidSummary();
            if (!result.ok) {
              prospectSummaryRecords = [];
              return prospectSummaryRecords;
            }
            const parsed = parseProspectedAsteroidSummaryText(result.text);
            prospectSummaryRecords = parsed;
            return prospectSummaryRecords;
          } catch (_error) {
            prospectSummaryRecords = [];
            return prospectSummaryRecords;
          } finally {
            prospectSummaryLoadPromise = null;
          }
        })();
        return prospectSummaryLoadPromise;
      }

      function buildSmoothLinePath(points) {
        return buildSmoothLinePathShared(points);
      }

      function buildProspectCumulativeFrequencyModel(sessionData, filename, summaryRecords, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        return buildProspectCumulativeFrequencyModelExtracted({
          sessionData,
          filename,
          summaryRecords,
          selectedHistogramCommodity: renderState.selectedHistogramCommodity,
          prospectFrequencyIncludeDuplicates: renderState.prospectFrequencyIncludeDuplicates,
          prospectFrequencyReverseCumulative: renderState.prospectFrequencyReverseCumulative,
          prospectFrequencyBinSize: renderState.prospectFrequencyBinSize,
          selectedYieldPopulationMode: renderState.selectedYieldPopulationMode,
          normalizeCommodityKey,
          normalizeTextKey,
        });
      }

      async function renderProspectCumulativeFrequency(sessionData, filename, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        const renderToken = ++prospectFrequencyRenderToken;
        chartProspectCumulativeFrequency.innerHTML = "";
        clearCrossChartHoverHighlights();
        cumulativeHoverContext = {
          commodityKey: "",
          points: [],
          showLinkedCrosshair: null,
          hideLinkedCrosshair: null
        };
        renderProspectFrequencyTitle(sessionData, renderState);
        if (prospectFrequencyHeaderControls) {
          prospectFrequencyHeaderControls.innerHTML = "";
        }

        if (prospectFrequencyHeaderControls) {
          const compareButton = document.createElement("button");
          compareButton.type = "button";
          compareButton.className = "panel-action-button";
          compareButton.textContent = "Compare";
          compareButton.addEventListener("click", () => openCompareRingsPage(renderState));
          prospectFrequencyHeaderControls.appendChild(compareButton);
        }

        const summaryRecords = await loadProspectedAsteroidSummaryRecords();
        if (renderToken !== prospectFrequencyRenderToken) {
          return;
        }

        const model = buildProspectCumulativeFrequencyModel(sessionData, filename, summaryRecords, renderState);
        if (!model || model.error) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = model && model.error ? model.error : "Cumulative frequency data unavailable.";
          chartProspectCumulativeFrequency.appendChild(note);
          return;
        }
        cumulativeHoverContext = renderProspectCumulativeFrequencyChart({
          chartProspectCumulativeFrequency,
          model,
          prospectFrequencyReverseCumulative: renderState.prospectFrequencyReverseCumulative,
          prospectFrequencyShowAverageReference: renderState.prospectFrequencyShowAverageReference,
          materialPercentShowGridlines: renderState.materialPercentShowGridlines,
          applyAdaptiveBinLabels,
          buildSmoothLinePath,
          formatNumber,
          showCursorTooltip,
          hideCursorTooltip,
          clearCrossChartHoverHighlights,
          highlightFromCumulativePointEntry,
          normalizeCommodityKey,
          onAverageReferenceChange: (checked) => {
            indexStateController.setProspectFrequencyShowAverageReference(checked);
            schedulePersistIndexReportSettings();
            const nextState = getIndexRenderState();
            if (nextState.activeSessionData) {
              void renderProspectCumulativeFrequency(nextState.activeSessionData, nextState.activeSessionFilename, nextState);
            }
          }
        });
      }

      function renderProspectHistogram(sessionData, stateSnapshot) {
        const initialRenderState = stateSnapshot || getIndexRenderState();
        chartProspectHistogram.innerHTML = "";
        clearCrossChartHoverHighlights();
        histogramHoverContext = {
          commodityKey: "",
          binSize: 10,
          bars: []
        };
        if (prospectHistogramHeaderControls) {
          prospectHistogramHeaderControls.innerHTML = "";
        }
        if (commodityHistogramFilters) {
          commodityHistogramFilters.innerHTML = "";
        }
        const model = buildProspectHistogramModel(
          sessionData,
          initialRenderState.prospectFrequencyIncludeDuplicates,
          initialRenderState.materialPercentShowOnlyCollected || initialRenderState.histogramShowOnlyCollected,
          initialRenderState.prospectFrequencyBinSize,
          initialRenderState
        );
        if (!model || !Array.isArray(model.commodities) || !model.commodities.length) {
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "No prospect percentage breakdown data in this session.";
          chartProspectHistogram.appendChild(note);
          if (commodityHistogramFilters) {
            const filterNote = document.createElement("span");
            filterNote.className = "chart-empty";
            filterNote.textContent = "No commodity options available.";
            commodityHistogramFilters.appendChild(filterNote);
          }
          if (initialRenderState.activeSessionData) {
            void renderProspectCumulativeFrequency(
              initialRenderState.activeSessionData,
              initialRenderState.activeSessionFilename,
              initialRenderState
            );
          }
          return;
        }
        const buildRefinedTonsByCommodity = (payload) => {
          const source = payload && typeof payload === "object" && payload.commodities && typeof payload.commodities === "object"
            ? payload.commodities
            : {};
          const totals = new Map();
          Object.entries(source).forEach(([name, details]) => {
            const commodityKey = normalizeCommodityKey(name) || normalizeTextKey(name) || String(name || "").trim().toLowerCase();
            if (!commodityKey) {
              return;
            }
            const gathered = details && typeof details === "object" && details.gathered && typeof details.gathered === "object"
              ? details.gathered
              : {};
            const tons = Number(gathered.tons);
            if (!Number.isFinite(tons) || tons <= 0) {
              return;
            }
            totals.set(commodityKey, (totals.get(commodityKey) || 0) + tons);
          });
          return totals;
        };
        const refinedTonsByCommodity = buildRefinedTonsByCommodity(sessionData);
        const commodities = [...model.commodities];
        commodities.sort((left, right) => {
          const leftKey = normalizeCommodityKey(left && left.name);
          const rightKey = normalizeCommodityKey(right && right.name);
          const leftRefined = Number(refinedTonsByCommodity.get(leftKey) || 0);
          const rightRefined = Number(refinedTonsByCommodity.get(rightKey) || 0);
          if (rightRefined !== leftRefined) {
            return rightRefined - leftRefined;
          }
          const leftPresent = Number.isFinite(Number(left && left.presentTotal)) ? Number(left.presentTotal) : Number(left && left.total);
          const rightPresent = Number.isFinite(Number(right && right.presentTotal)) ? Number(right.presentTotal) : Number(right && right.total);
          if (rightPresent !== leftPresent) {
            return rightPresent - leftPresent;
          }
          const leftTotal = Number(left && left.total);
          const rightTotal = Number(right && right.total);
          if (rightTotal !== leftTotal) {
            return rightTotal - leftTotal;
          }
          return String(left && left.name || "").localeCompare(String(right && right.name || ""));
        });
        const binSize = model.binSize;
        let selectedCommodity = initialRenderState.selectedHistogramCommodity;
        const highlightedCommodityKey = initialRenderState.materialPercentHighlightedCommodityKey;
        const wasSelectionClearedByMaterial = initialRenderState.histogramSelectionClearedByMaterial;
        if (!selectedCommodity && highlightedCommodityKey) {
          const byKey = commodities.find(
            (item) => normalizeCommodityKey(item.name) === highlightedCommodityKey
          );
          if (byKey) {
            indexStateController.setSelectedHistogramCommodity(byKey.name);
            selectedCommodity = byKey.name;
          }
        }

        if (
          !wasSelectionClearedByMaterial
          && !commodities.some((item) => item.name === selectedCommodity)
        ) {
          indexStateController.setSelectedHistogramCommodity(commodities[0].name);
          selectedCommodity = commodities[0].name;
        }

        const renderSelected = (renderState) => {
          const nextRenderState = renderState || getIndexRenderState();
          const reverseHistogram = shouldReverseProspectHistogram(nextRenderState);
          histogramHoverContext = renderProspectHistogramSelection({
            chartProspectHistogram,
            commodities,
            binSize,
            selectedHistogramCommodity: nextRenderState.selectedHistogramCommodity,
            reverseHistogram,
            applyAdaptiveBinLabels,
            normalizeCommodityKey,
            asNumber,
            showCursorTooltip,
            hideCursorTooltip,
            highlightFromHistogramBarEntry,
            clearCrossChartHoverHighlights,
          });
          if (nextRenderState.activeSessionData) {
            void renderProspectCumulativeFrequency(
              nextRenderState.activeSessionData,
              nextRenderState.activeSessionFilename,
              nextRenderState
            );
          }
        };

        if (commodityHistogramFilters) {
          commodities.forEach((item, index) => {
            const wrapper = document.createElement("label");
            wrapper.className = "event-filter-item";
            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = "commodity-histogram";
            radio.id = `commodity-histogram-${index}`;
            radio.checked = !!selectedCommodity && item.name === selectedCommodity;
            radio.addEventListener("change", () => {
              if (!radio.checked) {
                return;
              }
              indexStateController.setHistogramCommoditySelectionWithHighlight(
                item.name,
                item.name,
                normalizeCommodityKey
              );
              const nextRenderState = getIndexRenderState();
              renderSelected(nextRenderState);
              if (nextRenderState.activeSessionData) {
                renderMaterialPercentAmount(nextRenderState.activeSessionData, nextRenderState);
              }
            });

            const text = document.createElement("span");
            const collectedCount = Number.isFinite(Number(item.presentTotal))
              ? Number(item.presentTotal)
              : Number(item.total);
            text.textContent = `${item.name} (${collectedCount})`;

            wrapper.appendChild(radio);
            wrapper.appendChild(text);
            commodityHistogramFilters.appendChild(wrapper);
          });
        }

        renderSelected(getIndexRenderState());
      }

      function buildCumulativeCommoditySeries(sessionData) {
        return buildCumulativeCommoditySeriesExtracted({
          sessionData,
          normalizeCommodityName,
          normalizeCommodityKey,
          asNumber,
        });
      }

      function renderCumulativeCommodities(sessionData, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        const model = buildCumulativeCommoditySeries(sessionData);
        renderCumulativeCommoditiesChart({
          chartCumulativeCommodities,
          cumulativeHeaderControls,
          model,
          activeThemeId: renderState.activeThemeId,
          getSelection: () => cumulativeCommoditySelection,
          setSelection: (selection) => {
            cumulativeCommoditySelection = selection;
          },
          getRenderMode: () => cumulativeRenderMode,
          setRenderMode: (mode) => {
            cumulativeRenderMode = mode;
            schedulePersistIndexReportSettings();
          },
          getValueMode: () => cumulativeValueMode,
          setValueMode: (mode) => {
            cumulativeValueMode = mode;
            schedulePersistIndexReportSettings();
          },
          asNumber,
          formatNumber,
          formatLocalDateTime,
          formatLocalClock,
          showCursorTooltip,
          hideCursorTooltip,
        });
      }

      function normalizeTimelinePoints(points) {
        return normalizeTimelinePointsExtracted(points);
      }

      function buildTimelineBins(validPoints, options) {
        return buildTimelineBinsExtracted(validPoints, options);
      }

      function computeTimelinePeak(points, options) {
        return computeTimelinePeakExtracted(points, options);
      }

      function formatEventTypeLabel(value) {
        const text = String(value || "").trim();
        if (!text) {
          return "Unknown";
        }
        return text
          .replace(/_/g, " ")
          .replace(/\b\w/g, (char) => char.toUpperCase());
      }

      const eventJournalController = createEventJournalController({
        eventJournal,
        formatLocalDateTime,
        formatEventTypeLabel,
      });

      function renderFilteredEventTimeline() {
        if (!eventTimelineOptions) {
          return;
        }
        const selectedTypes = new Set(
          Object.keys(eventTypeSelection).filter((eventType) => eventTypeSelection[eventType])
        );
        if (!selectedTypes.size) {
          chartEvents.innerHTML = "";
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "No event types selected.";
          chartEvents.appendChild(note);
          eventJournalController.reset({ clearJournal: true });
          return;
        }
        const filteredEntries = allEventEntries.filter((entry) => selectedTypes.has(entry.label));
        const sortedEntries = [...filteredEntries].sort((left, right) => {
          const leftMs = Date.parse(left && left.timestamp ? left.timestamp : "");
          const rightMs = Date.parse(right && right.timestamp ? right.timestamp : "");
          if (!Number.isFinite(leftMs) && !Number.isFinite(rightMs)) {
            return 0;
          }
          if (!Number.isFinite(leftMs)) {
            return 1;
          }
          if (!Number.isFinite(rightMs)) {
            return -1;
          }
          return leftMs - rightMs;
        });
        const filteredPoints = sortedEntries.map((entry) => ({
          timestamp: entry.timestamp,
          label: entry.label
        }));
        const eventTimelineContext = renderTimelineChart(chartEvents, filteredPoints, eventTimelineOptions);
        eventJournalController.render({
          entries: sortedEntries,
          timelineContext: eventTimelineContext,
        });
      }

      function setupEventTypeFilters(eventEntries, options) {
        allEventEntries = Array.isArray(eventEntries) ? eventEntries : [];
        eventTimelineOptions = options || null;
        eventTypeSelection = {};
        if (!eventFilters) {
          renderFilteredEventTimeline();
          return;
        }
        wireTimelineCheckboxFilters({
          container: eventFilters,
          entries: allEventEntries,
          getLabel: (entry) => (entry && typeof entry.label === "string" ? entry.label : ""),
          selection: eventTypeSelection,
          emptyMessage: "No event filters available.",
          allCheckboxId: "event-filter-all",
          itemCheckboxIdPrefix: "event-filter",
          formatLabel: formatEventTypeLabel,
          onSelectionChange: renderFilteredEventTimeline,
        });
      }

      function renderFilteredRefinementTimeline() {
        if (!refinementTimelineOptions) {
          return;
        }
        const selectedCommodities = new Set(
          Object.keys(refinementSelection).filter((commodity) => refinementSelection[commodity])
        );
        if (!selectedCommodities.size) {
          chartRefinements.innerHTML = "";
          const note = document.createElement("p");
          note.className = "chart-empty";
          note.textContent = "No commodities selected.";
          chartRefinements.appendChild(note);
          return;
        }
        const filteredPoints = allRefinementEntries.filter((entry) => selectedCommodities.has(entry.label));
        renderTimelineChart(chartRefinements, filteredPoints, refinementTimelineOptions);
      }

      function setupRefinementCommodityFilters(refinementEntries, options) {
        allRefinementEntries = Array.isArray(refinementEntries) ? refinementEntries : [];
        refinementTimelineOptions = options || null;
        refinementSelection = {};
        if (!refinementFilters) {
          renderFilteredRefinementTimeline();
          return;
        }
        wireTimelineCheckboxFilters({
          container: refinementFilters,
          entries: allRefinementEntries,
          getLabel: (entry) => (entry && typeof entry.label === "string" ? entry.label : ""),
          selection: refinementSelection,
          emptyMessage: "No refinement commodity filters available.",
          allCheckboxId: "refinement-filter-all",
          itemCheckboxIdPrefix: "refinement-filter",
          onSelectionChange: renderFilteredRefinementTimeline,
        });
      }

      function renderTimelineChart(container, points, options) {
        return renderTimelineChartExtracted({
          container,
          points,
          chartOptions: options,
          formatLocalClock,
          showCursorTooltip,
          hideCursorTooltip,
        });
      }

      function renderCharts(sessionData, stateSnapshot) {
        const renderState = stateSnapshot || getIndexRenderState();
        resetCrossChartHoverContexts();
        const rows = buildCommodityRows(sessionData).sort((a, b) => b.tons - a.tons);
        const useCoolThroughputFill = renderState.activeThemeId !== "orange-dark";
        renderBarChart(chartCommodityTons, rows, (row) => row.tons, (value) => `${formatNumber(value, 0)} t`, false);
        renderBarChart(
          chartCommodityTph,
          [...rows].sort((a, b) => b.tph - a.tph),
          (row) => row.tph,
          (value) => `${formatNumber(value, 1)} TPH`,
          useCoolThroughputFill
        );
        renderContentMix(sessionData);
        renderProspectHistogram(sessionData, renderState);
        const postHistogramRenderState = getIndexRenderState();
        renderMaterialPercentAmount(sessionData, postHistogramRenderState);
        renderCumulativeCommodities(sessionData, postHistogramRenderState);
        renderEstimatedProfitDetails(sessionData, postHistogramRenderState);

        const meta = sessionData && typeof sessionData === "object" ? (sessionData.meta || {}) : {};
        const startMs = Date.parse(meta.start_time || "");
        const endMs = Date.parse(meta.end_time || "");
        const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
        const eventEntries = events
          .map((event) => {
            if (!event || typeof event !== "object") {
              return null;
            }
            const timestamp = event.timestamp;
            if (typeof timestamp !== "string") {
              return null;
            }
            const eventType = typeof event.type === "string" && event.type.trim()
              ? event.type.trim()
              : "unknown";
            const details = event.details && typeof event.details === "object" ? event.details : {};
            return { timestamp, label: eventType, details };
          })
          .filter((entry) => !!entry);
        setupEventTypeFilters(eventEntries, {
          startMs,
          endMs,
          bins: 24,
          cool: false,
          countLabel: "Events"
        });

        const refinementPoints = events
          .filter((event) => event && event.type === "mining_refined")
          .map((event) => {
            const timestamp = typeof event.timestamp === "string" ? event.timestamp : null;
            if (!timestamp) {
              return null;
            }
            const details = event.details && typeof event.details === "object" ? event.details : {};
            const typeLocalised = typeof details.type_localised === "string" ? details.type_localised.trim() : "";
            const typeName = typeof details.type === "string" ? details.type.trim() : "";
            const label = typeLocalised || typeName || "refined";
            return { timestamp, label };
          })
          .filter((point) => !!point);
        setupRefinementCommodityFilters(refinementPoints, {
          startMs,
          endMs,
          bins: 24,
          cool: true,
          countLabel: "Refinements"
        });

        return {
          maxRpm: computeTimelinePeak(refinementPoints, {
            startMs,
            endMs,
            bins: 24
          })
        };
      }

      function normalizeCommodityName(value) {
        if (typeof value !== "string") {
          return "";
        }
        return value.trim().toLowerCase();
      }

      function computeIgnoredProspectedCommodities(sessionData) {
        const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
        const prospectedCommodities = new Set();
        for (const event of events) {
          if (!event || event.type !== "prospected_asteroid") {
            continue;
          }
          const details = event.details && typeof event.details === "object" ? event.details : {};
          const materials = Array.isArray(details.materials) ? details.materials : [];
          for (const material of materials) {
            const name = normalizeCommodityName(material && material.name);
            if (name) {
              prospectedCommodities.add(name);
            }
          }
        }

        const refinedCommodities = new Set();
        events.forEach((event) => {
          if (!event || event.type !== "mining_refined") {
            return;
          }
          const details = event.details && typeof event.details === "object" ? event.details : {};
          const localized = normalizeCommodityName(details.type_localised);
          if (localized) {
            refinedCommodities.add(localized);
            return;
          }

          const rawType = typeof details.type === "string" ? details.type.trim() : "";
          if (!rawType) {
            return;
          }
          const cleaned = normalizeCommodityName(
            rawType
              .replace(/^\$/, "")
              .replace(/;$/, "")
              .replace(/_name$/i, "")
              .replace(/_/g, " ")
          );
          if (cleaned) {
            refinedCommodities.add(cleaned);
          }
        });

        let ignoredCount = 0;
        prospectedCommodities.forEach((name) => {
          if (!refinedCommodities.has(name)) {
            ignoredCount += 1;
          }
        });
        return ignoredCount;
      }

      function computeLimpetDumpCount(sessionData, threshold) {
        const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
        const dumpThresholdRaw = Number(threshold);
        const dumpThreshold = Number.isFinite(dumpThresholdRaw) ? Math.max(0, Math.floor(dumpThresholdRaw)) : 5;
        const readCargoLimpetCount = (details, inventory) => {
          const directLimpets = Number(details && details.limpets);
          if (Number.isFinite(directLimpets) && directLimpets >= 0) {
            return directLimpets;
          }
          const source = inventory && typeof inventory === "object" ? inventory : {};
          const inventoryLimpets = Number(
            source.Limpets ?? source.limpets ?? source.Drones ?? source.drones
          );
          if (Number.isFinite(inventoryLimpets) && inventoryLimpets >= 0) {
            return inventoryLimpets;
          }
          return null;
        };
        const cargoLimpetPoints = events
          .map((event, index) => {
            if (!event || event.type !== "cargo") {
              return null;
            }
            const details = event.details && typeof event.details === "object" ? event.details : {};
            const inventory = details.inventory;
            if (!inventory || typeof inventory !== "object" || Array.isArray(inventory)) {
              return null;
            }
            const limpetCount = readCargoLimpetCount(details, inventory);
            if (!Number.isFinite(limpetCount)) {
              return null;
            }
            const ms = Date.parse(typeof event.timestamp === "string" ? event.timestamp : "");
            return { ms, index, limpetCount };
          })
          .filter((point) => !!point)
          .sort((left, right) => {
            const leftValid = Number.isFinite(left.ms);
            const rightValid = Number.isFinite(right.ms);
            if (leftValid && rightValid && left.ms !== right.ms) {
              return left.ms - right.ms;
            }
            if (leftValid && !rightValid) {
              return -1;
            }
            if (!leftValid && rightValid) {
              return 1;
            }
            return left.index - right.index;
          });

        let dumps = 0;
        for (let i = 1; i < cargoLimpetPoints.length; i += 1) {
          const previous = cargoLimpetPoints[i - 1].limpetCount;
          const current = cargoLimpetPoints[i].limpetCount;
          if ((previous - current) > dumpThreshold) {
            dumps += 1;
          }
        }
        return dumps;
      }

      function computeHighestRefinedYieldCommodity(sessionData) {
        const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
        const refinedCommodityNames = new Set();
        events.forEach((event) => {
          if (!event || event.type !== "mining_refined") {
            return;
          }
          const details = event.details && typeof event.details === "object" ? event.details : {};
          const localized = typeof details.type_localised === "string" ? details.type_localised.trim() : "";
          if (localized) {
            refinedCommodityNames.add(normalizeCommodityName(localized));
          }
        });

        const candidates = [];
        events.forEach((event) => {
          if (!event || event.type !== "prospected_asteroid") {
            return;
          }
          const details = event.details && typeof event.details === "object" ? event.details : {};
          const materials = Array.isArray(details.materials) ? details.materials : [];
          materials.forEach((material) => {
            if (!material || typeof material !== "object") {
              return;
            }
            const name = typeof material.name === "string" ? material.name.trim() : "";
            const percent = Number(material.percentage);
            if (!name || !Number.isFinite(percent)) {
              return;
            }
            const normalized = normalizeCommodityName(name);
            const isRefined = refinedCommodityNames.size === 0 || refinedCommodityNames.has(normalized);
            candidates.push({
              name,
              percent,
              isRefined
            });
          });
        });

        const filtered = candidates.filter((item) => item.isRefined);
        const pool = filtered.length ? filtered : candidates;
        if (!pool.length) {
          return "--";
        }

        pool.sort((left, right) => {
          if (right.percent !== left.percent) {
            return right.percent - left.percent;
          }
          return left.name.localeCompare(right.name);
        });
        const top = pool[0];
        return `${top.name} (${top.percent.toFixed(2)}%)`;
      }

      function buildSummary(sessionData, filename, overrides) {
        const meta = sessionData && typeof sessionData === "object" ? (sessionData.meta || {}) : {};
        const overall = meta.overall_tph || {};
        const location = meta.location || {};
        const resolvedRingLabel = String(resolveSessionRingLabel(sessionData) || "").trim();
        const bodyRingLabel = (
          resolvedRingLabel && resolvedRingLabel !== "Unknown"
            ? resolvedRingLabel
            : (location.ring || location.body || "--")
        );
        const prospected = meta.prospected || {};
        const estimatedSell = meta.estimated_sell || {};
        const commodities = sessionData && sessionData.commodities ? Object.keys(sessionData.commodities).length : 0;
        const commoditiesIgnored = computeIgnoredProspectedCommodities(sessionData);
        const highestRefinedYield = computeHighestRefinedYieldCommodity(sessionData);
        const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
        const limpetDumpThresholdRaw = Number(meta.limpet_dump_threshold);
        const limpetDumpThreshold = Number.isFinite(limpetDumpThresholdRaw)
          ? Math.max(0, Math.floor(limpetDumpThresholdRaw))
          : 5;
        const limpetDumps = computeLimpetDumpCount(sessionData, limpetDumpThreshold);
        const totalEstProfitRaw = computeEstimatedSellTotalValue(sessionData, estimatedSell);
        const totalEstProfit = Number.isFinite(totalEstProfitRaw)
          ? `${Math.round(totalEstProfitRaw).toLocaleString()} CR`
          : "--";
        const prospectedTotalRaw = Number(prospected.total);
        const prospectedEventCount = events.reduce((count, event) => (
          event && event.type === "prospected_asteroid" ? count + 1 : count
        ), 0);
        const asteroidCount = Number.isFinite(prospectedTotalRaw) && prospectedTotalRaw >= 0
          ? formatNumber(Math.floor(prospectedTotalRaw), 0)
          : (prospectedEventCount > 0 ? formatNumber(prospectedEventCount, 0) : "--");
        const tonsValue = Number(overall.tons);
        const durationSeconds = Number(meta.duration_seconds);
        const roundedDurationHours = Number.isFinite(durationSeconds) && durationSeconds >= 0
          ? Number((durationSeconds / 3600.0).toFixed(2))
          : null;
        const durationDisplay = formatDurationWithHours(durationSeconds);
        const tonsPerHour = (
          Number.isFinite(tonsValue)
          && tonsValue >= 0
          && Number.isFinite(roundedDurationHours)
          && roundedDurationHours > 0
        )
          ? (tonsValue / roundedDurationHours).toFixed(2)
          : (overall.tons_per_hour ?? "--");
        const inventoryTonnage = Number(meta.inventory_tonnage);
        const cargoCapacity = Number(meta.cargo_capacity);
        const cargoPercentFull = (
          Number.isFinite(inventoryTonnage)
          && Number.isFinite(cargoCapacity)
          && cargoCapacity > 0
        )
          ? `${formatNumber((Math.max(0, inventoryTonnage) / cargoCapacity) * 100, 0)}%`
          : "--";
        const cargoDisplay = (
          Number.isFinite(inventoryTonnage)
          && Number.isFinite(cargoCapacity)
          && cargoCapacity >= 0
        )
          ? `${formatNumber(Math.max(0, inventoryTonnage), 0)}/${formatNumber(cargoCapacity, 0)} (${cargoPercentFull})`
          : "--";

        return [
          ["File", filename],
          ["Start", formatLocalDateTime(meta.start_time)],
          ["End", formatLocalDateTime(meta.end_time)],
          ["Ship", meta.ship || "--"],
          ["System", location.system || "--"],
          ["Body/Ring", bodyRingLabel],
          ["Tons Collected", overall.tons ?? "--"],
          ["Duration (Hours)", durationDisplay],
          ["Tons/Hour", tonsPerHour],
          ["Cargo", cargoDisplay],
          ["Total Est. Profit", totalEstProfit],
          ["Asteroids Prospected", asteroidCount],
          ["Prospectors Launched", meta.prospectors_launched ?? "--"],
          ["Prospected", prospected.total ?? "--"],
          ["Duplicate Prospectors", prospected.duplicates ?? "--"],
          ["Prospectors Lost", meta.prospectors_lost ?? "--"],
          ["Collectors Launched", meta.collectors_launched ?? "--"],
          ["Collectors Abandoned", meta.collectors_abandoned ?? "--"],
          [
            "Limpet Dumps",
            limpetDumps,
            `More than ${limpetDumpThreshold} limpets dumped from inventory between Cargo events`
          ],
          ["Commodity Types", commodities],
          ["Commodities Ignored", commoditiesIgnored],
          ["Highest Yield (Refined)", highestRefinedYield]
        ];
      }

      async function loadSession(filename) {
        if (!filename) {
          setStatus(analysisStatus, "No session selected.", "warn");
          analysisMetrics.innerHTML = "";
          clearCharts("No session selected.");
          return;
        }

        setStatus(analysisStatus, `Loading ${filename}...`);
        try {
          await Promise.all([
            refreshAnalysisSettings(),
            ensureCommodityLinkMap()
          ]);
          const result = await fetchSessionFile(filename);
          if (!result.ok) {
            throw new Error(`HTTP ${result.status}`);
          }
          const payload = result.data;
          indexStateController.setActiveSession(payload, filename);
          const renderState = getIndexRenderState();
          const chartStats = renderCharts(payload, renderState);
          renderMetrics(buildSummary(payload, filename, chartStats));
          setStatus(analysisStatus, "", "");
        } catch (error) {
          indexStateController.clearActiveSession();
          analysisMetrics.innerHTML = "";
          clearCharts("Unable to render charts because session load failed.");
          setStatus(
            analysisStatus,
            `Failed to load ${filename}: ${error && error.message ? error.message : "Unknown error"}`,
            "bad"
          );
        }
      }

      async function loadSessionList() {
        const listToken = ++sessionListRenderToken;
        setStatus(sessionStatus, "Loading available sessions...");
        try {
          const result = await fetchSessionDirectoryListing();
          if (!result.ok) {
            throw new Error(`HTTP ${result.status}`);
          }

          const listing = result.text;
          const doc = new DOMParser().parseFromString(listing, "text/html");
          const files = Array.from(doc.querySelectorAll("a[href]"))
            .map((link) => pickFilename(link.getAttribute("href")))
            .filter((name) => !!name);

          const unique = Array.from(new Set(files));
          unique.sort((left, right) => {
            const leftStamp = Number((/^session_data_(\d+)\.json$/.exec(left) || [])[1] || 0);
            const rightStamp = Number((/^session_data_(\d+)\.json$/.exec(right) || [])[1] || 0);
            return rightStamp - leftStamp;
          });

          sessionSelect.innerHTML = "";
          if (unique.length === 0) {
            const option = document.createElement("option");
            option.textContent = "No saved sessions found";
            sessionSelect.appendChild(option);
            sessionSelect.disabled = true;
            setStatus(sessionStatus, "No session_data JSON files found yet.", "warn");
            setStatus(analysisStatus, "Record and save a session first, then reopen analysis.", "warn");
            analysisMetrics.innerHTML = "";
            clearCharts("No saved sessions available.");
            return;
          }

          for (const file of unique) {
            const option = document.createElement("option");
            option.value = file;
            option.textContent = formatSessionOptionLabel(file, "", null);
            sessionSelect.appendChild(option);
            void (async () => {
              const details = await fetchSessionOptionDetails(file);
              if (listToken !== sessionListRenderToken) {
                return;
              }
              option.textContent = formatSessionOptionLabel(
                file,
                details.ringLabel,
                details.asteroidCount,
                details.commodityLabel
              );
            })();
          }

          sessionSelect.disabled = false;
          setStatus(sessionStatus, `Found ${unique.length} saved sessions.`, "ok");
          await loadSession(unique[0]);
        } catch (error) {
          sessionSelect.innerHTML = "";
          const option = document.createElement("option");
          option.textContent = "Unable to load session list";
          sessionSelect.appendChild(option);
          sessionSelect.disabled = true;
          setStatus(
            sessionStatus,
            `Failed to read session list: ${error && error.message ? error.message : "Unknown error"}`,
            "bad"
          );
          setStatus(analysisStatus, "Session analysis is unavailable until session files can be read.", "bad");
          analysisMetrics.innerHTML = "";
          clearCharts("Session list unavailable.");
        }
      }

      sessionSelect.addEventListener("change", function (event) {
        const target = event.target;
        const selected = target && typeof target.value === "string" ? target.value : "";
        void loadSession(selected);
      });

      const initialRenderState = getIndexRenderState();

      wireDisplaySettingsControls({
        materialPercentShowCollectedInput,
        materialPercentShowGridlinesInput,
        materialPercentIncludeDuplicatesInput,
        materialPercentIntervalInputs,
        materialPercentReverseCumulativeInput,
        materialPercentYieldPopulationInputs,
        initialState: initialRenderState,
        onCollectedModeToggle: (checked) => {
          indexStateController.setMaterialPercentCollectedMode(checked);
          schedulePersistIndexReportSettings();
          const renderState = getIndexRenderState();
          if (renderState.activeSessionData) {
            renderProspectHistogram(renderState.activeSessionData, renderState);
            renderMaterialPercentAmount(renderState.activeSessionData, renderState);
          }
        },
        onGridlinesToggle: (checked) => {
          indexStateController.setMaterialPercentGridlines(checked);
          schedulePersistIndexReportSettings();
          const renderState = getIndexRenderState();
          if (renderState.activeSessionData) {
            renderMaterialPercentAmount(renderState.activeSessionData, renderState);
            void renderProspectCumulativeFrequency(
              renderState.activeSessionData,
              renderState.activeSessionFilename,
              renderState
            );
          }
        },
        onIncludeDuplicatesToggle: (checked) => {
          indexStateController.setProspectFrequencyIncludeDuplicates(checked);
          schedulePersistIndexReportSettings();
          const renderState = getIndexRenderState();
          if (renderState.activeSessionData) {
            renderProspectHistogram(renderState.activeSessionData, renderState);
            const updatedRenderState = getIndexRenderState();
            renderMaterialPercentAmount(updatedRenderState.activeSessionData, updatedRenderState);
            void renderProspectCumulativeFrequency(
              updatedRenderState.activeSessionData,
              updatedRenderState.activeSessionFilename,
              updatedRenderState
            );
          }
        },
        onBinSizeSelect: (value) => {
          indexStateController.setProspectFrequencyBinSize(value);
          schedulePersistIndexReportSettings();
          const renderState = getIndexRenderState();
          if (renderState.activeSessionData) {
            renderProspectHistogram(renderState.activeSessionData, renderState);
          }
        },
        onReverseCumulativeToggle: (checked) => {
          indexStateController.setProspectFrequencyReverseCumulative(checked);
          schedulePersistIndexReportSettings();
          const renderState = getIndexRenderState();
          if (renderState.activeSessionData) {
            renderProspectHistogram(renderState.activeSessionData, renderState);
          }
        },
        onYieldPopulationSelect: (mode) => {
          indexStateController.setSelectedYieldPopulationMode(mode);
          schedulePersistIndexReportSettings();
          const renderState = getIndexRenderState();
          if (renderState.activeSessionData) {
            renderProspectHistogram(renderState.activeSessionData, renderState);
          }
        },
      });

      if (compareRingsButton) {
        compareRingsButton.addEventListener("click", () => openCompareRingsPage(getIndexRenderState()));
      }

      window.addEventListener("resize", () => {
        const renderState = getIndexRenderState();
        if (!renderState.activeSessionData) {
          return;
        }
        if (adaptiveLabelResizeTimer !== null) {
          window.clearTimeout(adaptiveLabelResizeTimer);
        }
        adaptiveLabelResizeTimer = window.setTimeout(() => {
          adaptiveLabelResizeTimer = null;
          const nextRenderState = getIndexRenderState();
          if (!nextRenderState.activeSessionData) {
            return;
          }
          renderProspectHistogram(nextRenderState.activeSessionData, nextRenderState);
        }, 140);
      });

      applyFocusTokenToTitle();
      initializeThemeControl();
      clearCharts("Loading chart data...");
      void loadSessionList();
    })();
