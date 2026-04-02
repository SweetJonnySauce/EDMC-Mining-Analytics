function buildCompareBinLabelsRow(points, reverseCumulative, applyAdaptiveBinLabels) {
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
    labelTexts[index] = `${labelRangeStart}-${labelRangeEnd}%`;
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

function renderHistogramSection(options) {
  const {
    chartPanel,
    ringName,
    commodityLabel,
    model,
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
  const totalBins = Math.max(1, model.points.length);
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
  const displayPeak = model.points.reduce((peak, point) => (
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
  model.points.forEach((point) => {
    const displayBinCount = Number(point.binCount) / sessionDivisor;
    const y = toYForCount(displayBinCount);
    const barStart = toXForBinStart(point.index);
    const barEnd = toXForBinEnd(point.index);
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
  section.appendChild(buildCompareBinLabelsRow(model.points, reverseCumulative, applyAdaptiveBinLabels));
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
  const histogramBarsByIndex = new Map();
  let linkedHistogramBars = [];
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
    clearLinkedHistogramBars();
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
  if (showHistogram) {
    renderHistogramSection({
      chartPanel,
      ringName,
      commodityLabel,
      model,
      normalizeBySessions,
      reverseCumulative,
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
  title.textContent = reverseCumulative
    ? `Cumulative Frequency (${commodityLabel}) - Reversed`
    : `Cumulative Frequency (${commodityLabel})`;
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
  const sessionDivisor = normalizeBySessions
    ? Math.max(1, Number(model && model.sessionsCount) || 0)
    : 1;
  const normalizedModelYMax = Number(model && model.yMax) / sessionDivisor;
  const countAxisMaxInt = Math.max(1, Math.ceil(normalizedModelYMax));
  const countAxisStep = inferStep(countAxisMaxInt);
  const countAxisScaleMax = Math.max(countAxisMaxInt, Math.ceil(countAxisMaxInt / countAxisStep) * countAxisStep);
  const yTicks = [];
  for (let value = countAxisScaleMax; value >= 0; value -= countAxisStep) {
    yTicks.push(value);
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
    tick.textContent = String(value);
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
  const totalBins = Math.max(1, model.points.length);
  const toDisplayIndex = (index) => (
    reverseCumulative
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

  const coordinates = model.points.map((point) => {
    const displayBinCount = Number(point.binCount) / sessionDivisor;
    const rawDisplayTotal = reverseCumulative
      ? Number(point.totalReverse)
      : Number(point.totalForward);
    const displayTotal = rawDisplayTotal / sessionDivisor;
    return {
      ...point,
      displayBinCount,
      displayTotal,
      rawDisplayTotal,
      x: toXForBinIndex(point.index),
      y: toYForCount(displayTotal)
    };
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
  const totalCount = Math.max(
    1,
    coordinates.reduce((peak, point) => Math.max(peak, asNumber(point.displayTotal)), 0),
    (asNumber(model.asteroidsCount) / sessionDivisor)
  );
  const toXForPercentValue = (rawValue) => {
    const value = Number(rawValue);
    if (!Number.isFinite(value)) {
      return null;
    }
    const clamped = Math.max(0, Math.min(maxPercentValue, value));
    const ratio = clamped / maxPercentValue;
    const displayRatio = reverseCumulative ? (1 - ratio) : ratio;
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
    if (reverseCumulative) {
      labelClasses.push("compare-reference-label--reverse");
    }
    label.setAttribute("class", labelClasses.join(" "));
    const includesAverage = group.items.some((item) => item && item.entry && item.entry.key === "avg");
    const labelOffsetX = reverseCumulative
      ? (includesAverage ? -10 : -16)
      : 10;
    const labelOffsetY = reverseCumulative
      ? (includesAverage ? -26 : -16)
      : 6;
    const maxLabelWidth = 72;
    const clampedX = reverseCumulative
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
    clearLinkedHistogramBars();
  };
  const setLinkedHighlightsForPoint = (point) => {
    setLinkedDotsForPoint(point);
    const pointIndex = Number(point && point.index);
    if (!Number.isFinite(pointIndex)) {
      clearLinkedHistogramBars();
      return;
    }
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
    const tooltipRangeStart = reverseCumulative ? point.intervalEnd : point.intervalStart;
    const tooltipRangeEnd = reverseCumulative ? point.intervalStart : point.intervalEnd;
    const detail = normalizeBySessions
      ? [
        `${ringName} | ${commodityLabel}`,
        `${tooltipRangeStart}% - ${tooltipRangeEnd}%`,
        `Cumulative Frequency / Session: ${formatNumber(point.displayTotal, 2)}`,
        `Bin Frequency / Session: ${formatNumber(point.displayBinCount, 2)}`,
        `Raw cumulative asteroids: ${formatNumber(point.rawDisplayTotal, 0)}`,
        `Raw bin asteroids: ${formatNumber(point.binCount, 0)}`
      ].join("\n")
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
    if (Number(point.displayBinCount) <= 0) {
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

  section.appendChild(buildCompareBinLabelsRow(model.points, reverseCumulative, applyAdaptiveBinLabels));
  chartPanel.appendChild(section);
}
