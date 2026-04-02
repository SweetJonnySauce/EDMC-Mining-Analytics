import { applyAdaptiveBinLabels } from "../shared/labels.js";
import { normalizeTextKey as normalizeTextKeyShared, normalizeCommodityKey as normalizeCommodityKeyShared } from "../shared/normalize.js";
import { asNumber as asNumberShared, formatNumber as formatNumberShared } from "../shared/number.js";
import { buildSmoothLinePath as buildSmoothLinePathShared, inferStep as inferStepShared } from "../shared/svg.js";
import { DEFAULT_THEME_ID, THEME_OPTIONS, createThemeController } from "../shared/theme.js";
import { createTooltipController } from "../shared/tooltip.js";
import { fetchFavoriteRings, fetchProspectedAsteroidSummary } from "../data/session_api.js";
import {
  buildCompareData as buildCompareDataModel,
  buildRingCommodityModel as buildRingCommodityModelModel
} from "./models/compare_model.js";
import { renderRingChart as renderRingChartModule } from "./charts/ring_chart.js";
import {
  renderReferenceCrosshairControls,
  renderYieldPopulationControls,
  renderGridlineControls,
  syncCommoditySelect as syncCommoditySelectControl,
} from "./ui/controls.js";
import { createCompareStore } from "./state/store.js";
import { createCompareStateController } from "./state/controller.js";

    (function () {
      const rootElement = document.documentElement;
      const themeToggle = document.getElementById("theme-toggle");
      const themeMenu = document.getElementById("theme-menu");
      const compareTitle = document.getElementById("compare-title");
      const compareCommoditySelect = document.getElementById("compare-commodity-select");
      const compareSortSelect = document.getElementById("compare-sort-select");
      const comparePopulationOptions = document.getElementById("compare-population-options");
      const compareReferenceOptions = document.getElementById("compare-reference-options");
      const compareGridlineOptions = document.getElementById("compare-gridline-options");
      const compareStatus = document.getElementById("compare-status");
      const compareList = document.getElementById("compare-list");
      const THEME_STORAGE_KEY = "edmcma.analysis.theme";
      const REFERENCE_CROSSHAIRS = [
        { key: "p90", label: "P90", metricKey: "p90", quantile: 0.9 },
        { key: "p75", label: "P75", metricKey: "p75", quantile: 0.75 },
        { key: "p50", label: "P50", metricKey: "p50", quantile: 0.5 },
        { key: "avg", label: "Avg", metricKey: "averageYield", quantile: null },
        { key: "p25", label: "P25", metricKey: "p25", quantile: 0.25 }
      ];
      const YIELD_POPULATION_MODES = [
        { key: "all", label: "All asteroids" },
        { key: "present", label: "Only w/ Commodity" }
      ];
      let activeThemeId = DEFAULT_THEME_ID;
      let compareData = null;
      let selectedCommodityKey = "";
      let requestedCommodityKey = "";
      let selectedYieldPopulationMode = "all";
      let selectedReferenceCrosshairs = new Set(["avg"]);
      let compareShowGridlines = true;
      let compareNormalizeMetrics = false;
      let compareReverseCumulative = false;
      let compareShowHistogram = false;
      let favoriteRingNames = new Set();
      const compareStore = createCompareStore({
        compareData,
        selectedCommodityKey,
        requestedCommodityKey,
        selectedYieldPopulationMode,
        selectedReferenceCrosshairs,
        compareShowGridlines,
        compareNormalizeMetrics,
        compareReverseCumulative,
        compareShowHistogram,
        favoriteRingNames
      });
      const compareStateController = createCompareStateController(compareStore);
      const syncCompareStateMirrors = (nextState) => {
        const state = nextState && typeof nextState === "object" ? nextState : {};
        compareData = state.compareData && typeof state.compareData === "object"
          ? state.compareData
          : null;
        selectedCommodityKey = typeof state.selectedCommodityKey === "string"
          ? state.selectedCommodityKey
          : "";
        requestedCommodityKey = typeof state.requestedCommodityKey === "string"
          ? state.requestedCommodityKey
          : "";
        selectedYieldPopulationMode = typeof state.selectedYieldPopulationMode === "string" && state.selectedYieldPopulationMode
          ? state.selectedYieldPopulationMode
          : "all";
        selectedReferenceCrosshairs = state.selectedReferenceCrosshairs instanceof Set
          ? new Set(state.selectedReferenceCrosshairs)
          : new Set(["avg"]);
        compareShowGridlines = state.compareShowGridlines !== false;
        compareNormalizeMetrics = !!state.compareNormalizeMetrics;
        compareReverseCumulative = !!state.compareReverseCumulative;
        compareShowHistogram = !!state.compareShowHistogram;
        favoriteRingNames = state.favoriteRingNames instanceof Set
          ? new Set(state.favoriteRingNames)
          : new Set();
      };
      syncCompareStateMirrors(compareStateController.getState());
      compareStateController.subscribe((nextState) => {
        syncCompareStateMirrors(nextState);
      });

      function getCompareRenderState() {
        const state = compareStateController.getState();
        return {
          compareData: state && typeof state.compareData === "object" ? state.compareData : null,
          selectedCommodityKey: typeof state.selectedCommodityKey === "string" ? state.selectedCommodityKey : "",
          requestedCommodityKey: typeof state.requestedCommodityKey === "string" ? state.requestedCommodityKey : "",
          selectedYieldPopulationMode: typeof state.selectedYieldPopulationMode === "string" && state.selectedYieldPopulationMode
            ? state.selectedYieldPopulationMode
            : "all",
          selectedReferenceCrosshairs: state && state.selectedReferenceCrosshairs instanceof Set
            ? new Set(state.selectedReferenceCrosshairs)
            : new Set(["avg"]),
          compareShowGridlines: !(state && state.compareShowGridlines === false),
          compareNormalizeMetrics: !!(state && state.compareNormalizeMetrics),
          compareReverseCumulative: !!(state && state.compareReverseCumulative),
          compareShowHistogram: !!(state && state.compareShowHistogram),
          favoriteRingNames: state && state.favoriteRingNames instanceof Set
            ? new Set(state.favoriteRingNames)
            : new Set()
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

      function resolveRequestedCommodityKey() {
        try {
          const params = new URLSearchParams(window.location.search || "");
          const rawCommodity = (params.get("commodity") || "").trim();
          return normalizeCommodityKey(rawCommodity);
        } catch (_err) {
          return "";
        }
      }

      function initializeThemeControl() {
        themeController.initialize();
      }

      function setStatus(text, isError) {
        if (!compareStatus) {
          return;
        }
        compareStatus.textContent = String(text || "");
        compareStatus.classList.toggle("bad", !!isError);
      }

      function setCompareTitle(commodityLabel) {
        if (!compareTitle) {
          return;
        }
        const label = typeof commodityLabel === "string" ? commodityLabel.trim() : "";
        if (!label) {
          compareTitle.textContent = "Compare Commodity Yield Across Rings";
          return;
        }
        compareTitle.textContent = `Compare ${label} Yield Across Rings`;
      }

      function normalizeTextKey(value) {
        return normalizeTextKeyShared(value);
      }

      function normalizeCommodityKey(value) {
        return normalizeCommodityKeyShared(value);
      }

      function pickCommodityLabel(current, candidate) {
        const next = typeof candidate === "string" ? candidate.trim() : "";
        if (!next) {
          return current || "";
        }
        if (!current) {
          return next;
        }
        const currentHasSpace = /\s/.test(current);
        const nextHasSpace = /\s/.test(next);
        if (!currentHasSpace && nextHasSpace) {
          return next;
        }
        return current;
      }

      function asNumber(value) {
        return asNumberShared(value);
      }

      function formatNumber(value, digits) {
        return formatNumberShared(value, digits);
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

      function buildSmoothLinePath(points) {
        return buildSmoothLinePathShared(points);
      }

      function inferStep(yMaxInt) {
        return inferStepShared(yMaxInt);
      }

      function buildCompareData(records) {
        return buildCompareDataModel({
          records,
          normalizeTextKey,
          normalizeCommodityKey,
          pickCommodityLabel
        });
      }

      function buildRingCommodityModel(ring, commodityKey, interval, forcedXMax, populationMode) {
        return buildRingCommodityModelModel({
          ring,
          commodityKey,
          interval,
          forcedXMax,
          populationMode
        });
      }

      function renderRingChart(chartPanel, ringName, commodityLabel, model, selectedCrosshairKeys, normalizeBySessions, reverseCumulative, showHistogram, stateSnapshot) {
        const renderState = stateSnapshot || getCompareRenderState();
        renderRingChartModule({
          chartPanel,
          ringName,
          commodityLabel,
          model,
          selectedCrosshairKeys,
          normalizeBySessions,
          reverseCumulative,
          showHistogram,
          showGridlines: renderState.compareShowGridlines,
          referenceCrosshairs: REFERENCE_CROSSHAIRS,
          applyAdaptiveBinLabels,
          inferStep,
          buildSmoothLinePath,
          formatNumber,
          asNumber,
          showCursorTooltip,
          hideCursorTooltip
        });
      }

      async function loadFavoriteRingNames() {
        const nextFavoriteRingNames = new Set();
        compareStateController.setFavoriteRingNames(nextFavoriteRingNames);
        try {
          const result = await fetchFavoriteRings();
          if (!result.ok) {
            return;
          }
          const payload = result.data;
          const rows = Array.isArray(payload)
            ? payload
            : ((payload && typeof payload === "object" && Array.isArray(payload.favorite_rings))
              ? payload.favorite_rings
              : []);
          rows.forEach((value) => {
            const ringName = typeof value === "string" ? value.trim() : "";
            if (ringName) {
              nextFavoriteRingNames.add(ringName);
            }
          });
          compareStateController.setFavoriteRingNames(nextFavoriteRingNames);
        } catch (_error) {
          // Optional source; ignore if unavailable.
        }
      }

      function dominantLabel(countMap) {
        if (!(countMap instanceof Map) || countMap.size === 0) {
          return "--";
        }
        let winner = "";
        let maxCount = -1;
        countMap.forEach((count, label) => {
          if (count > maxCount) {
            winner = label;
            maxCount = count;
          }
        });
        return winner || "--";
      }

      function syncReferenceCrosshairControls() {
        if (!compareReferenceOptions) {
          return;
        }
        const renderState = getCompareRenderState();
        renderReferenceCrosshairControls({
          container: compareReferenceOptions,
          referenceCrosshairs: REFERENCE_CROSSHAIRS,
          selectedReferenceCrosshairs: renderState.selectedReferenceCrosshairs,
          onToggle: (entryKey, checked) => {
            compareStateController.setReferenceCrosshairEnabled(entryKey, checked);
            renderComparePanels(getCompareRenderState());
          }
        });
      }

      function syncYieldPopulationControls() {
        if (!comparePopulationOptions) {
          return;
        }
        const renderState = getCompareRenderState();
        renderYieldPopulationControls({
          container: comparePopulationOptions,
          modes: YIELD_POPULATION_MODES,
          selectedYieldPopulationMode: renderState.selectedYieldPopulationMode,
          onSelect: (modeKey) => {
            compareStateController.setSelectedYieldPopulationMode(modeKey);
            renderComparePanels(getCompareRenderState());
          }
        });
      }

      function syncGridlineControls() {
        if (!compareGridlineOptions) {
          return;
        }
        const renderState = getCompareRenderState();
        renderGridlineControls({
          container: compareGridlineOptions,
          compareShowGridlines: renderState.compareShowGridlines,
          compareNormalizeMetrics: renderState.compareNormalizeMetrics,
          compareReverseCumulative: renderState.compareReverseCumulative,
          compareShowHistogram: renderState.compareShowHistogram,
          onGridlinesChange: (checked) => {
            compareStateController.setCompareShowGridlines(checked);
            renderComparePanels(getCompareRenderState());
          },
          onNormalizeChange: (checked) => {
            compareStateController.setCompareNormalizeMetrics(checked);
            renderComparePanels(getCompareRenderState());
          },
          onReverseChange: (checked) => {
            compareStateController.setCompareReverseCumulative(checked);
            renderComparePanels(getCompareRenderState());
          },
          onHistogramChange: (checked) => {
            compareStateController.setCompareShowHistogram(checked);
            renderComparePanels(getCompareRenderState());
          },
        });
      }

      function renderComparePanels(stateSnapshot) {
        const renderState = stateSnapshot || getCompareRenderState();
        const data = renderState.compareData;
        if (!compareList || !data) {
          setCompareTitle("");
          return;
        }
        const commodityKey = renderState.selectedCommodityKey;
        const commodityLabel = (data.commodities.find((item) => item.key === commodityKey) || {}).label || commodityKey || "--";
        setCompareTitle(commodityLabel);
        const sortMode = compareSortSelect ? compareSortSelect.value : "avg_desc";
        const interval = 5;
        const globalCommodityPeak = data.rings.reduce((peak, ring) => {
          const asteroids = Array.isArray(ring && ring.asteroidList) ? ring.asteroidList : [];
          const ringPeak = asteroids.reduce((innerPeak, asteroid) => {
            const value = Number(asteroid && asteroid.commodityPercentages && asteroid.commodityPercentages.get(commodityKey));
            if (!Number.isFinite(value)) {
              return innerPeak;
            }
            return Math.max(innerPeak, Math.max(0, value));
          }, 0);
          return Math.max(peak, ringPeak);
        }, 0);
        const sharedXMax = Math.max(interval, Math.ceil(globalCommodityPeak / interval) * interval);
        const rows = data.rings.map((ring) => {
          const metric = buildRingCommodityModel(ring, commodityKey, interval, sharedXMax, renderState.selectedYieldPopulationMode);
          return { ring, metric };
        }).filter((row) => Number(row && row.metric && row.metric.presentAsteroidsCount) > 0);
        rows.sort((left, right) => {
          if (sortMode === "name_asc") {
            return left.ring.ringName.localeCompare(right.ring.ringName);
          }
          if (
            sortMode === "p90_asc" || sortMode === "p90_desc"
            || sortMode === "p75_asc" || sortMode === "p75_desc"
            || sortMode === "p50_asc" || sortMode === "p50_desc"
            || sortMode === "p25_asc" || sortMode === "p25_desc"
          ) {
            let key = "p90";
            if (sortMode.startsWith("p75_")) {
              key = "p75";
            } else if (sortMode.startsWith("p50_")) {
              key = "p50";
            } else if (sortMode.startsWith("p25_")) {
              key = "p25";
            }
            const leftMetric = Number(left.metric[key]);
            const rightMetric = Number(right.metric[key]);
            const leftValid = Number.isFinite(leftMetric);
            const rightValid = Number.isFinite(rightMetric);
            if (leftValid && rightValid && leftMetric !== rightMetric) {
              return sortMode.endsWith("_asc")
                ? (leftMetric - rightMetric)
                : (rightMetric - leftMetric);
            }
            if (leftValid !== rightValid) {
              return leftValid ? -1 : 1;
            }
            return left.ring.ringName.localeCompare(right.ring.ringName);
          }
          const leftAvg = Number(left.metric.averageYield);
          const rightAvg = Number(right.metric.averageYield);
          const leftValid = Number.isFinite(leftAvg);
          const rightValid = Number.isFinite(rightAvg);
          if (leftValid && rightValid) {
            if (sortMode === "avg_asc" && leftAvg !== rightAvg) {
              return leftAvg - rightAvg;
            }
            if (sortMode !== "avg_asc" && leftAvg !== rightAvg) {
              return rightAvg - leftAvg;
            }
          } else if (leftValid !== rightValid) {
            return leftValid ? -1 : 1;
          }
          return left.ring.ringName.localeCompare(right.ring.ringName);
        });

        compareList.innerHTML = "";
        if (!rows.length) {
          const note = document.createElement("p");
          note.className = "compare-empty";
          note.textContent = `No rings have ${commodityLabel} data.`;
          compareList.appendChild(note);
          setStatus(`Showing 0 rings for ${commodityLabel}.`, false);
          return;
        }
        const pendingChartRenders = [];
        rows.forEach(({ ring, metric }) => {
          const row = document.createElement("article");
          row.className = "ring-row";

          const infoPanel = document.createElement("section");
          infoPanel.className = "ring-info-panel";

          const ringTitle = document.createElement("h2");
          ringTitle.className = "ring-title";
          ringTitle.textContent = ring.ringName;
          if (renderState.favoriteRingNames.has(String(ring.ringName || "").trim())) {
            const favoriteStar = document.createElement("span");
            favoriteStar.className = "ring-title-favorite";
            favoriteStar.textContent = "★";
            favoriteStar.title = "Favorite rings in the hotspot finder.";
            favoriteStar.setAttribute("aria-label", "Favorite rings in the hotspot finder.");
            ringTitle.appendChild(favoriteStar);
          }
          infoPanel.appendChild(ringTitle);

          const chartPanel = document.createElement("section");
          chartPanel.className = "ring-chart-panel";
          let hoveredInfoCrosshairKey = "";
          const renderRowChart = () => {
            const rowCrosshairs = new Set(renderState.selectedReferenceCrosshairs);
            if (hoveredInfoCrosshairKey) {
              rowCrosshairs.add(hoveredInfoCrosshairKey);
            }
            renderRingChart(
              chartPanel,
              ring.ringName,
              commodityLabel,
              metric,
              rowCrosshairs,
              renderState.compareNormalizeMetrics,
              renderState.compareReverseCumulative,
              renderState.compareShowHistogram,
              renderState
            );
          };

          const infoGrid = document.createElement("div");
          infoGrid.className = "info-grid";
          const usingAllAsteroidsForDisplay = renderState.selectedYieldPopulationMode === "all";
          const percentileScopeText = usingAllAsteroidsForDisplay
            ? "inclusive percentile across all prospected asteroids in this ring; asteroids without this commodity are treated as 0%."
            : "inclusive percentile across prospected asteroids where this commodity is present.";
          const averageScopeText = usingAllAsteroidsForDisplay
            ? "Mean yield across all prospected asteroids in this ring; asteroids without this commodity are treated as 0%."
            : "Mean yield across prospected asteroids where this commodity is present.";
          const buildZeroPercentileTooltip = (baseTooltip, percentileValue) => {
            const value = Number(percentileValue);
            if (!Number.isFinite(value) || value !== 0) {
              return baseTooltip;
            }
            if (usingAllAsteroidsForDisplay) {
              const totalAsteroids = Math.max(0, Number(metric.asteroidsCount));
              const presentAsteroids = Math.max(0, Number(metric.presentAsteroidsCount));
              const missingAsteroids = Math.max(0, totalAsteroids - presentAsteroids);
              if (totalAsteroids > 0 && missingAsteroids > 0) {
                const missingShare = (missingAsteroids / totalAsteroids) * 100;
                return `${baseTooltip}\n0% summary: ${formatNumber(missingAsteroids, 0)} of ${formatNumber(totalAsteroids, 0)} asteroids (${formatNumber(missingShare, 1)}%) have no ${commodityLabel}.`;
              }
            }
            return `${baseTooltip}\n0% summary: This percentile lands at 0% yield for ${commodityLabel}.`;
          };
          const metricRows = [
            {
              label: "P90",
              value: Number(metric.p90),
              display: Number.isFinite(metric.p90) ? `${formatNumber(metric.p90, 2)}%` : "--",
              tooltip: buildZeroPercentileTooltip(`P90 is the ${percentileScopeText}`, metric.p90),
              crosshairKey: "p90",
              crosshairValue: metric.p90
            },
            {
              label: "P75",
              value: Number(metric.p75),
              display: Number.isFinite(metric.p75) ? `${formatNumber(metric.p75, 2)}%` : "--",
              tooltip: buildZeroPercentileTooltip(`Top Quartile (P75): ${percentileScopeText}`, metric.p75),
              crosshairKey: "p75",
              crosshairValue: metric.p75
            },
            {
              label: "Median (P50)",
              value: Number(metric.p50),
              display: Number.isFinite(metric.p50) ? `${formatNumber(metric.p50, 2)}%` : "--",
              tooltip: buildZeroPercentileTooltip(`Median (P50): ${percentileScopeText}`, metric.p50),
              crosshairKey: "p50",
              crosshairValue: metric.p50
            },
            {
              label: "Avg Yield (mean)",
              value: Number(metric.averageYield),
              display: Number.isFinite(metric.averageYield) ? `${formatNumber(metric.averageYield, 2)}%` : "--",
              tooltip: averageScopeText,
              crosshairKey: "avg",
              crosshairValue: metric.averageYield
            },
            {
              label: "P25",
              value: Number(metric.p25),
              display: Number.isFinite(metric.p25) ? `${formatNumber(metric.p25, 2)}%` : "--",
              tooltip: buildZeroPercentileTooltip(`Bottom Quartile (P25): ${percentileScopeText}`, metric.p25),
              crosshairKey: "p25",
              crosshairValue: metric.p25
            }
          ];
          metricRows.sort((left, right) => {
            const leftValid = Number.isFinite(left.value);
            const rightValid = Number.isFinite(right.value);
            if (leftValid && rightValid) {
              if (left.value !== right.value) {
                return right.value - left.value;
              }
              return left.label.localeCompare(right.label);
            }
            if (leftValid !== rightValid) {
              return leftValid ? -1 : 1;
            }
            return left.label.localeCompare(right.label);
          });
          const infoRows = [
            ["Commodity", commodityLabel],
            ...metricRows.map((row) => [row.label, row.display, row.tooltip, row.crosshairKey, row.crosshairValue]),
            ["Asteroids", formatNumber(metric.asteroidsCount, 0)],
            ["Sessions", formatNumber(metric.sessionsCount, 0)],
            ["Ring Type", dominantLabel(ring.ringTypeCounts)],
            ["Reserve", dominantLabel(ring.reserveLevelCounts)]
          ];
          infoRows.forEach(([labelText, valueText, tooltipText, hoverCrosshairKey, hoverCrosshairValue]) => {
            const infoRow = document.createElement("div");
            infoRow.className = "info-row";
            const label = document.createElement("span");
            label.className = "label";
            label.textContent = `${labelText}:`;
            if (typeof tooltipText === "string" && tooltipText.trim()) {
              label.title = tooltipText;
            }
            const value = document.createElement("span");
            value.className = "value";
            value.textContent = String(valueText);
            if (hoverCrosshairKey && Number.isFinite(Number(hoverCrosshairValue))) {
              infoRow.classList.add("info-row--crosshair");
              const activateCrosshair = () => {
                if (hoveredInfoCrosshairKey === hoverCrosshairKey) {
                  return;
                }
                hoveredInfoCrosshairKey = hoverCrosshairKey;
                renderRowChart();
              };
              const deactivateCrosshair = () => {
                if (hoveredInfoCrosshairKey !== hoverCrosshairKey) {
                  return;
                }
                hoveredInfoCrosshairKey = "";
                renderRowChart();
              };
              infoRow.addEventListener("mouseenter", activateCrosshair);
              infoRow.addEventListener("mouseleave", deactivateCrosshair);
              value.addEventListener("mouseenter", activateCrosshair);
              value.addEventListener("mouseleave", deactivateCrosshair);
            }
            infoRow.appendChild(label);
            infoRow.appendChild(value);
            infoGrid.appendChild(infoRow);
          });
          infoPanel.appendChild(infoGrid);

          row.appendChild(infoPanel);
          row.appendChild(chartPanel);
          compareList.appendChild(row);
          pendingChartRenders.push(renderRowChart);
        });
        pendingChartRenders.forEach((renderRowChart) => {
          renderRowChart();
        });

        setStatus(
          `Showing ${rows.length} rings for ${commodityLabel}.`,
          false
        );
      }

      function syncCommodityControl(stateSnapshot) {
        const renderState = stateSnapshot || getCompareRenderState();
        const data = renderState.compareData;
        if (!compareCommoditySelect || !data) {
          return renderState;
        }
        syncCommoditySelectControl({
          selectElement: compareCommoditySelect,
          compareData: data,
          selectedCommodityKey: renderState.selectedCommodityKey,
          requestedCommodityKey: renderState.requestedCommodityKey,
          onSelectedCommodityKeyChange: (value) => {
            compareStateController.setSelectedCommodityKey(value);
          },
          onRequestedCommodityKeyConsume: () => {
            compareStateController.setRequestedCommodityKey("");
          },
        });
        return getCompareRenderState();
      }

      async function loadCompareData() {
        setStatus("Loading compare data...", false);
        try {
          await loadFavoriteRingNames();
          const result = await fetchProspectedAsteroidSummary();
          if (!result.ok) {
            throw new Error(`HTTP ${result.status}`);
          }
          const payload = result.text;
          const parsed = [];
          payload.split(/\r?\n/).forEach((line) => {
            const text = String(line || "").trim();
            if (!text) {
              return;
            }
            try {
              parsed.push(JSON.parse(text));
            } catch (_error) {
              // Skip malformed rows.
            }
          });
          const nextCompareData = buildCompareData(parsed);
          compareStateController.setCompareData(nextCompareData);
          if (!nextCompareData.commodities.length) {
            compareList.innerHTML = "";
            setStatus("No commodity records available yet.", false);
            return;
          }
          const renderState = syncCommodityControl(getCompareRenderState());
          renderComparePanels(renderState);
        } catch (error) {
          compareList.innerHTML = "";
          setStatus(
            `Unable to load compare data: ${error && error.message ? error.message : "Unknown error"}`,
            true
          );
        }
      }

      initializeThemeControl();
      compareStateController.setRequestedCommodityKey(resolveRequestedCommodityKey());
      syncYieldPopulationControls();
      syncReferenceCrosshairControls();
      syncGridlineControls();
      if (compareCommoditySelect) {
        compareCommoditySelect.addEventListener("change", (event) => {
          const target = event.target;
          compareStateController.setSelectedCommodityKey(target && typeof target.value === "string" ? target.value : "");
          renderComparePanels(getCompareRenderState());
        });
      }
      if (compareSortSelect) {
        compareSortSelect.addEventListener("change", () => {
          renderComparePanels(getCompareRenderState());
        });
      }
      void loadCompareData();
    })();
