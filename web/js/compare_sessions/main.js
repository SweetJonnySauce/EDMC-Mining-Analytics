import { fetchAnalysisSettings, fetchProspectedAsteroidSummary, saveAnalysisReportSettings } from "../data/session_api.js";
import { buildCompareData } from "../compare/models/compare_model.js";
import { buildSessionViolinModel, clusterSessionValueMarkers } from "../compare/models/session_violin_model.js";
import { buildPersistedCompareThemeUpdate, readPersistedCompareThemeId } from "./theme_persistence.js";
import { shouldShowOverallAverageMarker, shouldShowSessionMeanMarker } from "./average_visibility.js";
import { buildSessionTooltipText } from "./session_tooltips.js";
import { normalizeTextKey, normalizeCommodityKey } from "../shared/normalize.js";
import { formatNumber } from "../shared/number.js";
import { buildSessionAnalysisUrl } from "../shared/session_navigation.js";
import { DEFAULT_THEME_ID, THEME_OPTIONS, createThemeController } from "../shared/theme.js";
import { createTooltipController } from "../shared/tooltip.js";

(function () {
  const rootElement = document.documentElement;
  const themeToggle = document.getElementById("theme-toggle");
  const themeMenu = document.getElementById("theme-menu");
  const titleElement = document.getElementById("session-violin-title");
  const titleInfoAnchor = document.getElementById("session-violin-info-anchor");
  const subtitleElement = document.getElementById("session-violin-subtitle");
  const statusElement = document.getElementById("session-violin-status");
  const summaryElement = document.getElementById("session-violin-summary");
  const chartElement = document.getElementById("session-violin-chart");
  const THEME_STORAGE_KEY = "edmcma.analysis.theme";
  const VALID_THEME_IDS = new Set(THEME_OPTIONS.map((option) => option.id));
  let sessionThemeSaveTimer = null;
  let sessionThemePersistenceReady = false;
  let excludeZeroValueAsteroids = false;

  const tooltipController = createTooltipController();
  const themeController = createThemeController({
    rootElement,
    themeToggle,
    themeMenu,
    storageKey: THEME_STORAGE_KEY,
    defaultThemeId: DEFAULT_THEME_ID,
    themeOptions: THEME_OPTIONS,
    onThemeChange: (themeId) => {
      if (!sessionThemePersistenceReady) {
        return;
      }
      schedulePersistCompareTheme(themeId);
    },
  });

  function schedulePersistCompareTheme(themeId) {
    if (sessionThemeSaveTimer !== null) {
      window.clearTimeout(sessionThemeSaveTimer);
    }
    sessionThemeSaveTimer = window.setTimeout(async () => {
      sessionThemeSaveTimer = null;
      try {
        await saveAnalysisReportSettings(buildPersistedCompareThemeUpdate(themeId));
      } catch (_error) {
        // Keep the session report responsive if theme persistence is unavailable.
      }
    }, 350);
  }

  function setStatus(text, isError) {
    if (!statusElement) {
      return;
    }
    statusElement.textContent = String(text || "");
    statusElement.classList.toggle("bad", !!isError);
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

  function parseQueryState() {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return {
        ringName: String(params.get("ring") || "").trim(),
        commodityKey: normalizeCommodityKey(params.get("commodity") || ""),
        commodityLabel: String(params.get("commodity_label") || "").trim(),
        themeId: (() => {
          const themeId = String(params.get("theme") || "").trim();
          return VALID_THEME_IDS.has(themeId) ? themeId : "";
        })(),
      };
    } catch (_error) {
      return {
        ringName: "",
        commodityKey: "",
        commodityLabel: "",
        themeId: "",
      };
    }
  }

  async function loadPersistedSessionTheme(explicitThemeId) {
    if (explicitThemeId) {
      return;
    }
    try {
      const result = await fetchAnalysisSettings();
      if (!result.ok) {
        return;
      }
      const persistedThemeId = readPersistedCompareThemeId(result.data, themeController.getActiveThemeId());
      if (persistedThemeId !== themeController.getActiveThemeId()) {
        themeController.applyTheme(persistedThemeId, false);
      }
    } catch (_error) {
      // Keep the session report responsive if settings are unavailable.
    }
  }

  function renderSummaryCards(model) {
    if (!summaryElement) {
      return;
    }
    summaryElement.innerHTML = "";
    const peakYield = Array.isArray(model && model.sessions)
      ? model.sessions.reduce((peak, session) => Math.max(peak, Math.max(0, Number(session && session.maxValue) || 0)), 0)
      : 0;
    const cards = [
      { label: "Sessions", value: formatNumber(model.sessions.length, 0) },
      { label: "Asteroids", value: formatNumber(model.totalAsteroids, 0) },
      { label: "Peak Yield", value: `${formatNumber(peakYield, 2)}%` },
    ];
    cards.forEach((entry) => {
      const card = document.createElement("div");
      card.className = "session-violin-summary-card";
      const label = document.createElement("span");
      label.className = "session-violin-summary-label";
      label.textContent = entry.label;
      const value = document.createElement("span");
      value.className = "session-violin-summary-value";
      value.textContent = entry.value;
      card.appendChild(label);
      card.appendChild(value);
      summaryElement.appendChild(card);
    });
  }

  function buildViolinPath(session, centerX, yToPx, maxDensity, maxHalfWidth) {
    const points = Array.isArray(session && session.densityPoints) ? session.densityPoints : [];
    if (!points.length) {
      return "";
    }
    const safeMaxDensity = maxDensity > 0 ? maxDensity : 1;
    const rightSide = points.map((point) => {
      const density = Number(point && point.density);
      const width = (Number.isFinite(density) ? density : 0) / safeMaxDensity * maxHalfWidth;
      return {
        x: centerX + width,
        y: yToPx(point.y),
      };
    });
    const leftSide = [...points].reverse().map((point) => {
      const density = Number(point && point.density);
      const width = (Number.isFinite(density) ? density : 0) / safeMaxDensity * maxHalfWidth;
      return {
        x: centerX - width,
        y: yToPx(point.y),
      };
    });
    const outline = [...rightSide, ...leftSide];
    if (!outline.length) {
      return "";
    }
    let path = `M${outline[0].x.toFixed(2)} ${outline[0].y.toFixed(2)}`;
    for (let index = 1; index < outline.length; index += 1) {
      const point = outline[index];
      path += ` L${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
    }
    path += " Z";
    return path;
  }

  function buildSessionDotMarkers(values, yAxisMax, plotHeight) {
    const safeYAxisMax = Math.max(1, Number(yAxisMax) || 1);
    const safePlotHeight = Math.max(1, Number(plotHeight) || 1);
    const percentPerPixel = safeYAxisMax / safePlotHeight;
    const proximityThreshold = Math.max(0.35, percentPerPixel * 7);
    return clusterSessionValueMarkers(values, proximityThreshold);
  }

  function dotRadiusForCount(count) {
    const size = Math.max(1, Number(count) || 1);
    return Math.min(10, 4 + ((Math.sqrt(size) - 1) * 2.2));
  }

  function bindTooltip(node, text) {
    if (!node) {
      return;
    }
    const resolveText = () => (typeof text === "function" ? text() : text);
    node.addEventListener("mouseenter", (event) => {
      tooltipController.show(resolveText(), event);
    });
    node.addEventListener("mousemove", (event) => {
      tooltipController.show(resolveText(), event);
    });
    node.addEventListener("mouseleave", () => {
      tooltipController.hide();
    });
  }

  function formatAsteroidLine(asteroid) {
    const asteroidId = Number.isFinite(Number(asteroid && asteroid.asteroidId))
      ? `#${Math.trunc(Number(asteroid.asteroidId))}`
      : "Unknown";
    const value = formatNumber(Math.max(0, Number(asteroid && asteroid.value) || 0), 2);
    const notes = [];
    if (asteroid && asteroid.present === false) {
      notes.push("commodity absent");
    }
    if (asteroid && asteroid.duplicate) {
      notes.push("duplicate");
    }
    const noteText = notes.length ? ` (${notes.join(", ")})` : "";
    return `Asteroid ${asteroidId}: ${value}%${noteText}`;
  }

  function buildPointTooltipText(options) {
    const {
      commodityLabel,
      ringName,
      session,
      marker,
    } = options || {};
    const members = Array.isArray(marker && marker.members) ? marker.members : [];
    const visibleMembers = members.slice(0, 12);
    const hiddenCount = Math.max(0, members.length - visibleMembers.length);
    const lines = [
      `${commodityLabel} | ${ringName}`,
      session.sessionLabel,
      members.length > 1
        ? `Asteroids in dot: ${formatNumber(members.length, 0)}`
        : "Asteroid in dot: 1",
      members.length > 1
        ? `Yield span: ${formatNumber(marker.minValue, 2)}% to ${formatNumber(marker.maxValue, 2)}%`
        : `Yield: ${formatNumber(marker.value, 2)}%`,
      ...visibleMembers.map((asteroid) => formatAsteroidLine(asteroid)),
    ];
    if (hiddenCount > 0) {
      lines.push(`+ ${formatNumber(hiddenCount, 0)} more asteroids in cluster`);
    }
    return lines.join("\n");
  }

  function buildViolinInfoDialog() {
    const dialog = document.createElement("dialog");
    dialog.className = "compare-info-dialog";

    const content = document.createElement("div");
    content.className = "compare-info-dialog-content";

    const title = document.createElement("h3");
    title.className = "compare-info-dialog-title";
    title.textContent = "What A Violin Chart Shows";
    content.appendChild(title);

    const summaryList = document.createElement("ul");
    summaryList.className = "compare-info-dialog-list";
    [
      "Each violin represents one mining session on the x-axis.",
      "The y-axis is the asteroid content percentage for the selected commodity.",
      "Wider sections mean more asteroids were concentrated around that percentage range.",
      "Narrow sections mean fewer asteroids landed in that range.",
    ].forEach((item) => {
      const entry = document.createElement("li");
      entry.textContent = item;
      summaryList.appendChild(entry);
    });
    content.appendChild(summaryList);

    const section = document.createElement("section");
    section.className = "compare-info-dialog-section";

    const sectionTitle = document.createElement("h4");
    sectionTitle.className = "compare-info-dialog-section-title";
    sectionTitle.textContent = "How To Read This View";
    section.appendChild(sectionTitle);

    const description = document.createElement("p");
    description.className = "compare-info-dialog-description";
    description.textContent = "Use this chart to compare how each session's asteroid yields were distributed. A fat middle means yields were packed into that band. Long thin tails mean the session had a few outliers at low or high percentages.";
    section.appendChild(description);

    const note = document.createElement("p");
    note.className = "compare-info-dialog-note";
    note.textContent = "The short horizontal marker inside each violin is the session mean. The dots mark actual asteroid percentages; larger dots indicate multiple asteroids clustered at nearly the same value.";
    section.appendChild(note);

    content.appendChild(section);

    const actions = document.createElement("div");
    actions.className = "compare-info-dialog-actions";

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "compare-info-dialog-close";
    closeButton.textContent = "Close";
    closeButton.addEventListener("click", () => {
      if (dialog.open) {
        dialog.close();
      }
    });
    actions.appendChild(closeButton);
    content.appendChild(actions);

    dialog.appendChild(content);
    dialog.addEventListener("click", (event) => {
      const rect = dialog.getBoundingClientRect();
      const withinBounds = (
        event.clientX >= rect.left
        && event.clientX <= rect.right
        && event.clientY >= rect.top
        && event.clientY <= rect.bottom
      );
      if (!withinBounds && dialog.open) {
        dialog.close();
      }
    });

    const button = document.createElement("button");
    button.type = "button";
    button.className = "compare-info-button";
    button.textContent = "i";
    button.setAttribute("aria-label", "Explain what a violin chart shows");
    bindTooltip(button, "Explain what a violin chart shows");
    button.addEventListener("click", () => {
      tooltipController.hide();
      if (dialog.open) {
        return;
      }
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
        return;
      }
      dialog.setAttribute("open", "open");
    });

    return { button, dialog };
  }

  function buildChartNoteText() {
    if (excludeZeroValueAsteroids) {
      return "Asteroids with 0% of the selected commodity are excluded from this view.";
    }
    return "Each violin shows the distribution of prospected asteroid percentages in a session. Missing commodity values are treated as 0% for asteroids prospected in that session.";
  }

  function renderChart(model, commodityLabel, ringName, onToggleExcludeZeros) {
    if (!chartElement) {
      return;
    }
    chartElement.innerHTML = "";

    const controls = document.createElement("div");
    controls.className = "session-violin-chart-controls";

    const toggleLabel = document.createElement("label");
    toggleLabel.className = "session-violin-toggle";
    const toggleInput = document.createElement("input");
    toggleInput.type = "checkbox";
    toggleInput.checked = excludeZeroValueAsteroids;
    toggleInput.addEventListener("change", () => {
      excludeZeroValueAsteroids = !!toggleInput.checked;
      if (typeof onToggleExcludeZeros === "function") {
        onToggleExcludeZeros();
      }
    });
    const toggleText = document.createElement("span");
    toggleText.textContent = "Hide 0% asteroids";
    toggleLabel.appendChild(toggleInput);
    toggleLabel.appendChild(toggleText);
    controls.appendChild(toggleLabel);
    chartElement.appendChild(controls);

    if (!model.sessions.length) {
      const empty = document.createElement("p");
      empty.className = "session-violin-empty";
      empty.textContent = excludeZeroValueAsteroids
        ? "No sessions remain after excluding 0% asteroids."
        : "No sessions available for this ring and commodity.";
      chartElement.appendChild(empty);
      return;
    }

    const title = document.createElement("p");
    title.className = "session-violin-chart-title";
    title.textContent = `Session Violins (${commodityLabel} - ${ringName})`;
    chartElement.appendChild(title);

    const note = document.createElement("p");
    note.className = "session-violin-chart-note";
    note.textContent = buildChartNoteText();
    chartElement.appendChild(note);

    const widthPerSession = 88;
    const axisPaneWidth = 72;
    const rightPad = 28;
    const topPad = 20;
    const bottomPad = 78;
    const plotHeight = 320;
    const plotWidth = model.sessions.length * widthPerSession;
    const plotSvgWidth = plotWidth + rightPad;
    const height = topPad + plotHeight + bottomPad;
    const yAxisMax = Math.max(5, Number(model.yMax) || 5);
    const overallAverageYield = Number.isFinite(Number(model && model.averageYield))
      ? Math.max(0, Number(model.averageYield))
      : null;
    const showOverallAverageMarker = shouldShowOverallAverageMarker(excludeZeroValueAsteroids);
    const showSessionMeanMarker = shouldShowSessionMeanMarker(excludeZeroValueAsteroids);
    const yTickStep = yAxisMax <= 25 ? 5 : 10;
    const maxHalfWidth = Math.min(28, Math.max(14, widthPerSession * 0.32));
    const plotBottom = topPad + plotHeight;
    const axisLineX = axisPaneWidth - 8;
    const axisLabelX = axisLineX - 10;
    const axisTitleX = 20;
    const toY = (value) => {
      const safeValue = Math.max(0, Math.min(yAxisMax, Number(value) || 0));
      return topPad + (plotHeight * (1 - (safeValue / yAxisMax)));
    };
    const averageLineY = Number.isFinite(overallAverageYield) ? toY(overallAverageYield) : null;
    const toX = (index) => ((index + 0.5) * widthPerSession);
    const ns = "http://www.w3.org/2000/svg";
    const layout = document.createElement("div");
    layout.className = "session-violin-layout";
    chartElement.appendChild(layout);

    const axisPane = document.createElement("div");
    axisPane.className = "session-violin-axis-pane";
    layout.appendChild(axisPane);

    const scroll = document.createElement("div");
    scroll.className = "session-violin-scroll";
    layout.appendChild(scroll);

    const axisSvg = document.createElementNS(ns, "svg");
    axisSvg.classList.add("session-violin-axis-svg");
    axisSvg.setAttribute("viewBox", `0 0 ${axisPaneWidth} ${height}`);
    axisSvg.setAttribute("preserveAspectRatio", "xMinYMin meet");
    axisSvg.style.width = `${axisPaneWidth}px`;
    axisPane.appendChild(axisSvg);

    const plotSvg = document.createElementNS(ns, "svg");
    plotSvg.classList.add("session-violin-svg");
    plotSvg.setAttribute("viewBox", `0 0 ${plotSvgWidth} ${height}`);
    plotSvg.setAttribute("preserveAspectRatio", "xMinYMin meet");
    plotSvg.style.width = `${plotSvgWidth}px`;

    for (let value = 0; value <= yAxisMax + 0.0001; value += yTickStep) {
      const y = toY(value);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("class", "session-violin-grid-line");
      line.setAttribute("x1", "0");
      line.setAttribute("x2", plotWidth.toFixed(2));
      line.setAttribute("y1", y.toFixed(2));
      line.setAttribute("y2", y.toFixed(2));
      plotSvg.appendChild(line);

      const label = document.createElementNS(ns, "text");
      label.setAttribute("class", "session-violin-axis-label");
      label.setAttribute("x", axisLabelX.toFixed(2));
      label.setAttribute("y", (y + 4).toFixed(2));
      label.setAttribute("text-anchor", "end");
      const averageOverlapsTick = showOverallAverageMarker
        && Number.isFinite(averageLineY)
        && Math.abs(averageLineY - y) < 10;
      if (averageOverlapsTick) {
        label.setAttribute("visibility", "hidden");
      }
      label.textContent = `${formatNumber(value, 0)}%`;
      axisSvg.appendChild(label);
    }

    const yAxis = document.createElementNS(ns, "line");
    yAxis.setAttribute("class", "session-violin-axis-line");
    yAxis.setAttribute("x1", axisLineX.toFixed(2));
    yAxis.setAttribute("x2", axisLineX.toFixed(2));
    yAxis.setAttribute("y1", topPad.toFixed(2));
    yAxis.setAttribute("y2", plotBottom.toFixed(2));
    axisSvg.appendChild(yAxis);

    const xAxis = document.createElementNS(ns, "line");
    xAxis.setAttribute("class", "session-violin-axis-line");
    xAxis.setAttribute("x1", "0");
    xAxis.setAttribute("x2", plotWidth.toFixed(2));
    xAxis.setAttribute("y1", plotBottom.toFixed(2));
    xAxis.setAttribute("y2", plotBottom.toFixed(2));
    plotSvg.appendChild(xAxis);

    const axisTitle = document.createElementNS(ns, "text");
    axisTitle.setAttribute("class", "session-violin-axis-title");
    axisTitle.setAttribute("x", axisTitleX.toFixed(2));
    axisTitle.setAttribute("y", (topPad + (plotHeight / 2)).toFixed(2));
    axisTitle.setAttribute("text-anchor", "middle");
    axisTitle.setAttribute("transform", `rotate(-90 ${axisTitleX.toFixed(2)} ${(topPad + (plotHeight / 2)).toFixed(2)})`);
    axisTitle.textContent = "% Content";
    axisSvg.appendChild(axisTitle);

    if (showOverallAverageMarker && Number.isFinite(averageLineY) && Number.isFinite(overallAverageYield)) {
      const averageTooltipText = `Overall Avg Yield: ${formatNumber(overallAverageYield, 2)}%`;
      const averageHitArea = document.createElementNS(ns, "line");
      averageHitArea.setAttribute("class", "session-violin-overall-average-hitarea");
      averageHitArea.setAttribute("x1", "0");
      averageHitArea.setAttribute("x2", plotWidth.toFixed(2));
      averageHitArea.setAttribute("y1", averageLineY.toFixed(2));
      averageHitArea.setAttribute("y2", averageLineY.toFixed(2));
      bindTooltip(averageHitArea, averageTooltipText);
      plotSvg.appendChild(averageHitArea);

      const averageLine = document.createElementNS(ns, "line");
      averageLine.setAttribute("class", "session-violin-overall-average");
      averageLine.setAttribute("x1", "0");
      averageLine.setAttribute("x2", plotWidth.toFixed(2));
      averageLine.setAttribute("y1", averageLineY.toFixed(2));
      averageLine.setAttribute("y2", averageLineY.toFixed(2));
      bindTooltip(averageLine, averageTooltipText);
      plotSvg.appendChild(averageLine);

      const averageLabel = document.createElementNS(ns, "text");
      averageLabel.setAttribute("class", "session-violin-overall-average-label");
      averageLabel.setAttribute("x", axisLabelX.toFixed(2));
      averageLabel.setAttribute("y", (averageLineY + 4).toFixed(2));
      averageLabel.setAttribute("text-anchor", "end");
      averageLabel.textContent = "Avg";
      bindTooltip(averageLabel, averageTooltipText);
      axisSvg.appendChild(averageLabel);
    }

    model.sessions.forEach((session, index) => {
      const centerX = toX(index);
      const sessionTooltipText = buildSessionTooltipText({
        commodityLabel,
        ringName,
        session,
      });

      const violinPath = buildViolinPath(session, centerX, toY, model.maxDensity, maxHalfWidth);
      const path = document.createElementNS(ns, "path");
      path.setAttribute("class", "session-violin-path");
      path.setAttribute("d", violinPath);
      bindTooltip(path, sessionTooltipText);
      plotSvg.appendChild(path);

      if (showSessionMeanMarker) {
        const meanLine = document.createElementNS(ns, "line");
        const meanHalfSpan = Math.max(10, Math.min(18, maxHalfWidth * 0.7));
        meanLine.setAttribute("class", "session-violin-mean");
        meanLine.setAttribute("x1", (centerX - meanHalfSpan).toFixed(2));
        meanLine.setAttribute("x2", (centerX + meanHalfSpan).toFixed(2));
        meanLine.setAttribute("y1", toY(session.averageYield).toFixed(2));
        meanLine.setAttribute("y2", toY(session.averageYield).toFixed(2));
        plotSvg.appendChild(meanLine);
      }

      const dotMarkers = buildSessionDotMarkers(session.asteroidSamples, yAxisMax, plotHeight);
      dotMarkers.forEach((marker) => {
        const dot = document.createElementNS(ns, "circle");
        const radius = dotRadiusForCount(marker.count);
        dot.setAttribute("class", marker.count > 1 ? "session-violin-point session-violin-point--clustered" : "session-violin-point");
        dot.setAttribute("cx", centerX.toFixed(2));
        dot.setAttribute("cy", toY(marker.value).toFixed(2));
        dot.setAttribute("r", radius.toFixed(2));
        bindTooltip(dot, () => buildPointTooltipText({
          commodityLabel,
          ringName,
          session,
          marker,
        }));
        plotSvg.appendChild(dot);
      });

      const label = document.createElementNS(ns, "text");
      label.setAttribute("class", "session-violin-label");
      label.setAttribute("x", centerX.toFixed(2));
      label.setAttribute("y", (plotBottom + 22).toFixed(2));
      label.setAttribute("text-anchor", "middle");
      label.textContent = session.sessionLabel;
      const sessionAnalysisUrl = buildSessionAnalysisUrl({
        sessionGuid: session.sessionGuid,
        themeId: themeController.getActiveThemeId(),
      });
      if (session.sessionGuid) {
        const link = document.createElementNS(ns, "a");
        link.setAttribute("href", sessionAnalysisUrl);
        link.setAttribute("class", "session-violin-session-link");
        link.addEventListener("click", () => {
          link.setAttribute("href", buildSessionAnalysisUrl({
            sessionGuid: session.sessionGuid,
            themeId: themeController.getActiveThemeId(),
          }));
        });
        bindTooltip(link, `Open ${session.sessionLabel} in session analysis`);
        label.setAttribute("class", "session-violin-label session-violin-label--link");
        link.appendChild(label);
        plotSvg.appendChild(link);
      } else {
        bindTooltip(label, sessionTooltipText);
        plotSvg.appendChild(label);
      }
    });

    scroll.appendChild(plotSvg);
  }

  async function initializePage() {
    const query = parseQueryState();
    themeController.initialize();
    await loadPersistedSessionTheme(query.themeId);
    sessionThemePersistenceReady = true;
    if (titleInfoAnchor) {
      const { button, dialog } = buildViolinInfoDialog();
      titleInfoAnchor.replaceChildren(button);
      document.body.appendChild(dialog);
    }
    if (!query.ringName || !query.commodityKey) {
      setStatus("Missing ring or commodity in the session violin URL.", true);
      if (subtitleElement) {
        subtitleElement.textContent = "Open this page from the compare report.";
      }
      return;
    }

    setStatus("Loading session violin data...", false);
    try {
      const result = await fetchProspectedAsteroidSummary();
      if (!result.ok) {
        throw new Error(`HTTP ${result.status}`);
      }
      const rows = [];
      String(result.text || "").split(/\r?\n/).forEach((line) => {
        const text = String(line || "").trim();
        if (!text) {
          return;
        }
        try {
          rows.push(JSON.parse(text));
        } catch (_error) {
          // Skip malformed rows.
        }
      });
      const compareData = buildCompareData({
        records: rows,
        normalizeTextKey,
        normalizeCommodityKey,
        pickCommodityLabel,
      });
      const ringKey = normalizeTextKey(query.ringName);
      const ring = Array.isArray(compareData.rings)
        ? compareData.rings.find((entry) => normalizeTextKey(entry && entry.ringName) === ringKey)
        : null;
      const commodity = Array.isArray(compareData.commodities)
        ? compareData.commodities.find((entry) => entry && entry.key === query.commodityKey)
        : null;
      if (!ring || !commodity) {
        throw new Error("Selected ring or commodity could not be found in the compare dataset.");
      }
      const commodityLabel = commodity.label || query.commodityLabel || query.commodityKey;
      if (titleElement) {
        titleElement.textContent = `${commodityLabel} Session Violins`;
      }
      if (subtitleElement) {
        subtitleElement.textContent = `${ring.ringName} • Each violin shows the per-session distribution of asteroid content percentages.`;
      }
      const renderPage = () => {
        const model = buildSessionViolinModel({
          ring,
          commodityKey: query.commodityKey,
          excludeZeroValueAsteroids,
        });
        renderSummaryCards(model);
        renderChart(model, commodityLabel, ring.ringName, renderPage);
        const filterSuffix = excludeZeroValueAsteroids ? " (0% asteroids hidden)" : "";
        setStatus(`Showing ${formatNumber(model.sessions.length, 0)} sessions for ${commodityLabel}.${filterSuffix}`, false);
      };
      renderPage();
    } catch (error) {
      if (summaryElement) {
        summaryElement.innerHTML = "";
      }
      if (chartElement) {
        chartElement.innerHTML = "";
      }
      setStatus(
        `Unable to load session violin data: ${error && error.message ? error.message : "Unknown error"}`,
        true
      );
    }
  }

  void initializePage();
})();
