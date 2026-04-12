import { interpolateMissingValuesBetweenRealBins } from "../models/compare_model.js";
import { getResInfoDialogModel } from "../ui/res_info.js";

export function isNoDataDot(point, useCdf) {
  if (!point || typeof point !== "object") {
    return true;
  }
  if (useCdf) {
    if (point.isTerminalThresholdPoint) {
      return false;
    }
    return !point.hasRealData;
  }
  return Number(point.displayBinCount) <= 0;
}

function inferProbabilityStep(maxValue) {
  const targetTickCount = 5;
  const safeMax = Math.max(0.01, Number(maxValue) || 0.01);
  const minStep = Math.max(0.01, safeMax / (targetTickCount - 1));
  let magnitude = Math.pow(10, Math.floor(Math.log10(minStep)));
  if (!Number.isFinite(magnitude) || magnitude <= 0) {
    magnitude = 0.01;
  }
  let step = 0;
  for (let attempts = 0; attempts < 8 && step <= 0; attempts += 1) {
    [1, 2, 2.5, 5].forEach((multiplier) => {
      const candidate = multiplier * magnitude;
      if (candidate >= minStep && (step <= 0 || candidate < step)) {
        step = candidate;
      }
    });
    magnitude *= 10;
  }
  return step > 0 ? step : 0.25;
}

export function buildCdfAxisScale(points, totalPopulation) {
  const safePopulation = Math.max(1, Number(totalPopulation) || 0);
  const values = (Array.isArray(points) ? points : [])
    .map((point) => Number(point && point.totalReverse) / safePopulation)
    .filter((value) => Number.isFinite(value) && value >= 0);
  const observedMax = values.reduce((peak, value) => Math.max(peak, value), 0);
  if (observedMax <= 0) {
    return {
      countAxisScaleMax: 1,
      yTicks: [1, 0.75, 0.5, 0.25, 0],
    };
  }
  const countAxisStep = inferProbabilityStep(observedMax);
  const countAxisScaleMax = Math.max(
    countAxisStep,
    Math.ceil(observedMax / countAxisStep) * countAxisStep
  );
  const yTicks = [];
  for (let value = countAxisScaleMax; value >= 0; value -= countAxisStep) {
    yTicks.push(Number(Math.max(0, value).toFixed(6)));
  }
  if (yTicks[yTicks.length - 1] !== 0) {
    yTicks.push(0);
  }
  return {
    countAxisScaleMax,
    yTicks,
  };
}

function buildCompareBinLabelsRow(
  points,
  reverseCumulative,
  applyAdaptiveBinLabels,
  useThresholdLabels,
  showCursorTooltip,
  hideCursorTooltip,
  axisTooltipText,
) {
  const labels = document.createElement("div");
  labels.className = "compare-bin-labels";
  const labelPoints = reverseCumulative ? [...points].reverse() : points;
  labels.style.gridTemplateColumns = `repeat(${labelPoints.length}, minmax(0, 1fr))`;
  const labelTexts = [];
  labelPoints.forEach((point, index) => {
    const label = document.createElement("span");
    label.className = "compare-bin-label";
    const labelRangeStart = reverseCumulative ? point.intervalEnd : point.intervalStart;
    const labelRangeEnd = reverseCumulative ? point.intervalStart : point.intervalEnd;
    labelTexts[index] = useThresholdLabels
      ? `${formatThresholdLabel(point, reverseCumulative)}%`
      : `${labelRangeStart}-${labelRangeEnd}%`;
    const tooltipText = useThresholdLabels ? "% content" : String(axisTooltipText || "").trim();
    if (tooltipText) {
      label.setAttribute("aria-label", tooltipText);
      if (typeof showCursorTooltip === "function" && typeof hideCursorTooltip === "function") {
        label.addEventListener("mouseenter", (event) => {
          showCursorTooltip(tooltipText, event);
        });
        label.addEventListener("mousemove", (event) => {
          showCursorTooltip(tooltipText, event);
        });
        label.addEventListener("mouseleave", () => {
          hideCursorTooltip();
        });
      }
    }
    labels.appendChild(label);
  });
  applyAdaptiveBinLabels(labels, labelTexts, 4);
  const labelsRow = document.createElement("div");
  labelsRow.className = "compare-bin-label-row";
  const spacer = document.createElement("div");
  spacer.className = "compare-y-axis compare-bin-spacer";
  labelsRow.appendChild(spacer);
  labelsRow.appendChild(labels);
  return labelsRow;
}

function formatThresholdLabel(point, reverseCumulative) {
  if (!point || typeof point !== "object") {
    return "0";
  }
  const value = reverseCumulative ? Number(point.intervalEnd) : Number(point.intervalStart);
  return Number.isFinite(value) ? String(value) : "0";
}

export function buildAboveThresholdDisplayPoints(model) {
  const rawRows = Array.isArray(model && model.aboveThresholdPlanRows)
    ? model.aboveThresholdPlanRows
    : [];
  const sourcePoints = (Array.isArray(model && model.points)
    ? model.points
    : []);
  if (!sourcePoints.length) {
    return [];
  }

  let trailingZeroStart = sourcePoints.length;
  for (let index = sourcePoints.length - 1; index >= 0; index -= 1) {
    if (Number(sourcePoints[index] && sourcePoints[index].totalReverse) > 0) {
      break;
    }
    trailingZeroStart = index;
  }
  if ((sourcePoints.length - trailingZeroStart) > 1) {
    sourcePoints.splice(trailingZeroStart + 1);
  }

  const lastPoint = sourcePoints[sourcePoints.length - 1];
  if (lastPoint && lastPoint.hasRealData && Number(lastPoint.totalReverse) > 0) {
    const lastStart = Number(lastPoint.intervalStart);
    const lastEnd = Number(lastPoint.intervalEnd);
    const inferredStep = Number.isFinite(lastEnd - lastStart) && (lastEnd - lastStart) > 0
      ? (lastEnd - lastStart)
      : 5;
    const terminalRow = rawRows.find((row) => Number(row && row.cutoffYieldPercent) === lastEnd);
    sourcePoints.push({
      ...lastPoint,
      index: Number.isFinite(Number(lastPoint.index)) ? (Number(lastPoint.index) + 1) : sourcePoints.length,
      intervalStart: lastEnd,
      intervalEnd: lastEnd + inferredStep,
      center: lastEnd + (inferredStep / 2),
      binCount: 0,
      hasRealData: !!(terminalRow && terminalRow.hasRealData),
      total: 0,
      totalForward: Number(lastPoint.totalForward),
      totalReverse: 0,
    });
  }

  return sourcePoints;
}

function buildAboveThresholdPlanDisplayModel(model) {
  const points = buildAboveThresholdDisplayPoints(model);
  const rawRows = Array.isArray(model && model.aboveThresholdPlanRows)
    ? model.aboveThresholdPlanRows
    : [];
  const rowsByCutoff = new Map();
  rawRows.forEach((row) => {
    const cutoff = Number(row && row.cutoffYieldPercent);
    if (Number.isFinite(cutoff)) {
      rowsByCutoff.set(cutoff, row);
    }
  });
  const rows = points.map((point) => {
    const cutoff = Number(point && point.intervalStart);
    const matchedRow = rowsByCutoff.get(cutoff);
    if (matchedRow) {
      return matchedRow;
    }
    return {
      cutoffYieldPercent: cutoff,
      asteroidsToMine: null,
      asteroidsToProspect: null,
    };
  });
  const alignedPoints = points.map((point, index) => {
    const matchedRow = rows[index];
    if (!matchedRow) {
      return point;
    }
    const qualifyingCount = Number(matchedRow.qualifyingAsteroidsCount);
    if (!Number.isFinite(qualifyingCount)) {
      return point;
    }
    return {
      ...point,
      totalReverse: qualifyingCount,
      hasRealData: !!matchedRow.hasRealData,
    };
  });
  const prospectDisplayValues = interpolateMissingValuesBetweenRealBins({
    entries: rows,
    readValue: (row) => row && row.asteroidsToProspect,
    isRealEntry: (_row, index) => !!(alignedPoints[index] && alignedPoints[index].hasRealData),
  });
  const mineDisplayValues = interpolateMissingValuesBetweenRealBins({
    entries: rows,
    readValue: (row) => row && row.asteroidsToMine,
    isRealEntry: (_row, index) => !!(alignedPoints[index] && alignedPoints[index].hasRealData),
  });
  return {
    points: alignedPoints,
    rows,
    prospectDisplayValues,
    mineDisplayValues,
  };
}

function buildCumulativeDisplayPoints(points, reverseCumulative) {
  const sourcePoints = Array.isArray(points) ? [...points] : [];
  if (!sourcePoints.length) {
    return [];
  }
  const displayPoints = reverseCumulative ? [...sourcePoints].reverse() : sourcePoints;
  let lastRealDisplayIndex = displayPoints.length - 1;
  while (lastRealDisplayIndex >= 0 && !displayPoints[lastRealDisplayIndex].hasRealData) {
    lastRealDisplayIndex -= 1;
  }
  if (lastRealDisplayIndex < 0) {
    return [];
  }
  const trimmedDisplayPoints = displayPoints.slice(0, lastRealDisplayIndex + 1);
  return reverseCumulative ? trimmedDisplayPoints.reverse() : trimmedDisplayPoints;
}

function buildResInfoDialog(showCursorTooltip, hideCursorTooltip) {
  const model = getResInfoDialogModel();
  const dialog = document.createElement("dialog");
  dialog.className = "compare-info-dialog";

  const content = document.createElement("div");
  content.className = "compare-info-dialog-content";

  const title = document.createElement("h3");
  title.className = "compare-info-dialog-title";
  title.textContent = model.title;
  content.appendChild(title);

  const summaryItems = Array.isArray(model.summaryPoints) ? model.summaryPoints : [];
  if (summaryItems.length) {
    const summaryList = document.createElement("ul");
    summaryList.className = "compare-info-dialog-list";
    summaryItems.forEach((item) => {
      const text = String(item || "").trim();
      if (!text) {
        return;
      }
      const entry = document.createElement("li");
      entry.textContent = text;
      summaryList.appendChild(entry);
    });
    if (summaryList.childElementCount) {
      content.appendChild(summaryList);
    }
  }

  const tableSections = Array.isArray(model.tables) ? model.tables : [];
  tableSections.forEach((sectionModel) => {
    const rows = Array.isArray(sectionModel && sectionModel.rows) ? sectionModel.rows : [];
    const columns = Array.isArray(sectionModel && sectionModel.columns) ? sectionModel.columns : [];
    if (!rows.length || columns.length < 2) {
      return;
    }

    const section = document.createElement("section");
    section.className = "compare-info-dialog-section";

    const heading = document.createElement("h4");
    heading.className = "compare-info-dialog-section-title";
    heading.textContent = String(sectionModel.title || "").trim() || "Details";
    section.appendChild(heading);

    const description = String(sectionModel.description || "").trim();
    if (description) {
      const body = document.createElement("p");
      body.className = "compare-info-dialog-description";
      body.textContent = description;
      section.appendChild(body);
    }

    const table = document.createElement("table");
    table.className = "compare-info-dialog-table";

    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    columns.forEach((columnLabel) => {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = String(columnLabel || "").trim();
      headRow.appendChild(cell);
    });
    head.appendChild(headRow);
    table.appendChild(head);

    const body = document.createElement("tbody");
    rows.forEach((rowValues) => {
      if (!Array.isArray(rowValues) || rowValues.length < 2) {
        return;
      }
      const row = document.createElement("tr");
      rowValues.forEach((value, index) => {
        const cell = document.createElement(index === 0 ? "th" : "td");
        if (index === 0) {
          cell.scope = "row";
        }
        cell.textContent = String(value || "").trim();
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
    if (!body.childElementCount) {
      return;
    }
    table.appendChild(body);
    section.appendChild(table);
    content.appendChild(section);
  });

  const closingNote = String(model.closingNote || "").trim();
  if (closingNote) {
    const note = document.createElement("p");
    note.className = "compare-info-dialog-note";
    note.textContent = closingNote;
    content.appendChild(note);
  }

  const source = document.createElement("p");
  source.className = "compare-info-dialog-source";
  source.append("Source: ");
  const link = document.createElement("a");
  link.href = model.sourceUrl;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = model.sourceUrl;
  source.appendChild(link);
  content.appendChild(source);

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
  button.setAttribute("aria-label", "Explain the outside-RES yield assumption");
  if (typeof showCursorTooltip === "function" && typeof hideCursorTooltip === "function") {
    button.addEventListener("mouseenter", (event) => {
      showCursorTooltip("Explain the outside-RES yield assumption", event);
    });
    button.addEventListener("mousemove", (event) => {
      showCursorTooltip("Explain the outside-RES yield assumption", event);
    });
    button.addEventListener("mouseleave", () => {
      hideCursorTooltip();
    });
  }
  button.addEventListener("click", () => {
    if (typeof hideCursorTooltip === "function") {
      hideCursorTooltip();
    }
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

function renderHistogramSection(options) {
  const {
    chartPanel,
    ringName,
    commodityLabel,
    model,
    displayPoints,
    normalizeBySessions,
    reverseCumulative,
    interactions,
    showGridlines,
    inferStep,
    formatNumber,
    showCursorTooltip,
    hideCursorTooltip,
    applyAdaptiveBinLabels,
  } = options || {};
  const histogramPoints = Array.isArray(displayPoints) && displayPoints.length
    ? displayPoints
    : (Array.isArray(model && model.points) ? model.points : []);
  const section = document.createElement("div");
  section.className = "compare-chart-section";

  const title = document.createElement("p");
  title.className = "ring-chart-title";
  title.textContent = "Asteroid Percentage Histogram";
  section.appendChild(title);

  const width = 1000;
  let height = 180;
  const topPad = 10;
  const bottomPad = 16;
  const sidePad = 14;
  const drawWidth = Math.max(1, width - (sidePad * 2));
  let drawHeight = Math.max(1, height - topPad - bottomPad);
  const totalBins = Math.max(1, histogramPoints.length);
  const toDisplayIndex = (index) => (
    reverseCumulative
      ? (totalBins - index - 1)
      : index
  );
  const toXForBinStart = (index) => sidePad + ((toDisplayIndex(index) / totalBins) * drawWidth);
  const toXForBinEnd = (index) => sidePad + (((toDisplayIndex(index) + 1) / totalBins) * drawWidth);
  const sessionDivisor = normalizeBySessions
    ? Math.max(1, Number(model && model.sessionsCount) || 0)
    : 1;
  const displayPeak = histogramPoints.reduce((peak, point) => (
    Math.max(peak, Number(point.binCount) / sessionDivisor)
  ), 0);
  const countAxisMaxInt = Math.max(1, Math.ceil(displayPeak));
  const countAxisStep = inferStep(countAxisMaxInt);
  const countAxisScaleMax = Math.max(countAxisMaxInt, Math.ceil(countAxisMaxInt / countAxisStep) * countAxisStep);
  const yTicks = [];
  for (let value = countAxisScaleMax; value >= 0; value -= countAxisStep) {
    yTicks.push(value);
  }
  if (yTicks[yTicks.length - 1] !== 0) {
    yTicks.push(0);
  }
  const toYForCount = (count) => {
    const ratio = countAxisScaleMax <= 0 ? 0 : (count / countAxisScaleMax);
    return topPad + (drawHeight * (1 - ratio));
  };

  const plot = document.createElement("div");
  plot.className = "compare-plot compare-plot--histogram";
  const yAxis = document.createElement("div");
  yAxis.className = "compare-y-axis";
  const yAxisTicks = document.createElement("div");
  yAxisTicks.className = "compare-y-axis-ticks";
  yTicks.forEach((value) => {
    const tick = document.createElement("span");
    tick.className = "compare-y-axis-tick";
    tick.textContent = String(value);
    tick.setAttribute("aria-label", "# of asteroids");
    tick.addEventListener("mouseenter", (event) => {
      showCursorTooltip("# of asteroids", event);
    });
    tick.addEventListener("mousemove", (event) => {
      showCursorTooltip("# of asteroids", event);
    });
    tick.addEventListener("mouseleave", () => {
      hideCursorTooltip();
    });
    const y = toYForCount(value);
    tick.style.top = `${((y / height) * 100).toFixed(4)}%`;
    yAxisTicks.appendChild(tick);
  });
  yAxis.appendChild(yAxisTicks);
  const surface = document.createElement("div");
  surface.className = "compare-surface compare-surface--histogram";
  plot.appendChild(yAxis);
  plot.appendChild(surface);
  section.appendChild(plot);

  const surfaceRect = surface.getBoundingClientRect();
  if (surfaceRect.width > 0 && surfaceRect.height > 0) {
    height = Math.max(120, Math.round((width * surfaceRect.height) / surfaceRect.width));
    drawHeight = Math.max(1, height - topPad - bottomPad);
  }

  yTicks.forEach((value, index) => {
    const y = toYForCount(value);
    const tick = yAxisTicks.children[index];
    if (!(tick instanceof HTMLElement)) {
      return;
    }
    tick.style.top = `${((y / height) * 100).toFixed(4)}%`;
  });

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.classList.add("compare-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "none");

  if (showGridlines) {
    yTicks.forEach((value) => {
      const y = toYForCount(value);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", sidePad.toFixed(2));
      line.setAttribute("x2", (width - sidePad).toFixed(2));
      line.setAttribute("y1", y.toFixed(2));
      line.setAttribute("y2", y.toFixed(2));
      line.setAttribute("class", "compare-grid-line");
      svg.appendChild(line);
    });
  }

  const baselineY = topPad + drawHeight;
  histogramPoints.forEach((point, displayIndex) => {
    const displayBinCount = Number(point.binCount) / sessionDivisor;
    const y = toYForCount(displayBinCount);
    const barStart = toXForBinStart(displayIndex);
    const barEnd = toXForBinEnd(displayIndex);
    const barInset = 1.2;
    const x = Math.min(barStart, barEnd) + barInset;
    const barWidth = Math.max(1, Math.abs(barEnd - barStart) - (barInset * 2));
    const barHeight = Math.max(1.2, baselineY - y);
    const bar = document.createElementNS(ns, "rect");
    bar.setAttribute("class", "compare-histogram-bar");
    bar.setAttribute("x", x.toFixed(2));
    bar.setAttribute("y", (baselineY - barHeight).toFixed(2));
    bar.setAttribute("width", barWidth.toFixed(2));
    bar.setAttribute("height", barHeight.toFixed(2));
    const tooltipRangeStart = reverseCumulative ? point.intervalEnd : point.intervalStart;
    const tooltipRangeEnd = reverseCumulative ? point.intervalStart : point.intervalEnd;
    const detail = normalizeBySessions
      ? [
        `${ringName} | ${commodityLabel}`,
        `${tooltipRangeStart}% - ${tooltipRangeEnd}%`,
        `Bin Frequency / Session: ${formatNumber(displayBinCount, 2)}`,
        `Raw bin asteroids: ${formatNumber(point.binCount, 0)}`
      ].join("\n")
      : [
        `${ringName} | ${commodityLabel}`,
        `${tooltipRangeStart}% - ${tooltipRangeEnd}%`,
        `Bin Frequency: ${formatNumber(point.binCount, 0)}`
      ].join("\n");
    if (interactions && typeof interactions.registerBar === "function") {
      interactions.registerBar(point.index, bar);
    }
    bar.addEventListener("mouseenter", (event) => {
      if (interactions && typeof interactions.onBinHover === "function") {
        interactions.onBinHover(point.index, event);
      }
      showCursorTooltip(detail, event);
    });
    bar.addEventListener("mousemove", (event) => {
      if (interactions && typeof interactions.onBinHover === "function") {
        interactions.onBinHover(point.index, event);
      }
      showCursorTooltip(detail, event);
    });
    bar.addEventListener("mouseleave", () => {
      if (interactions && typeof interactions.onBinLeave === "function") {
        interactions.onBinLeave();
      }
      hideCursorTooltip();
    });
    svg.appendChild(bar);
  });

  surface.appendChild(svg);
  plot.addEventListener("mouseleave", () => {
    if (interactions && typeof interactions.onBinLeave === "function") {
      interactions.onBinLeave();
    }
    hideCursorTooltip();
  });
  section.appendChild(
    buildCompareBinLabelsRow(
      histogramPoints,
      reverseCumulative,
      applyAdaptiveBinLabels,
      false,
      showCursorTooltip,
      hideCursorTooltip,
      "% content range",
    )
  );
  chartPanel.appendChild(section);
}

function renderAboveThresholdGridSection(options) {
  const {
    chartPanel,
    commodityLabel,
    model,
    formatNumber,
    showCursorTooltip,
    hideCursorTooltip,
    interactions,
  } = options || {};
  const section = document.createElement("div");
  section.className = "compare-chart-section compare-chart-section--data-grid";

  const title = document.createElement("p");
  title.className = "ring-chart-title";
  title.textContent = `Cutoff Mining Plan (${commodityLabel})`;
  section.appendChild(title);

  const note = document.createElement("p");
  note.className = "compare-grid-note";
  const targetTons = Number(model && model.targetTons);
  const tonsPerPercentagePoint = Number(model && model.tonsPerPercentagePoint);
  const { button: resInfoButton, dialog: resInfoDialog } = buildResInfoDialog(
    showCursorTooltip,
    hideCursorTooltip,
  );
  note.append(
    `Projected # of prospected (#P) and mined (#M) asteroids needed to fill ${formatNumber(targetTons, 0)}t using ${formatNumber(tonsPerPercentagePoint, 2)}t per percentage point outside RES`
  );
  note.appendChild(resInfoButton);
  section.appendChild(note);
  section.appendChild(resInfoDialog);

  const {
    points,
    rows,
    prospectDisplayValues,
    mineDisplayValues,
  } = buildAboveThresholdPlanDisplayModel(model);
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "compare-empty";
    empty.textContent = "No above-threshold plan rows available.";
    section.appendChild(empty);
    chartPanel.appendChild(section);
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "compare-plan-grid";
  const linkedPane = document.createElement("div");
  linkedPane.className = "compare-plan-grid-linked-pane";
  wrapper.appendChild(linkedPane);
  if (interactions && typeof interactions.registerPane === "function") {
    interactions.registerPane(wrapper, linkedPane);
  }
  const rowDefinitions = [
    {
      label: "#P",
      title: "# Asteroids to Prospect",
      cellClassName: "compare-plan-grid-value--top",
      readValue: (_row, index) => {
        const value = prospectDisplayValues[index] && prospectDisplayValues[index].value;
        return Number.isFinite(value) ? formatNumber(value, 0) : "--";
      },
    },
    {
      label: "#M",
      title: "# Asteroids to Mine",
      cellClassName: "compare-plan-grid-value--middle",
      readValue: (_row, index) => {
        const value = mineDisplayValues[index] && mineDisplayValues[index].value;
        return Number.isFinite(value) ? formatNumber(value, 0) : "--";
      },
    },
    {
      label: "%Y",
      title: "Cutoff Yield %",
      cellClassName: "compare-plan-grid-value--bottom",
      readValue: (row) => `${formatNumber(row && row.cutoffYieldPercent, 0)}%`,
    },
  ];
  rowDefinitions.forEach((definition) => {
    const row = document.createElement("div");
    row.className = "compare-plan-grid-row";
    const label = document.createElement("div");
    label.className = "compare-plan-grid-key";
    label.textContent = definition.label;
    label.setAttribute("aria-label", definition.title);
    if (typeof showCursorTooltip === "function" && typeof hideCursorTooltip === "function") {
      label.addEventListener("mouseenter", (event) => {
        showCursorTooltip(definition.title, event);
      });
      label.addEventListener("mousemove", (event) => {
        showCursorTooltip(definition.title, event);
      });
      label.addEventListener("mouseleave", () => {
        hideCursorTooltip();
      });
    }
    const values = document.createElement("div");
    values.className = "compare-plan-grid-values";
    values.style.gridTemplateColumns = `repeat(${rows.length}, minmax(0, 1fr))`;
    rows.forEach((planRow, index) => {
      const cell = document.createElement("span");
      cell.className = `compare-plan-grid-value compare-plan-grid-value--interactive ${definition.cellClassName || ""}`.trim();
      cell.textContent = definition.readValue(planRow, index);
      const point = points[index];
      const pointIndex = Number(point && point.index);
      if (Number.isFinite(pointIndex)) {
        if (interactions && typeof interactions.registerCell === "function") {
          interactions.registerCell(pointIndex, cell);
        }
        if (interactions && typeof interactions.onCellHover === "function") {
          cell.addEventListener("mouseenter", (event) => {
            interactions.onCellHover(pointIndex, event);
          });
          cell.addEventListener("mousemove", (event) => {
            interactions.onCellHover(pointIndex, event);
          });
        }
        if (interactions && typeof interactions.onCellLeave === "function") {
          cell.addEventListener("mouseleave", () => {
            interactions.onCellLeave();
          });
        }
      }
      values.appendChild(cell);
    });
    row.appendChild(label);
    row.appendChild(values);
    wrapper.appendChild(row);
  });
  section.appendChild(wrapper);
  chartPanel.appendChild(section);
}

export function renderRingChart(options) {
  const {
    chartPanel,
    ringName,
    commodityLabel,
    model,
    selectedCrosshairKeys,
    normalizeBySessions,
    useCdf,
    reverseCumulative,
    showHistogram,
    showGridlines,
    referenceCrosshairs,
    applyAdaptiveBinLabels,
    inferStep,
    buildSmoothLinePath,
    formatNumber,
    asNumber,
    showCursorTooltip,
    hideCursorTooltip,
    formatReferenceLabelForTooltip,
  } = options || {};
  chartPanel.innerHTML = "";
  if (!model || !Array.isArray(model.points) || model.points.length === 0) {
    const note = document.createElement("p");
    note.className = "compare-empty";
    note.textContent = "No asteroids for this commodity in this ring.";
    chartPanel.appendChild(note);
    return;
  }
  const effectiveReverseCumulative = useCdf ? true : reverseCumulative;
  const displayReverseAxis = useCdf ? false : reverseCumulative;
  const effectiveNormalizeBySessions = useCdf ? false : normalizeBySessions;
  const aboveThresholdPlanDisplayModel = useCdf
    ? buildAboveThresholdPlanDisplayModel(model)
    : null;
  const cumulativeDisplayPoints = useCdf
    ? []
    : buildCumulativeDisplayPoints(model.points, displayReverseAxis);
  const planGridCellsByIndex = new Map();
  let planGridWrapper = null;
  let planGridLinkedPane = null;
  let linkedPlanGridCells = [];
  const histogramBarsByIndex = new Map();
  let linkedHistogramBars = [];
  const registerPlanGridCell = (pointIndex, node) => {
    const index = Number(pointIndex);
    if (!Number.isFinite(index) || !node) {
      return;
    }
    const existing = planGridCellsByIndex.get(index) || [];
    existing.push(node);
    planGridCellsByIndex.set(index, existing);
  };
  const clearLinkedPlanGridCells = () => {
    if (!linkedPlanGridCells.length) {
      if (planGridLinkedPane) {
        planGridLinkedPane.classList.remove("compare-plan-grid-linked-pane--visible");
      }
      return;
    }
    linkedPlanGridCells.forEach((node) => {
      if (node) {
        node.classList.remove("compare-plan-grid-value--linked");
      }
    });
    linkedPlanGridCells = [];
    if (planGridLinkedPane) {
      planGridLinkedPane.classList.remove("compare-plan-grid-linked-pane--visible");
    }
  };
  const positionLinkedPlanGridPane = (nodes) => {
    if (!planGridWrapper || !planGridLinkedPane || !Array.isArray(nodes) || !nodes.length) {
      return;
    }
    const wrapperRect = planGridWrapper.getBoundingClientRect();
    if (!wrapperRect.width || !wrapperRect.height) {
      return;
    }
    const cellRects = nodes
      .map((node) => (node ? node.getBoundingClientRect() : null))
      .filter((rect) => rect && rect.width && rect.height);
    if (!cellRects.length) {
      return;
    }
    const left = Math.min(...cellRects.map((rect) => rect.left)) - wrapperRect.left + planGridWrapper.scrollLeft;
    const right = Math.max(...cellRects.map((rect) => rect.right)) - wrapperRect.left + planGridWrapper.scrollLeft;
    const top = Math.min(...cellRects.map((rect) => rect.top)) - wrapperRect.top + planGridWrapper.scrollTop;
    const bottom = Math.max(...cellRects.map((rect) => rect.bottom)) - wrapperRect.top + planGridWrapper.scrollTop;
    planGridLinkedPane.style.left = `${left}px`;
    planGridLinkedPane.style.top = `${top}px`;
    planGridLinkedPane.style.width = `${Math.max(0, right - left)}px`;
    planGridLinkedPane.style.height = `${Math.max(0, bottom - top)}px`;
    planGridLinkedPane.classList.add("compare-plan-grid-linked-pane--visible");
  };
  const setLinkedPlanGridCellsForIndex = (pointIndex) => {
    clearLinkedPlanGridCells();
    const index = Number(pointIndex);
    if (!Number.isFinite(index)) {
      return;
    }
    const nodes = planGridCellsByIndex.get(index) || [];
    nodes.forEach((node) => {
      node.classList.add("compare-plan-grid-value--linked");
    });
    linkedPlanGridCells = nodes;
    positionLinkedPlanGridPane(nodes);
  };
  const registerPlanGridPane = (wrapper, pane) => {
    planGridWrapper = wrapper || null;
    planGridLinkedPane = pane || null;
  };
  const registerHistogramBar = (binIndex, node) => {
    const index = Number(binIndex);
    if (!Number.isFinite(index) || !node) {
      return;
    }
    const existing = histogramBarsByIndex.get(index) || [];
    existing.push(node);
    histogramBarsByIndex.set(index, existing);
  };
  const clearLinkedHistogramBars = () => {
    if (!linkedHistogramBars.length) {
      return;
    }
    linkedHistogramBars.forEach((node) => {
      if (node) {
        node.classList.remove("compare-histogram-bar--linked");
      }
    });
    linkedHistogramBars = [];
  };
  const setLinkedHistogramBarsForIndex = (binIndex) => {
    clearLinkedHistogramBars();
    const index = Number(binIndex);
    if (!Number.isFinite(index)) {
      return;
    }
    const nodes = histogramBarsByIndex.get(index) || [];
    nodes.forEach((node) => {
      node.classList.add("compare-histogram-bar--linked");
    });
    linkedHistogramBars = nodes;
  };
  let pointByIndex = new Map();
  let showLinkedCrosshairAt = (_point) => {};
  let hideLinkedCrosshair = () => {
    clearLinkedPlanGridCells();
    clearLinkedHistogramBars();
  };
  const handlePlanGridCellHover = (pointIndex, event) => {
    const index = Number(pointIndex);
    if (!Number.isFinite(index)) {
      return;
    }
    const point = pointByIndex.get(index);
    if (point) {
      showLinkedCrosshairAt(point);
      hideCursorTooltip();
      return;
    }
    setLinkedPlanGridCellsForIndex(index);
  };
  const handlePlanGridCellLeave = () => {
    hideCursorTooltip();
    hideCrosshair();
  };
  const handleHistogramBinHover = (binIndex) => {
    const index = Number(binIndex);
    if (!Number.isFinite(index)) {
      return;
    }
    const point = pointByIndex.get(index);
    if (point) {
      showLinkedCrosshairAt(point);
      return;
    }
    setLinkedHistogramBarsForIndex(index);
  };
  const handleHistogramBinLeave = () => {
    hideLinkedCrosshair();
  };
  if (showHistogram && useCdf) {
    renderAboveThresholdGridSection({
      chartPanel,
      commodityLabel,
      model,
      formatNumber,
      showCursorTooltip,
      hideCursorTooltip,
      interactions: {
        registerCell: registerPlanGridCell,
        registerPane: registerPlanGridPane,
        onCellHover: handlePlanGridCellHover,
        onCellLeave: handlePlanGridCellLeave,
      },
    });
  } else if (showHistogram) {
    renderHistogramSection({
      chartPanel,
      ringName,
      commodityLabel,
      model,
      displayPoints: cumulativeDisplayPoints,
      normalizeBySessions: effectiveNormalizeBySessions,
      reverseCumulative: displayReverseAxis,
      interactions: {
        registerBar: registerHistogramBar,
        onBinHover: handleHistogramBinHover,
        onBinLeave: handleHistogramBinLeave
      },
      showGridlines,
      inferStep,
      formatNumber,
      showCursorTooltip,
      hideCursorTooltip,
      applyAdaptiveBinLabels,
    });
  }

  const section = document.createElement("div");
  section.className = "compare-chart-section";
  const title = document.createElement("p");
  title.className = "ring-chart-title";
  title.textContent = useCdf
    ? `CDFb / Above-Threshold % (${commodityLabel})`
    : (effectiveReverseCumulative
      ? `Cumulative Frequency (${commodityLabel}) - Reversed`
      : `Cumulative Frequency (${commodityLabel})`);
  section.appendChild(title);

  const width = 1000;
  let height = 220;
  const topPad = 10;
  const bottomPad = 16;
  const sidePad = 14;
  const drawWidth = Math.max(1, width - (sidePad * 2));
  let drawHeight = Math.max(1, height - topPad - bottomPad);
  const dotRadius = 8.7;
  const referenceMarkerHalfExtent = 6.2;
  const sessionDivisor = effectiveNormalizeBySessions
    ? Math.max(1, Number(model && model.sessionsCount) || 0)
    : 1;
  const totalPopulation = Math.max(1, asNumber(model && model.asteroidsCount));
  const sourcePoints = useCdf
    ? aboveThresholdPlanDisplayModel.points
    : cumulativeDisplayPoints;
  const labelPoints = sourcePoints;
  if (!sourcePoints.length) {
    const empty = document.createElement("p");
    empty.className = "compare-empty";
    empty.textContent = useCdf
      ? "No above-threshold cutoffs available above 0%."
      : "No asteroids for this commodity in this ring.";
    section.appendChild(empty);
    chartPanel.appendChild(section);
    return;
  }
  const cdfAxisScale = useCdf
    ? buildCdfAxisScale(sourcePoints, totalPopulation)
    : null;
  const axisScaleMax = useCdf ? 1 : Math.max(
    1,
    Math.ceil((Number(model && model.yMax) / sessionDivisor) || 0)
  );
  const countAxisStep = useCdf ? null : inferStep(axisScaleMax);
  const countAxisScaleMax = useCdf
    ? cdfAxisScale.countAxisScaleMax
    : Math.max(axisScaleMax, Math.ceil(axisScaleMax / countAxisStep) * countAxisStep);
  const yTicks = useCdf ? [...cdfAxisScale.yTicks] : [];
  if (!useCdf) {
    for (let value = countAxisScaleMax; value >= 0; value -= countAxisStep) {
      yTicks.push(value);
    }
  }
  if (yTicks[yTicks.length - 1] !== 0) {
    yTicks.push(0);
  }

  const plot = document.createElement("div");
  plot.className = "compare-plot";
  const yAxis = document.createElement("div");
  yAxis.className = "compare-y-axis";
  const yAxisTicks = document.createElement("div");
  yAxisTicks.className = "compare-y-axis-ticks";
  yTicks.forEach((value) => {
    const tick = document.createElement("span");
    tick.className = "compare-y-axis-tick";
    tick.textContent = useCdf ? `${formatNumber(value * 100, 0)}%` : String(value);
    if (useCdf) {
      tick.setAttribute("aria-label", "% of asteroids above % content");
      tick.addEventListener("mouseenter", (event) => {
        showCursorTooltip("% of asteroids above % content", event);
      });
      tick.addEventListener("mousemove", (event) => {
        showCursorTooltip("% of asteroids above % content", event);
      });
      tick.addEventListener("mouseleave", () => {
        hideCursorTooltip();
      });
    } else {
      const cumulativeAxisTooltip = "# of asteroids";
      tick.setAttribute("aria-label", cumulativeAxisTooltip);
      tick.addEventListener("mouseenter", (event) => {
        showCursorTooltip(cumulativeAxisTooltip, event);
      });
      tick.addEventListener("mousemove", (event) => {
        showCursorTooltip(cumulativeAxisTooltip, event);
      });
      tick.addEventListener("mouseleave", () => {
        hideCursorTooltip();
      });
    }
    yAxisTicks.appendChild(tick);
  });
  yAxis.appendChild(yAxisTicks);
  const surface = document.createElement("div");
  surface.className = "compare-surface";
  plot.appendChild(yAxis);
  plot.appendChild(surface);
  section.appendChild(plot);

  const surfaceRect = surface.getBoundingClientRect();
  if (surfaceRect.width > 0 && surfaceRect.height > 0) {
    height = Math.max(120, Math.round((width * surfaceRect.height) / surfaceRect.width));
    drawHeight = Math.max(1, height - topPad - bottomPad);
  }

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.classList.add("compare-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "none");
  const totalBins = Math.max(1, sourcePoints.length);
  const toDisplayIndex = (index) => (
    displayReverseAxis
      ? (totalBins - index - 1)
      : index
  );
  const toXForBinIndex = (index) => sidePad + (((toDisplayIndex(index) + 0.5) / totalBins) * drawWidth);
  const toYForCount = (count) => {
    const ratio = countAxisScaleMax <= 0 ? 0 : (count / countAxisScaleMax);
    return topPad + (drawHeight * (1 - ratio));
  };

  yTicks.forEach((value, index) => {
    const y = toYForCount(value);
    const tick = yAxisTicks.children[index];
    if (!(tick instanceof HTMLElement)) {
      return;
    }
    tick.style.top = `${((y / height) * 100).toFixed(4)}%`;
  });

  if (showGridlines) {
    yTicks.forEach((value) => {
      const y = toYForCount(value);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", sidePad.toFixed(2));
      line.setAttribute("x2", (width - sidePad).toFixed(2));
      line.setAttribute("y1", y.toFixed(2));
      line.setAttribute("y2", y.toFixed(2));
      line.setAttribute("class", "compare-grid-line");
      svg.appendChild(line);
    });
  }

  const coordinates = sourcePoints.map((point, displayIndex) => {
    const displayBinCount = Number(point.binCount) / sessionDivisor;
    const rawDisplayTotal = effectiveReverseCumulative
      ? Number(point.totalReverse)
      : Number(point.totalForward);
    const actualDisplayTotal = useCdf
      ? (rawDisplayTotal / totalPopulation)
      : (rawDisplayTotal / sessionDivisor);
    return {
      ...point,
      planDisplayIndex: displayIndex,
      displayBinCount,
      displayTotal: actualDisplayTotal,
      actualDisplayTotal,
      rawDisplayTotal,
      isTerminalThresholdPoint: useCdf
        && displayIndex === (sourcePoints.length - 1)
        && rawDisplayTotal === 0,
      x: toXForBinIndex(displayIndex),
      y: toYForCount(actualDisplayTotal)
    };
  });
  const interpolatedDisplayTotals = interpolateMissingValuesBetweenRealBins({
    entries: coordinates,
    readValue: (point) => point && point.actualDisplayTotal,
    isRealEntry: (point) => !!(point && point.hasRealData),
    strategy: useCdf ? "linear" : (displayReverseAxis ? "next" : "previous"),
  });
  interpolatedDisplayTotals.forEach((entry, index) => {
    const point = coordinates[index];
    if (!point) {
      return;
    }
    const nextDisplayTotal = Number.isFinite(entry && entry.value)
      ? entry.value
      : point.actualDisplayTotal;
    point.displayTotal = point.syntheticTrailingPoint ? 0 : nextDisplayTotal;
    point.inferredDisplayTotal = !!(entry && entry.inferred) || !!point.syntheticTrailingPoint;
    point.y = toYForCount(nextDisplayTotal);
    if (point.syntheticTrailingPoint) {
      point.y = toYForCount(0);
    }
  });
  pointByIndex = new Map();
  coordinates.forEach((point) => {
    const pointIndex = Number(point && point.index);
    if (!Number.isFinite(pointIndex)) {
      return;
    }
    pointByIndex.set(pointIndex, point);
  });

  const pathData = buildSmoothLinePath(coordinates);
  const line = document.createElementNS(ns, "path");
  line.setAttribute("class", "compare-line");
  line.setAttribute("d", pathData);
  svg.appendChild(line);

  const referenceMetrics = model;

  const selectedKeys = selectedCrosshairKeys instanceof Set ? selectedCrosshairKeys : new Set();
  const maxPercentValue = Math.max(1, asNumber(model.xMax));
  const minThresholdValue = useCdf && sourcePoints.length
    ? Math.max(0, Number(sourcePoints[0].intervalStart))
    : 0;
  const maxThresholdValue = useCdf && sourcePoints.length
    ? Math.max(minThresholdValue, Number(sourcePoints[sourcePoints.length - 1].intervalStart))
    : maxPercentValue;
  const totalCount = useCdf
    ? 1
    : Math.max(
      1,
      coordinates.reduce((peak, point) => Math.max(peak, asNumber(point.displayTotal)), 0),
      (asNumber(model.asteroidsCount) / sessionDivisor)
    );
  const toXForPercentValue = (rawValue) => {
    const value = Number(rawValue);
    if (!Number.isFinite(value)) {
      return null;
    }
    if (useCdf) {
      if (sourcePoints.length <= 1) {
        return coordinates.length ? coordinates[0].x : null;
      }
      const clamped = Math.max(minThresholdValue, Math.min(maxThresholdValue, value));
      const leftX = coordinates[0].x;
      const rightX = coordinates[coordinates.length - 1].x;
      const span = maxThresholdValue - minThresholdValue;
      const ratio = span > 0 ? ((clamped - minThresholdValue) / span) : 0;
      return leftX + ((rightX - leftX) * ratio);
    }
    const clamped = Math.max(0, Math.min(maxPercentValue, value));
    const ratio = clamped / maxPercentValue;
    const displayRatio = displayReverseAxis ? (1 - ratio) : ratio;
    return sidePad + (displayRatio * drawWidth);
  };
  const getYOnLineForX = (targetX) => {
    if (!Number.isFinite(targetX) || !coordinates.length) {
      return null;
    }
    if (coordinates.length === 1) {
      return Number.isFinite(coordinates[0].y) ? coordinates[0].y : null;
    }
    for (let index = 1; index < coordinates.length; index += 1) {
      const left = coordinates[index - 1];
      const right = coordinates[index];
      const minX = Math.min(left.x, right.x);
      const maxX = Math.max(left.x, right.x);
      if (targetX < minX || targetX > maxX) {
        continue;
      }
      const span = right.x - left.x;
      if (!Number.isFinite(span) || Math.abs(span) <= 0.000001) {
        return right.y;
      }
      const ratio = Math.max(0, Math.min(1, (targetX - left.x) / span));
      return left.y + ((right.y - left.y) * ratio);
    }
    let nearest = coordinates[0];
    let nearestDistance = Math.abs(nearest.x - targetX);
    for (let index = 1; index < coordinates.length; index += 1) {
      const candidate = coordinates[index];
      const distance = Math.abs(candidate.x - targetX);
      if (distance < nearestDistance) {
        nearest = candidate;
        nearestDistance = distance;
      }
    }
    return nearest.y;
  };
  const referencePoints = [];
  const references = Array.isArray(referenceCrosshairs) ? referenceCrosshairs : [];
  references.forEach((entry) => {
    if (!selectedKeys.has(entry.key)) {
      return;
    }
    const metricValue = Number(referenceMetrics[entry.metricKey]);
    const quantile = Number(entry.quantile);
    const clampedQuantile = Number.isFinite(quantile) ? Math.max(0, Math.min(1, quantile)) : 0;
    const referenceCount = Number.isFinite(quantile) ? (totalCount * clampedQuantile) : null;
    const referenceX = toXForPercentValue(metricValue);
    if (!Number.isFinite(referenceX)) {
      return;
    }
    const yOnLine = getYOnLineForX(referenceX);
    const referenceY = Number.isFinite(yOnLine)
      ? yOnLine
      : (Number.isFinite(referenceCount) ? toYForCount(referenceCount) : toYForCount(0));
    referencePoints.push({ entry, referenceX, referenceY, metricValue });
  });

  const overlapTolerance = 1.5;
  const referenceGroups = [];
  referencePoints.forEach((point) => {
    const existing = referenceGroups.find(
      (group) => Math.abs(group.referenceX - point.referenceX) <= overlapTolerance
        && Math.abs(group.referenceY - point.referenceY) <= overlapTolerance
    );
    if (existing) {
      existing.items.push(point);
      return;
    }
    referenceGroups.push({
      referenceX: point.referenceX,
      referenceY: point.referenceY,
      items: [point]
    });
  });

  referenceGroups.forEach((group) => {
    const lead = group.items[0];
    const lineClass = `compare-reference-line compare-reference-line--${lead.entry.key}`;
    const horizontal = document.createElementNS(ns, "line");
    horizontal.setAttribute("class", lineClass);
    horizontal.setAttribute("x1", sidePad.toFixed(2));
    horizontal.setAttribute("y1", group.referenceY.toFixed(2));
    horizontal.setAttribute("x2", group.referenceX.toFixed(2));
    horizontal.setAttribute("y2", group.referenceY.toFixed(2));
    svg.appendChild(horizontal);

    const vertical = document.createElementNS(ns, "line");
    vertical.setAttribute("class", lineClass);
    vertical.setAttribute("x1", group.referenceX.toFixed(2));
    vertical.setAttribute("y1", group.referenceY.toFixed(2));
    vertical.setAttribute("x2", group.referenceX.toFixed(2));
    vertical.setAttribute("y2", (topPad + drawHeight).toFixed(2));
    svg.appendChild(vertical);

    const label = document.createElementNS(ns, "text");
    const labelClasses = [
      "compare-reference-label",
      `compare-reference-label--${lead.entry.key}`
    ];
    if (displayReverseAxis) {
      labelClasses.push("compare-reference-label--reverse");
    }
    label.setAttribute("class", labelClasses.join(" "));
    const includesAverage = group.items.some((item) => item && item.entry && item.entry.key === "avg");
    const labelOffsetX = displayReverseAxis
      ? (includesAverage ? -10 : -16)
      : 10;
    const labelOffsetY = displayReverseAxis
      ? (includesAverage ? -26 : -16)
      : 6;
    const maxLabelWidth = 72;
    const clampedX = displayReverseAxis
      ? Math.max(sidePad + maxLabelWidth, Math.min(width - sidePad - 6, group.referenceX + labelOffsetX))
      : Math.max(sidePad + 6, Math.min(width - sidePad - maxLabelWidth, group.referenceX + labelOffsetX));
    const clampedY = Math.max(topPad + 2, Math.min((topPad + drawHeight) - 8, group.referenceY + labelOffsetY));
    label.setAttribute("x", clampedX.toFixed(2));
    label.setAttribute("y", clampedY.toFixed(2));
    label.textContent = group.items.map((item) => item.entry.label).join(" & ");
    svg.appendChild(label);

    const markerClass = `compare-reference-marker-line compare-reference-marker-line--${lead.entry.key}`;
    const markerSize = referenceMarkerHalfExtent;
    const markerLeft = group.referenceX - markerSize;
    const markerRight = group.referenceX + markerSize;
    const markerTop = group.referenceY - markerSize;
    const markerBottom = group.referenceY + markerSize;
    const markerTooltipText = [
      `${ringName} | ${commodityLabel}`,
      ...group.items.map((item) => {
        if (typeof formatReferenceLabelForTooltip === "function") {
          return `${formatReferenceLabelForTooltip(item.entry.label)}: ${formatNumber(item.metricValue, 2)}%`;
        }
        return `${item.entry.label}: ${formatNumber(item.metricValue, 2)}%`;
      })
    ].join("\n");
    const bindMarkerHover = (node) => {
      node.addEventListener("mouseenter", (event) => {
        clearLinkedHighlights();
        hCross.setAttribute("x1", sidePad.toFixed(2));
        hCross.setAttribute("y1", group.referenceY.toFixed(2));
        hCross.setAttribute("x2", group.referenceX.toFixed(2));
        hCross.setAttribute("y2", group.referenceY.toFixed(2));
        hCross.style.opacity = "1";

        vCross.setAttribute("x1", group.referenceX.toFixed(2));
        vCross.setAttribute("y1", group.referenceY.toFixed(2));
        vCross.setAttribute("x2", group.referenceX.toFixed(2));
        vCross.setAttribute("y2", (topPad + drawHeight).toFixed(2));
        vCross.style.opacity = "1";
        showCursorTooltip(markerTooltipText, event);
      });
      node.addEventListener("mousemove", (event) => {
        showCursorTooltip(markerTooltipText, event);
      });
      node.addEventListener("mouseleave", () => {
        hCross.style.opacity = "0";
        vCross.style.opacity = "0";
        hideCursorTooltip();
      });
    };

    const markerA = document.createElementNS(ns, "line");
    markerA.setAttribute("class", markerClass);
    markerA.setAttribute("x1", markerLeft.toFixed(2));
    markerA.setAttribute("y1", markerTop.toFixed(2));
    markerA.setAttribute("x2", markerRight.toFixed(2));
    markerA.setAttribute("y2", markerBottom.toFixed(2));
    bindMarkerHover(markerA);
    svg.appendChild(markerA);

    const markerB = document.createElementNS(ns, "line");
    markerB.setAttribute("class", markerClass);
    markerB.setAttribute("x1", markerLeft.toFixed(2));
    markerB.setAttribute("y1", markerBottom.toFixed(2));
    markerB.setAttribute("x2", markerRight.toFixed(2));
    markerB.setAttribute("y2", markerTop.toFixed(2));
    bindMarkerHover(markerB);
    svg.appendChild(markerB);
  });

  const snapPoints = [
    ...coordinates.map((point) => ({ kind: "bin", ...point })),
    ...referenceGroups.map((group) => ({
      kind: "reference",
      x: group.referenceX,
      y: group.referenceY,
      labels: group.items.map((item) => item.entry.label),
      values: group.items.map((item) => item.metricValue)
    }))
  ];

  const hitbox = document.createElementNS(ns, "path");
  hitbox.setAttribute("class", "compare-line-hitbox");
  hitbox.setAttribute("d", pathData);
  svg.appendChild(hitbox);

  const hCross = document.createElementNS(ns, "line");
  hCross.setAttribute("class", "compare-crosshair");
  svg.appendChild(hCross);

  const vCross = document.createElementNS(ns, "line");
  vCross.setAttribute("class", "compare-crosshair");
  svg.appendChild(vCross);

  const findNearestPoint = (event) => {
    if (!snapPoints.length) {
      return null;
    }
    const rect = svg.getBoundingClientRect();
    if (!rect.width) {
      return snapPoints[0];
    }
    const ratio = (event.clientX - rect.left) / rect.width;
    const localX = ratio * width;
    let nearest = snapPoints[0];
    let nearestDistance = Math.abs(nearest.x - localX);
    for (let index = 1; index < snapPoints.length; index += 1) {
      const candidate = snapPoints[index];
      const distance = Math.abs(candidate.x - localX);
      if (distance < nearestDistance) {
        nearest = candidate;
        nearestDistance = distance;
      }
    }
    return nearest;
  };

  const pointDotsByIndex = new Map();
  let linkedDots = [];
  const clearLinkedDots = () => {
    if (!linkedDots.length) {
      return;
    }
    linkedDots.forEach((dot) => {
      if (dot) {
        dot.classList.remove("compare-dot--linked");
      }
    });
    linkedDots = [];
  };
  const setLinkedDotsForPoint = (point) => {
    clearLinkedDots();
    const pointIndex = Number(point && point.index);
    if (!Number.isFinite(pointIndex)) {
      return;
    }
    const nodes = pointDotsByIndex.get(pointIndex) || [];
    nodes.forEach((dot) => {
      dot.classList.add("compare-dot--linked");
    });
    linkedDots = nodes;
  };
  const clearLinkedHighlights = () => {
    clearLinkedDots();
    clearLinkedPlanGridCells();
    clearLinkedHistogramBars();
  };
  const setLinkedHighlightsForPoint = (point) => {
    setLinkedDotsForPoint(point);
    const pointIndex = Number(point && point.index);
    if (!Number.isFinite(pointIndex)) {
      clearLinkedPlanGridCells();
      clearLinkedHistogramBars();
      return;
    }
    setLinkedPlanGridCellsForIndex(pointIndex);
    setLinkedHistogramBarsForIndex(pointIndex);
  };

  const showPointTooltip = (point, event) => {
    if (point.kind === "reference") {
      const detail = [
        `${ringName} | ${commodityLabel}`,
        ...point.labels.map((label, idx) => {
          const userLabel = typeof formatReferenceLabelForTooltip === "function"
            ? formatReferenceLabelForTooltip(label)
            : label;
          return `${userLabel}: ${formatNumber(point.values[idx], 2)}%`;
        })
      ].join("\n");
      showCursorTooltip(detail, event);
      return;
    }
    const tooltipRangeStart = displayReverseAxis ? point.intervalEnd : point.intervalStart;
    const tooltipRangeEnd = displayReverseAxis ? point.intervalStart : point.intervalEnd;
    const detail = useCdf
      ? (() => {
        const cutoffLabel = formatThresholdLabel(point, displayReverseAxis);
        const cutoffValue = Number(point && point.intervalStart);
        const planRows = Array.isArray(model && model.aboveThresholdPlanRows)
          ? model.aboveThresholdPlanRows
          : [];
        const matchedPlanRow = planRows.find((row) => Number(row && row.cutoffYieldPercent) === cutoffValue);
        const planDisplayIndex = Number(point && point.planDisplayIndex);
        const inferredProspectValue = Number.isFinite(planDisplayIndex)
          ? Number(
            aboveThresholdPlanDisplayModel
            && aboveThresholdPlanDisplayModel.prospectDisplayValues
            && aboveThresholdPlanDisplayModel.prospectDisplayValues[planDisplayIndex]
            && aboveThresholdPlanDisplayModel.prospectDisplayValues[planDisplayIndex].value
          )
          : Number.NaN;
        const inferredMineValue = Number.isFinite(planDisplayIndex)
          ? Number(
            aboveThresholdPlanDisplayModel
            && aboveThresholdPlanDisplayModel.mineDisplayValues
            && aboveThresholdPlanDisplayModel.mineDisplayValues[planDisplayIndex]
            && aboveThresholdPlanDisplayModel.mineDisplayValues[planDisplayIndex].value
          )
          : Number.NaN;
        const asteroidsToProspect = point.syntheticTrailingPoint
          ? 0
          : (point.inferredDisplayTotal
            ? inferredProspectValue
            : Number(matchedPlanRow && matchedPlanRow.asteroidsToProspect));
        const asteroidsToMine = point.syntheticTrailingPoint
          ? 0
          : (point.inferredDisplayTotal
            ? inferredMineValue
            : Number(matchedPlanRow && matchedPlanRow.asteroidsToMine));
        const targetTons = Number(model && model.targetTons);
        const lead = point.inferredDisplayTotal ? "Estimated: " : "";
        const planMessage = (
          asteroidsToProspect === 0 && asteroidsToMine === 0
            ? "Good luck CMDR! At this rate, you'll never fill your cargo hold."
            : `You will need to prospect ${Number.isFinite(asteroidsToProspect) ? formatNumber(asteroidsToProspect, 0) : "--"} asteroids and mine ${Number.isFinite(asteroidsToMine) ? formatNumber(asteroidsToMine, 0) : "--"} asteroids to get ${Number.isFinite(targetTons) ? formatNumber(targetTons, 0) : "--"} tons of cargo.`
        );
        return [
          `${ringName} | ${commodityLabel}`,
          `${lead}${formatNumber(point.displayTotal * 100, 1)}% of asteroids have more than ${cutoffLabel}% ${commodityLabel} content.`,
          planMessage
        ].join("\n");
      })()
      : effectiveNormalizeBySessions
      ? (() => {
        const detailLines = [
          `${ringName} | ${commodityLabel}`,
          `${tooltipRangeStart}% - ${tooltipRangeEnd}%`,
          `Cumulative Frequency / Session: ${formatNumber(point.displayTotal, 2)}`,
          `Bin Frequency / Session: ${formatNumber(point.displayBinCount, 2)}`,
        ];
        if (Number(model && model.sessionsCount) > 1) {
          detailLines.push(`Raw cumulative asteroids: ${formatNumber(point.rawDisplayTotal, 0)}`);
          detailLines.push(`Raw bin asteroids: ${formatNumber(point.binCount, 0)}`);
        }
        return detailLines.join("\n");
      })()
      : [
        `${ringName} | ${commodityLabel}`,
        `${tooltipRangeStart}% - ${tooltipRangeEnd}%`,
        `Cumulative Frequency: ${formatNumber(point.rawDisplayTotal, 0)}`,
        `Bin Frequency: ${formatNumber(point.binCount, 0)}`
      ].join("\n");
    showCursorTooltip(detail, event);
  };

  showLinkedCrosshairAt = (point) => {
    setLinkedHighlightsForPoint(point);
    hCross.setAttribute("x1", sidePad.toFixed(2));
    hCross.setAttribute("y1", point.y.toFixed(2));
    hCross.setAttribute("x2", point.x.toFixed(2));
    hCross.setAttribute("y2", point.y.toFixed(2));
    hCross.style.opacity = "1";

    vCross.setAttribute("x1", point.x.toFixed(2));
    vCross.setAttribute("y1", point.y.toFixed(2));
    vCross.setAttribute("x2", point.x.toFixed(2));
    vCross.setAttribute("y2", (topPad + drawHeight).toFixed(2));
    vCross.style.opacity = "1";
  };

  const showCrosshairAt = (point, event) => {
    showLinkedCrosshairAt(point);

    showPointTooltip(point, event);
  };

  hideLinkedCrosshair = () => {
    hCross.style.opacity = "0";
    vCross.style.opacity = "0";
    clearLinkedHighlights();
  };

  const hideCrosshair = () => {
    hideLinkedCrosshair();
    hideCursorTooltip();
  };

  hitbox.addEventListener("mouseenter", (event) => {
    const nearest = findNearestPoint(event);
    if (nearest) {
      showCrosshairAt(nearest, event);
    }
  });
  hitbox.addEventListener("mousemove", (event) => {
    const nearest = findNearestPoint(event);
    if (nearest) {
      showCrosshairAt(nearest, event);
    }
  });
  hitbox.addEventListener("mouseleave", () => {
    hideCrosshair();
  });

  coordinates.forEach((point) => {
    const bindHoverHandlers = (node) => {
      node.addEventListener("mouseenter", (event) => {
        showCrosshairAt(point, event);
      });
      node.addEventListener("mousemove", (event) => {
        showCrosshairAt(point, event);
      });
      node.addEventListener("mouseleave", () => {
        hideCrosshair();
      });
    };

    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("class", "compare-dot");
    if (isNoDataDot(point, useCdf)) {
      dot.classList.add("compare-dot--no-data");
    }
    dot.setAttribute("cx", point.x.toFixed(2));
    dot.setAttribute("cy", point.y.toFixed(2));
    dot.setAttribute("r", dotRadius.toFixed(2));
    const pointIndex = Number(point.index);
    if (Number.isFinite(pointIndex)) {
      const nodes = pointDotsByIndex.get(pointIndex) || [];
      nodes.push(dot);
      pointDotsByIndex.set(pointIndex, nodes);
    }
    bindHoverHandlers(dot);
    svg.appendChild(dot);
  });

  surface.appendChild(svg);
  plot.addEventListener("mouseleave", hideCrosshair);

  section.appendChild(
    buildCompareBinLabelsRow(
      labelPoints,
      displayReverseAxis,
      applyAdaptiveBinLabels,
      useCdf,
      showCursorTooltip,
      hideCursorTooltip,
      useCdf ? "% content" : "% content range",
    )
  );
  chartPanel.appendChild(section);
}
