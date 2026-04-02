export function normalizeTimelinePoints(points) {
  if (!Array.isArray(points) || points.length === 0) {
    return [];
  }
  return points
    .map((point) => {
      if (typeof point === "string") {
        const ms = Date.parse(point);
        if (!Number.isFinite(ms)) {
          return null;
        }
        return { ms, label: "event" };
      }
      if (!point || typeof point !== "object") {
        return null;
      }
      const stamp = point.timestamp;
      if (typeof stamp !== "string") {
        return null;
      }
      const ms = Date.parse(stamp);
      if (!Number.isFinite(ms)) {
        return null;
      }
      const label = typeof point.label === "string" && point.label.trim()
        ? point.label.trim()
        : "event";
      return { ms, label };
    })
    .filter((point) => !!point)
    .sort((a, b) => a.ms - b.ms);
}

export function buildTimelineBins(validPoints, options) {
  if (!Array.isArray(validPoints) || validPoints.length === 0) {
    return null;
  }
  const settings = options && typeof options === "object" ? options : {};
  const start = Number.isFinite(settings.startMs) ? settings.startMs : validPoints[0].ms;
  const end = Number.isFinite(settings.endMs) && settings.endMs > start ? settings.endMs : validPoints[validPoints.length - 1].ms;
  const duration = Math.max(1, end - start);
  const bins = Math.max(8, Math.min(36, settings.bins || 24));
  const binsData = new Array(bins).fill(null).map(() => ({
    count: 0,
    labels: new Map()
  }));

  validPoints.forEach((point) => {
    let index = Math.floor(((point.ms - start) / duration) * bins);
    if (index < 0) {
      index = 0;
    }
    if (index >= bins) {
      index = bins - 1;
    }
    const binData = binsData[index];
    binData.count += 1;
    binData.labels.set(point.label, (binData.labels.get(point.label) || 0) + 1);
  });

  const counts = binsData.map((binData) => binData.count);
  const peak = Math.max(...counts, 0);
  return {
    start,
    end,
    duration,
    bins,
    binsData,
    counts,
    peak
  };
}

export function computeTimelinePeak(points, options) {
  const validPoints = normalizeTimelinePoints(points);
  if (!validPoints.length) {
    return 0;
  }
  const timelineData = buildTimelineBins(validPoints, options);
  return timelineData ? timelineData.peak : 0;
}

export function renderTimelineChart(options) {
  const {
    container,
    points,
    chartOptions,
    formatLocalClock,
    showCursorTooltip,
    hideCursorTooltip,
  } = options || {};
  if (!(container instanceof HTMLElement)) {
    return null;
  }
  const timelineOptions = chartOptions && typeof chartOptions === "object" ? chartOptions : {};
  const formatClock = typeof formatLocalClock === "function"
    ? formatLocalClock
    : ((value) => String(value ?? ""));
  const showTooltip = typeof showCursorTooltip === "function"
    ? showCursorTooltip
    : (() => {});
  const hideTooltip = typeof hideCursorTooltip === "function"
    ? hideCursorTooltip
    : (() => {});

  container.innerHTML = "";
  const validPoints = normalizeTimelinePoints(points);
  if (!validPoints.length) {
    const note = document.createElement("p");
    note.className = "chart-empty";
    note.textContent = "No timeline events in this session.";
    container.appendChild(note);
    return null;
  }
  const timelineData = buildTimelineBins(validPoints, timelineOptions);
  if (!timelineData) {
    const note = document.createElement("p");
    note.className = "chart-empty";
    note.textContent = "Timeline data could not be prepared.";
    container.appendChild(note);
    return null;
  }

  const start = timelineData.start;
  const end = timelineData.end;
  const duration = timelineData.duration;
  const bins = timelineData.bins;
  const binsData = timelineData.binsData;
  const counts = timelineData.counts;
  const peak = Math.max(1, timelineData.peak);
  const timeline = document.createElement("div");
  timeline.className = "timeline";

  const plot = document.createElement("div");
  plot.className = "timeline-plot";

  const yAxis = document.createElement("div");
  yAxis.className = "timeline-y-axis";
  const mid = Math.round(peak / 2);
  [peak, mid, 0].forEach((value) => {
    const tick = document.createElement("span");
    tick.textContent = String(value);
    yAxis.appendChild(tick);
  });

  const bars = document.createElement("div");
  bars.className = "timeline-bars";
  const barElements = [];

  counts.forEach((count, index) => {
    const bar = document.createElement("div");
    bar.className = timelineOptions.cool ? "timeline-bar cool" : "timeline-bar";
    const height = Math.max(2, (count / peak) * 100);
    bar.style.height = `${height}%`;

    const binStart = start + (duration * index / bins);
    const binEnd = start + (duration * (index + 1) / bins);
    const binData = binsData[index];
    const countLabel = timelineOptions.countLabel || "Count";
    const breakdown = Array.from(binData.labels.entries())
      .sort((left, right) => right[1] - left[1])
      .map(([label, qty]) => `${label} x${qty}`);
    const breakdownText = breakdown.length ? `\n${breakdown.join("\n")}` : "";
    const detail = `${formatClock(binStart)} - ${formatClock(binEnd)} | ${countLabel}: ${count}${breakdownText}`;
    bar.addEventListener("mouseenter", (event) => {
      showTooltip(detail, event);
    });
    bar.addEventListener("mousemove", (event) => {
      showTooltip(detail, event);
    });
    bar.addEventListener("mouseleave", () => {
      hideTooltip();
    });
    bars.appendChild(bar);
    barElements.push(bar);
  });

  const axis = document.createElement("div");
  axis.className = "timeline-axis";
  axis.innerHTML = `<span>${formatClock(start)}</span><span>${formatClock(end)}</span>`;

  plot.appendChild(yAxis);
  plot.appendChild(bars);
  plot.addEventListener("mouseleave", hideTooltip);
  timeline.appendChild(plot);
  timeline.appendChild(axis);
  container.appendChild(timeline);
  return {
    start,
    duration,
    bins,
    barElements
  };
}
