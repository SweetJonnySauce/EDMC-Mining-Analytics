export function renderProspectHistogramSelection(options) {
  const {
    chartProspectHistogram,
    commodities,
    binSize,
    selectedHistogramCommodity,
    reverseHistogram,
    applyAdaptiveBinLabels,
    normalizeCommodityKey,
    asNumber,
    showCursorTooltip,
    hideCursorTooltip,
    highlightFromHistogramBarEntry,
    clearCrossChartHoverHighlights,
  } = options || {};
  if (!(chartProspectHistogram instanceof HTMLElement)) {
    return {
      commodityKey: "",
      binSize: Number(binSize) || 10,
      bars: []
    };
  }
  const readNumber = typeof asNumber === "function"
    ? asNumber
    : ((value) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : 0;
    });
  const normalizeCommodity = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const applyLabels = typeof applyAdaptiveBinLabels === "function"
    ? applyAdaptiveBinLabels
    : (() => 1);
  const showTooltip = typeof showCursorTooltip === "function"
    ? showCursorTooltip
    : (() => {});
  const hideTooltip = typeof hideCursorTooltip === "function"
    ? hideCursorTooltip
    : (() => {});
  const highlightBar = typeof highlightFromHistogramBarEntry === "function"
    ? highlightFromHistogramBarEntry
    : (() => {});
  const clearHighlights = typeof clearCrossChartHoverHighlights === "function"
    ? clearCrossChartHoverHighlights
    : (() => {});

  const items = Array.isArray(commodities) ? commodities : [];
  const safeBinSize = Number.isFinite(Number(binSize)) ? Number(binSize) : 10;
  chartProspectHistogram.innerHTML = "";

  const buildHistogramTickValues = (peakValue) => {
    const peakInt = Math.max(1, Math.floor(readNumber(peakValue)));
    const maxVisibleTicks = 9;
    if ((peakInt + 1) <= maxVisibleTicks) {
      const yMax = peakInt;
      return {
        yMax,
        values: Array.from({ length: yMax + 1 }, (_unused, offset) => yMax - offset)
      };
    }
    let step = Math.max(1, Math.round(peakInt / (maxVisibleTicks - 1)));
    // Avoid a trailing "... 1, 0" pair, which compresses the final interval visually.
    while (step < peakInt && (peakInt % step) === 1) {
      step += 1;
    }
    const yMax = peakInt;
    let values = [];
    const buildValues = () => {
      const computed = [];
      for (let value = yMax; value >= 0; value -= step) {
        computed.push(value);
      }
      if (computed[computed.length - 1] !== 0) {
        computed.push(0);
      }
      return computed.filter((value, index, allValues) => allValues.indexOf(value) === index);
    };
    values = buildValues();
    while (values.length > maxVisibleTicks) {
      step += 1;
      values = buildValues();
    }
    return { yMax, values };
  };

  const buildHistogramYAxis = (tickValues, yMaxValue) => {
    const yAxisLabel = document.createElement("div");
    yAxisLabel.className = "histogram-y-axis-label";
    yAxisLabel.textContent = "# of Asteroids";

    const yAxis = document.createElement("div");
    yAxis.className = "histogram-y-axis";
    const ticksLayer = document.createElement("div");
    ticksLayer.className = "histogram-y-axis-ticks";
    const safeYMax = Math.max(1, Math.floor(readNumber(yMaxValue)));
    tickValues.forEach((value) => {
      const tick = document.createElement("span");
      tick.className = "histogram-y-axis-tick";
      tick.textContent = String(value);
      const clampedValue = Math.max(0, Math.min(safeYMax, Math.floor(readNumber(value))));
      const topPercent = 100 - ((clampedValue / safeYMax) * 100);
      tick.style.top = `${topPercent.toFixed(4)}%`;
      // Center all ticks on their numeric value positions so spacing is linear.
      tick.style.transform = "translateY(-50%)";
      ticksLayer.appendChild(tick);
    });
    yAxis.appendChild(ticksLayer);

    return { yAxisLabel, yAxis };
  };

  const selected = items.find((item) => item && item.name === selectedHistogramCommodity) || null;
  if (!selected) {
    const binsCount = Math.max(
      1,
      ...items.map((item) => (
        item && Array.isArray(item.counts)
          ? item.counts.length
          : 0
      ))
    );
    const layout = document.createElement("div");
    layout.className = "histogram-layout";

    const plot = document.createElement("div");
    plot.className = "histogram-plot";

    const { yAxisLabel, yAxis } = buildHistogramYAxis([1, 0], 1);

    const bars = document.createElement("div");
    bars.className = "histogram-bars";
    bars.style.gridTemplateColumns = `repeat(${binsCount}, minmax(0, 1fr))`;
    const note = document.createElement("span");
    note.className = "chart-empty";
    note.textContent = "No collected commodity selected in histogram.";
    note.style.gridColumn = "1 / -1";
    note.style.alignSelf = "center";
    note.style.justifySelf = "center";
    note.style.textAlign = "center";
    bars.appendChild(note);

    const labels = document.createElement("div");
    labels.className = "histogram-bin-labels";
    labels.style.gridTemplateColumns = `repeat(${binsCount}, minmax(0, 1fr))`;
    const displayBinIndexes = reverseHistogram
      ? Array.from({ length: binsCount }, (_unused, index) => binsCount - index - 1)
      : Array.from({ length: binsCount }, (_unused, index) => index);
    const histogramLabelTexts = [];
    displayBinIndexes.forEach((binIndex, displayIndex) => {
      const label = document.createElement("span");
      label.className = "histogram-bin-label";
      const rangeStart = binIndex * safeBinSize;
      const rangeEnd = rangeStart + safeBinSize;
      const labelRangeStart = reverseHistogram ? rangeEnd : rangeStart;
      const labelRangeEnd = reverseHistogram ? rangeStart : rangeEnd;
      histogramLabelTexts[displayIndex] = `${labelRangeStart}-\n${labelRangeEnd}%`;
      labels.appendChild(label);
    });
    const labelsRow = document.createElement("div");
    labelsRow.className = "histogram-label-row";
    const spacer = document.createElement("div");
    spacer.className = "timeline-y-axis histogram-label-spacer";
    labelsRow.appendChild(spacer);
    labelsRow.appendChild(labels);

    const axis = document.createElement("div");
    axis.className = "timeline-axis";
    axis.innerHTML = "";

    plot.appendChild(yAxisLabel);
    plot.appendChild(yAxis);
    plot.appendChild(bars);
    layout.appendChild(plot);
    layout.appendChild(labelsRow);
    layout.appendChild(axis);
    chartProspectHistogram.appendChild(layout);
    applyLabels(labels, histogramLabelTexts, 4);
    return {
      commodityKey: normalizeCommodity(selectedHistogramCommodity),
      binSize: safeBinSize,
      bars: []
    };
  }

  const peak = Math.max(...selected.counts, 1);
  const selectedCommodityKey = normalizeCommodity(selected.name);
  const layout = document.createElement("div");
  layout.className = "histogram-layout";
  const plot = document.createElement("div");
  plot.className = "histogram-plot";

  const yTickModel = buildHistogramTickValues(peak);
  const yTicks = yTickModel.values;
  const yAxisMax = yTickModel.yMax;
  const { yAxisLabel, yAxis } = buildHistogramYAxis(yTicks, yAxisMax);

  const bars = document.createElement("div");
  bars.className = "histogram-bars";
  bars.style.gridTemplateColumns = `repeat(${selected.counts.length}, minmax(0, 1fr))`;
  const histogramBarEntries = [];
  const displayBinIndexes = reverseHistogram
    ? Array.from({ length: selected.counts.length }, (_unused, index) => selected.counts.length - index - 1)
    : Array.from({ length: selected.counts.length }, (_unused, index) => index);
  displayBinIndexes.forEach((binIndex) => {
    const count = selected.counts[binIndex];
    const bar = document.createElement("div");
    bar.className = "histogram-bar";
    const ratio = yAxisMax > 0 ? (count / yAxisMax) : 0;
    bar.style.height = `${Math.max(2, ratio * 100)}%`;
    const rangeStart = binIndex * safeBinSize;
    const rangeEnd = rangeStart + safeBinSize;
    const labelRangeStart = reverseHistogram ? rangeEnd : rangeStart;
    const labelRangeEnd = reverseHistogram ? rangeStart : rangeEnd;
    const detail = `${selected.name}\n${labelRangeStart}% - ${labelRangeEnd}%: ${count} prospects`;
    const barEntry = {
      element: bar,
      index: binIndex,
      rangeStart,
      rangeEnd,
      isLast: binIndex === (selected.counts.length - 1)
    };
    histogramBarEntries.push(barEntry);
    bar.addEventListener("mouseenter", (event) => {
      showTooltip(detail, event);
      highlightBar(barEntry);
    });
    bar.addEventListener("mousemove", (event) => {
      showTooltip(detail, event);
      highlightBar(barEntry);
    });
    bar.addEventListener("mouseleave", () => {
      hideTooltip();
      clearHighlights();
    });
    bars.appendChild(bar);
  });
  bars.addEventListener("mouseleave", () => {
    hideTooltip();
    clearHighlights();
  });

  const labels = document.createElement("div");
  labels.className = "histogram-bin-labels";
  labels.style.gridTemplateColumns = `repeat(${selected.counts.length}, minmax(0, 1fr))`;
  const histogramLabelTexts = [];
  displayBinIndexes.forEach((binIndex, displayIndex) => {
    const label = document.createElement("span");
    label.className = "histogram-bin-label";
    const rangeStart = binIndex * safeBinSize;
    const rangeEnd = rangeStart + safeBinSize;
    const labelRangeStart = reverseHistogram ? rangeEnd : rangeStart;
    const labelRangeEnd = reverseHistogram ? rangeStart : rangeEnd;
    histogramLabelTexts[displayIndex] = `${labelRangeStart}-\n${labelRangeEnd}%`;
    labels.appendChild(label);
  });
  const labelsRow = document.createElement("div");
  labelsRow.className = "histogram-label-row";
  const spacer = document.createElement("div");
  spacer.className = "timeline-y-axis histogram-label-spacer";
  labelsRow.appendChild(spacer);
  labelsRow.appendChild(labels);

  const axis = document.createElement("div");
  axis.className = "timeline-axis";
  axis.innerHTML = "";

  plot.appendChild(yAxisLabel);
  plot.appendChild(yAxis);
  plot.appendChild(bars);
  layout.appendChild(plot);
  layout.appendChild(labelsRow);
  layout.appendChild(axis);
  chartProspectHistogram.appendChild(layout);
  applyLabels(labels, histogramLabelTexts, 4);
  return {
    commodityKey: selectedCommodityKey,
    binSize: safeBinSize,
    bars: histogramBarEntries
  };
}
