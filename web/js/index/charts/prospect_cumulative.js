export function renderProspectCumulativeFrequencyChart(options) {
  const {
    chartProspectCumulativeFrequency,
    model,
    prospectFrequencyReverseCumulative,
    prospectFrequencyShowAverageReference,
    materialPercentShowGridlines,
    applyAdaptiveBinLabels,
    buildSmoothLinePath,
    formatNumber,
    showCursorTooltip,
    hideCursorTooltip,
    clearCrossChartHoverHighlights,
    highlightFromCumulativePointEntry,
    normalizeCommodityKey,
    onAverageReferenceChange,
  } = options || {};
  if (!(chartProspectCumulativeFrequency instanceof HTMLElement)) {
    return {
      commodityKey: "",
      points: [],
      showLinkedCrosshair: null,
      hideLinkedCrosshair: null
    };
  }
  const applyLabels = typeof applyAdaptiveBinLabels === "function"
    ? applyAdaptiveBinLabels
    : (() => 1);
  const buildPath = typeof buildSmoothLinePath === "function"
    ? buildSmoothLinePath
    : (() => "");
  const formatNumeric = typeof formatNumber === "function"
    ? formatNumber
    : ((value) => String(value ?? ""));
  const showTooltip = typeof showCursorTooltip === "function"
    ? showCursorTooltip
    : (() => {});
  const hideTooltip = typeof hideCursorTooltip === "function"
    ? hideCursorTooltip
    : (() => {});
  const clearHighlights = typeof clearCrossChartHoverHighlights === "function"
    ? clearCrossChartHoverHighlights
    : (() => {});
  const highlightPoint = typeof highlightFromCumulativePointEntry === "function"
    ? highlightFromCumulativePointEntry
    : (() => {});
  const normalizeCommodity = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const onAverageToggle = typeof onAverageReferenceChange === "function"
    ? onAverageReferenceChange
    : (() => {});

  const layout = document.createElement("div");
  layout.className = "prospect-frequency-layout";
  const plot = document.createElement("div");
  plot.className = "prospect-frequency-plot";
  const yAxis = document.createElement("div");
  yAxis.className = "timeline-y-axis";
  const computeAxisStep = (axisMaxInt) => {
    const targetTickCount = 7;
    const minStep = Math.max(1, axisMaxInt / (targetTickCount - 1));
    let magnitude = Math.pow(10, Math.floor(Math.log10(minStep)));
    if (!Number.isFinite(magnitude) || magnitude <= 0) {
      magnitude = 1;
    }
    let step = 0;
    for (let attempts = 0; attempts < 8 && step <= 0; attempts += 1) {
      [1, 2, 5].forEach((multiplier) => {
        const candidate = multiplier * magnitude;
        if (candidate >= minStep && (step <= 0 || candidate < step)) {
          step = candidate;
        }
      });
      magnitude *= 10;
    }
    return step > 0 ? step : 1;
  };
  const countAxisMaxInt = Math.max(1, Math.ceil(model.yMax));
  const countAxisStep = computeAxisStep(countAxisMaxInt);
  const countAxisScaleMax = Math.max(countAxisMaxInt, Math.ceil(countAxisMaxInt / countAxisStep) * countAxisStep);
  const yTickValues = [];
  for (let value = countAxisScaleMax; value >= 0; value -= countAxisStep) {
    yTickValues.push(value);
  }
  if (yTickValues[yTickValues.length - 1] !== 0) {
    yTickValues.push(0);
  }
  yTickValues.forEach((value) => {
    const tick = document.createElement("span");
    tick.textContent = String(value);
    yAxis.appendChild(tick);
  });

  const surface = document.createElement("div");
  surface.className = "prospect-frequency-surface";

  const width = 1000;
  const height = 240;
  const topPad = 10;
  const bottomPad = 18;
  const sidePad = 14;
  const drawWidth = Math.max(1, width - (sidePad * 2));
  const drawHeight = Math.max(1, height - topPad - bottomPad);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.classList.add("prospect-frequency-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "none");

  const totalBins = Math.max(1, model.points.length);
  const toDisplayIndex = (index) => (
    prospectFrequencyReverseCumulative
      ? (totalBins - index - 1)
      : index
  );
  const toXForBinIndex = (index) => sidePad + (((toDisplayIndex(index) + 0.5) / totalBins) * drawWidth);
  const toYForCount = (count) => {
    const ratio = countAxisScaleMax <= 0 ? 0 : (count / countAxisScaleMax);
    return topPad + (drawHeight * (1 - ratio));
  };
  if (materialPercentShowGridlines) {
    yTickValues.forEach((value) => {
      const y = toYForCount(value);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", sidePad.toFixed(2));
      line.setAttribute("x2", (width - sidePad).toFixed(2));
      line.setAttribute("y1", y.toFixed(2));
      line.setAttribute("y2", y.toFixed(2));
      line.setAttribute("class", "prospect-frequency-grid-line");
      svg.appendChild(line);
    });
  }
  const coordinates = model.points.map((point) => ({
    ...point,
    x: toXForBinIndex(point.index),
    y: toYForCount(point.total)
  }));
  const cumulativePointByIndex = new Map();
  coordinates.forEach((point, pointIndex) => {
    cumulativePointByIndex.set(point.index, {
      index: point.index,
      intervalStart: point.intervalStart,
      intervalEnd: point.intervalEnd,
      isLast: pointIndex === (coordinates.length - 1),
      dots: [],
      currentDots: [],
      x: point.x,
      y: point.y
    });
  });

  const pathData = buildPath(coordinates);
  const line = document.createElementNS(ns, "path");
  line.setAttribute("class", "prospect-frequency-line");
  line.setAttribute("d", pathData);
  svg.appendChild(line);

  const toXForPercentValue = (rawValue) => {
    const value = Number(rawValue);
    if (!Number.isFinite(value)) {
      return null;
    }
    const maxXValue = Math.max(1, Number(model.xMax) || 1);
    const clamped = Math.max(0, Math.min(maxXValue, value));
    const ratio = clamped / maxXValue;
    const displayRatio = prospectFrequencyReverseCumulative ? (1 - ratio) : ratio;
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
  let averageReferencePoint = null;
  if (prospectFrequencyShowAverageReference) {
    const averageMetricValue = Number(model.averageYield);
    const averageX = toXForPercentValue(averageMetricValue);
    const averageY = getYOnLineForX(averageX);
    if (Number.isFinite(averageX) && Number.isFinite(averageY)) {
      averageReferencePoint = {
        kind: "average-reference",
        x: averageX,
        y: averageY,
        averageYield: model.averageYield
      };
      const avgHCross = document.createElementNS(ns, "line");
      avgHCross.setAttribute("class", "prospect-frequency-crosshair");
      avgHCross.setAttribute("x1", sidePad.toFixed(2));
      avgHCross.setAttribute("y1", averageY.toFixed(2));
      avgHCross.setAttribute("x2", averageX.toFixed(2));
      avgHCross.setAttribute("y2", averageY.toFixed(2));
      avgHCross.style.opacity = "1";
      svg.appendChild(avgHCross);

      const avgVCross = document.createElementNS(ns, "line");
      avgVCross.setAttribute("class", "prospect-frequency-crosshair");
      avgVCross.setAttribute("x1", averageX.toFixed(2));
      avgVCross.setAttribute("y1", averageY.toFixed(2));
      avgVCross.setAttribute("x2", averageX.toFixed(2));
      avgVCross.setAttribute("y2", (topPad + drawHeight).toFixed(2));
      avgVCross.style.opacity = "1";
      svg.appendChild(avgVCross);

      const markerSize = 6.2;
      const markerA = document.createElementNS(ns, "line");
      markerA.setAttribute("class", "prospect-frequency-average-marker");
      markerA.setAttribute("x1", (averageX - markerSize).toFixed(2));
      markerA.setAttribute("y1", (averageY - markerSize).toFixed(2));
      markerA.setAttribute("x2", (averageX + markerSize).toFixed(2));
      markerA.setAttribute("y2", (averageY + markerSize).toFixed(2));
      svg.appendChild(markerA);

      const markerB = document.createElementNS(ns, "line");
      markerB.setAttribute("class", "prospect-frequency-average-marker");
      markerB.setAttribute("x1", (averageX - markerSize).toFixed(2));
      markerB.setAttribute("y1", (averageY + markerSize).toFixed(2));
      markerB.setAttribute("x2", (averageX + markerSize).toFixed(2));
      markerB.setAttribute("y2", (averageY - markerSize).toFixed(2));
      svg.appendChild(markerB);

      const avgLabel = document.createElementNS(ns, "text");
      const avgLabelClasses = ["prospect-frequency-average-label"];
      if (prospectFrequencyReverseCumulative) {
        avgLabelClasses.push("prospect-frequency-average-label--reverse");
      }
      avgLabel.setAttribute("class", avgLabelClasses.join(" "));
      const avgLabelOffsetX = prospectFrequencyReverseCumulative ? -16 : 10;
      const avgLabelOffsetY = prospectFrequencyReverseCumulative ? -16 : 6;
      const avgLabelMaxWidth = 60;
      const avgLabelX = prospectFrequencyReverseCumulative
        ? Math.max(sidePad + avgLabelMaxWidth, Math.min(width - sidePad - 6, averageX + avgLabelOffsetX))
        : Math.max(sidePad + 6, Math.min(width - sidePad - avgLabelMaxWidth, averageX + avgLabelOffsetX));
      const avgLabelY = Math.max(topPad + 2, Math.min((topPad + drawHeight) - 8, averageY + avgLabelOffsetY));
      avgLabel.setAttribute("x", avgLabelX.toFixed(2));
      avgLabel.setAttribute("y", avgLabelY.toFixed(2));
      avgLabel.textContent = "Avg";
      svg.appendChild(avgLabel);
    }
  }

  const hitbox = document.createElementNS(ns, "path");
  hitbox.setAttribute("class", "prospect-frequency-line-hitbox");
  hitbox.setAttribute("d", pathData);
  svg.appendChild(hitbox);

  const hCross = document.createElementNS(ns, "line");
  hCross.setAttribute("class", "prospect-frequency-crosshair");
  svg.appendChild(hCross);

  const vCross = document.createElementNS(ns, "line");
  vCross.setAttribute("class", "prospect-frequency-crosshair");
  svg.appendChild(vCross);

  let linkedCrosshairLines = [];

  const hideLinkedCrosshair = () => {
    if (!linkedCrosshairLines.length) {
      return;
    }
    linkedCrosshairLines.forEach((lineNode) => {
      if (lineNode && lineNode.parentNode === svg) {
        svg.removeChild(lineNode);
      }
    });
    linkedCrosshairLines = [];
  };

  const showLinkedCrosshairAt = (pointEntryOrEntries) => {
    hideLinkedCrosshair();
    const entries = Array.isArray(pointEntryOrEntries)
      ? pointEntryOrEntries
      : [pointEntryOrEntries];
    const seenIndexes = new Set();
    entries.forEach((pointEntry) => {
      if (!pointEntry) {
        return;
      }
      const pointIndex = Number(pointEntry.index);
      if (Number.isFinite(pointIndex) && seenIndexes.has(pointIndex)) {
        return;
      }
      if (Number.isFinite(pointIndex)) {
        seenIndexes.add(pointIndex);
      }
      const x = Number(pointEntry.x);
      const y = Number(pointEntry.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        return;
      }

      const linkedHCross = document.createElementNS(ns, "line");
      linkedHCross.setAttribute("class", "prospect-frequency-crosshair");
      linkedHCross.setAttribute("x1", sidePad.toFixed(2));
      linkedHCross.setAttribute("y1", y.toFixed(2));
      linkedHCross.setAttribute("x2", x.toFixed(2));
      linkedHCross.setAttribute("y2", y.toFixed(2));
      linkedHCross.style.opacity = "1";
      svg.appendChild(linkedHCross);
      linkedCrosshairLines.push(linkedHCross);

      const linkedVCross = document.createElementNS(ns, "line");
      linkedVCross.setAttribute("class", "prospect-frequency-crosshair");
      linkedVCross.setAttribute("x1", x.toFixed(2));
      linkedVCross.setAttribute("y1", y.toFixed(2));
      linkedVCross.setAttribute("x2", x.toFixed(2));
      linkedVCross.setAttribute("y2", (topPad + drawHeight).toFixed(2));
      linkedVCross.style.opacity = "1";
      svg.appendChild(linkedVCross);
      linkedCrosshairLines.push(linkedVCross);
    });
  };

  const showCrosshairAt = (point, event) => {
    const tooltipRangeStart = prospectFrequencyReverseCumulative ? point.intervalEnd : point.intervalStart;
    const tooltipRangeEnd = prospectFrequencyReverseCumulative ? point.intervalStart : point.intervalEnd;
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

    const detail = point.kind === "average-reference"
      ? [
        `${model.commodity} | Average Yield Reference`,
        `Avg Yield: ${formatNumeric(point.averageYield, 2)}%`
      ].join("\n")
      : [
        `${model.commodity} | ${tooltipRangeStart}% - ${tooltipRangeEnd}%`,
        `Cumulative Frequency: ${point.total} (Current: ${point.current}, Other: ${point.other})`,
        `Bin Frequency: ${point.binTotal} (Current: ${point.binCurrent}, Other: ${point.binOther})`
      ].join("\n");
    showTooltip(detail, event);
  };

  const hideCrosshair = () => {
    hCross.style.opacity = "0";
    vCross.style.opacity = "0";
    hideTooltip();
    clearHighlights();
  };

  const findNearestPoint = (event) => {
    const snapPoints = averageReferencePoint
      ? [...coordinates, averageReferencePoint]
      : coordinates;
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

  hitbox.addEventListener("mouseenter", (event) => {
    const nearest = findNearestPoint(event);
    if (nearest) {
      showCrosshairAt(nearest, event);
      if (nearest.kind === "average-reference") {
        clearHighlights();
      } else {
        highlightPoint(cumulativePointByIndex.get(nearest.index));
      }
    }
  });
  hitbox.addEventListener("mousemove", (event) => {
    const nearest = findNearestPoint(event);
    if (nearest) {
      showCrosshairAt(nearest, event);
      if (nearest.kind === "average-reference") {
        clearHighlights();
      } else {
        highlightPoint(cumulativePointByIndex.get(nearest.index));
      }
    }
  });
  hitbox.addEventListener("mouseleave", () => {
    hideCrosshair();
  });

  coordinates.forEach((point) => {
    const otherDot = document.createElementNS(ns, "circle");
    otherDot.setAttribute("class", "prospect-frequency-dot--other");
    otherDot.setAttribute("cx", point.x.toFixed(2));
    otherDot.setAttribute("cy", point.y.toFixed(2));
    otherDot.setAttribute("r", "5.7");
    const pointEntry = cumulativePointByIndex.get(point.index);
    if (pointEntry) {
      pointEntry.dots.push(otherDot);
    }
    otherDot.addEventListener("mouseenter", (event) => {
      showCrosshairAt(point, event);
      highlightPoint(pointEntry);
    });
    otherDot.addEventListener("mousemove", (event) => {
      showCrosshairAt(point, event);
      highlightPoint(pointEntry);
    });
    otherDot.addEventListener("mouseleave", hideCrosshair);
    svg.appendChild(otherDot);
  });

  coordinates.forEach((point) => {
    if (point.binCurrent <= 0) {
      return;
    }
    const currentDot = document.createElementNS(ns, "circle");
    currentDot.setAttribute("class", "prospect-frequency-dot--current");
    currentDot.setAttribute("cx", point.x.toFixed(2));
    currentDot.setAttribute("cy", point.y.toFixed(2));
    currentDot.setAttribute("r", "6.2");
    const pointEntry = cumulativePointByIndex.get(point.index);
    if (pointEntry) {
      pointEntry.dots.push(currentDot);
      pointEntry.currentDots.push(currentDot);
    }
    currentDot.addEventListener("mouseenter", (event) => {
      showCrosshairAt(point, event);
      highlightPoint(pointEntry);
    });
    currentDot.addEventListener("mousemove", (event) => {
      showCrosshairAt(point, event);
      highlightPoint(pointEntry);
    });
    currentDot.addEventListener("mouseleave", hideCrosshair);
    svg.appendChild(currentDot);
  });

  surface.appendChild(svg);
  plot.appendChild(yAxis);
  plot.appendChild(surface);
  layout.appendChild(plot);

  const labels = document.createElement("div");
  labels.className = "histogram-bin-labels prospect-frequency-bin-labels";
  const labelPoints = prospectFrequencyReverseCumulative ? [...model.points].reverse() : model.points;
  labels.style.gridTemplateColumns = `repeat(${labelPoints.length}, minmax(0, 1fr))`;
  const cumulativeLabelTexts = [];
  labelPoints.forEach((point, index) => {
    const label = document.createElement("span");
    label.className = "histogram-bin-label prospect-frequency-bin-label";
    const labelRangeStart = prospectFrequencyReverseCumulative ? point.intervalEnd : point.intervalStart;
    const labelRangeEnd = prospectFrequencyReverseCumulative ? point.intervalStart : point.intervalEnd;
    cumulativeLabelTexts.push(`${labelRangeStart}-\n${labelRangeEnd}%`);
    labels.appendChild(label);
  });
  const labelsRow = document.createElement("div");
  labelsRow.className = "prospect-frequency-label-row";
  const spacer = document.createElement("div");
  spacer.className = "prospect-frequency-label-spacer";
  labelsRow.appendChild(spacer);
  labelsRow.appendChild(labels);
  layout.appendChild(labelsRow);

  const legend = document.createElement("div");
  legend.className = "prospect-frequency-legend";

  const dotLegendOther = document.createElement("span");
  dotLegendOther.className = "prospect-frequency-legend-item";
  dotLegendOther.innerHTML = "<span class=\"prospect-frequency-dot\"></span><span>Other Sessions</span>";
  legend.appendChild(dotLegendOther);

  const dotLegendCurrent = document.createElement("span");
  dotLegendCurrent.className = "prospect-frequency-legend-item";
  dotLegendCurrent.innerHTML = "<span class=\"prospect-frequency-dot prospect-frequency-dot--current\"></span><span>Current Session</span>";
  legend.appendChild(dotLegendCurrent);

  const sessionsLegend = document.createElement("span");
  sessionsLegend.className = "prospect-frequency-legend-item";
  sessionsLegend.textContent = `Mining Sessions: ${model.sessionsCount}`;
  legend.appendChild(sessionsLegend);

  const averageLegend = document.createElement("label");
  averageLegend.className = "prospect-frequency-legend-item prospect-frequency-control";
  const averageInput = document.createElement("input");
  averageInput.type = "checkbox";
  averageInput.checked = prospectFrequencyShowAverageReference;
  averageInput.addEventListener("change", () => {
    onAverageToggle(averageInput.checked);
  });
  const averageText = document.createElement("span");
  averageText.textContent = `Avg Yield: ${formatNumeric(model.averageYield, 2)}%`;
  averageLegend.appendChild(averageInput);
  averageLegend.appendChild(averageText);
  legend.appendChild(averageLegend);

  const asteroidLegend = document.createElement("span");
  asteroidLegend.className = "prospect-frequency-legend-item";
  asteroidLegend.textContent = `Asteroids: ${model.asteroidsCount}`;
  legend.appendChild(asteroidLegend);

  layout.appendChild(legend);
  chartProspectCumulativeFrequency.appendChild(layout);
  applyLabels(labels, cumulativeLabelTexts, 4);
  return {
    commodityKey: normalizeCommodity(model.commodity),
    points: Array.from(cumulativePointByIndex.values()),
    showLinkedCrosshair: showLinkedCrosshairAt,
    hideLinkedCrosshair
  };
}
