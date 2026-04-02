export function renderCumulativeCommoditiesChart(options) {
  const {
    chartCumulativeCommodities,
    cumulativeHeaderControls,
    model,
    activeThemeId,
    getSelection,
    setSelection,
    getRenderMode,
    setRenderMode,
    getValueMode,
    setValueMode,
    asNumber,
    formatNumber,
    formatLocalDateTime,
    formatLocalClock,
    showCursorTooltip,
    hideCursorTooltip,
  } = options || {};

  if (!(chartCumulativeCommodities instanceof HTMLElement)) {
    return;
  }
  const readSelection = typeof getSelection === "function" ? getSelection : (() => ({}));
  const writeSelection = typeof setSelection === "function" ? setSelection : (() => {});
  const readRenderMode = typeof getRenderMode === "function" ? getRenderMode : (() => "line");
  const writeRenderMode = typeof setRenderMode === "function" ? setRenderMode : (() => {});
  const readValueMode = typeof getValueMode === "function" ? getValueMode : (() => "quantity");
  const writeValueMode = typeof setValueMode === "function" ? setValueMode : (() => {});
  const readNumber = typeof asNumber === "function"
    ? asNumber
    : ((value) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : 0;
    });
  const formatNumeric = typeof formatNumber === "function"
    ? formatNumber
    : ((value) => String(value ?? ""));
  const formatDateTime = typeof formatLocalDateTime === "function"
    ? formatLocalDateTime
    : ((value) => String(value ?? ""));
  const formatClock = typeof formatLocalClock === "function"
    ? formatLocalClock
    : ((value) => String(value ?? ""));
  const showTooltip = typeof showCursorTooltip === "function"
    ? showCursorTooltip
    : (() => {});
  const hideTooltip = typeof hideCursorTooltip === "function"
    ? hideCursorTooltip
    : (() => {});

  chartCumulativeCommodities.innerHTML = "";
  if (cumulativeHeaderControls instanceof HTMLElement) {
    cumulativeHeaderControls.innerHTML = "";
  }

  if (!model || !Array.isArray(model.series) || !model.series.length) {
    const note = document.createElement("p");
    note.className = "chart-empty";
    note.textContent = "No cargo inventory snapshots found in this session.";
    chartCumulativeCommodities.appendChild(note);
    return;
  }

  const { startMs, endMs, series } = model;
  const duration = Math.max(1, endMs - startMs);
  const seriesIndexByName = new Map(series.map((item, index) => [item.name, index]));
  const currentSelection = readSelection() || {};
  const nextSelection = {};
  series.forEach((item) => {
    nextSelection[item.name] = Object.prototype.hasOwnProperty.call(currentSelection, item.name)
      ? !!currentSelection[item.name]
      : true;
  });
  writeSelection(nextSelection);

  const palette = (activeThemeId === "green-light" || activeThemeId === "green-dark")
    ? [
        "#224914",
        "#2e631b",
        "#367520",
        "#3c8223",
        "#4d9134",
        "#7ab465",
        "#b7daaa",
        "#d7ebd0"
      ]
    : [
        "#67d4ff",
        "#3b8cec",
        "#8be37f",
        "#f7c948",
        "#ff9f43",
        "#d0a5ff",
        "#ff6f91",
        "#4dd0b5"
      ];
  const readMetricValue = (point) => readValueMode() === "profit"
    ? readNumber(point && point.profit)
    : readNumber(point && point.quantity);
  const formatMetricValue = (value) => readValueMode() === "profit"
    ? `${formatNumeric(value, 0)} CR`
    : `${formatNumeric(value, 0)} t`;
  const formatAxisMetricValue = (value) => readValueMode() === "profit"
    ? (
        value >= 1000000
          ? `${formatNumeric(value / 1000000, 0)} M`
          : (value >= 1000 ? `${formatNumeric(value / 1000, 0)} K` : formatNumeric(value, 0))
      )
    : formatNumeric(value, 0);

  const layout = document.createElement("div");
  layout.className = "cumulative-layout";

  const plot = document.createElement("div");
  plot.className = "cumulative-plot";

  const yAxis = document.createElement("div");
  yAxis.className = "timeline-y-axis";

  const surface = document.createElement("div");
  surface.className = "cumulative-surface";

  const legend = document.createElement("div");
  legend.className = "cumulative-legend";

  const legendRows = new Map();
  const allItem = document.createElement("label");
  allItem.className = "cumulative-legend-item";
  const allCheckbox = document.createElement("input");
  allCheckbox.type = "checkbox";
  allCheckbox.checked = true;
  const allText = document.createElement("span");
  allText.textContent = "All";
  allItem.appendChild(allCheckbox);
  allItem.appendChild(allText);
  legend.appendChild(allItem);

  const syncAllCheckboxState = () => {
    const selection = readSelection() || {};
    const selectedCount = series.reduce(
      (sum, item) => sum + (selection[item.name] ? 1 : 0),
      0
    );
    allCheckbox.checked = selectedCount === series.length;
    allCheckbox.indeterminate = selectedCount > 0 && selectedCount < series.length;
  };

  allCheckbox.addEventListener("change", () => {
    const checked = allCheckbox.checked;
    allCheckbox.indeterminate = false;
    const selection = { ...(readSelection() || {}) };
    series.forEach((item) => {
      selection[item.name] = checked;
      const row = legendRows.get(item.name);
      if (row && row.checkbox) {
        row.checkbox.checked = checked;
      }
    });
    writeSelection(selection);
    renderSelectedSeries();
  });

  series.forEach((item) => {
    const index = seriesIndexByName.get(item.name) || 0;
    const color = palette[index % palette.length];
    const legendItem = document.createElement("label");
    legendItem.className = "cumulative-legend-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = !!(readSelection() || {})[item.name];
    checkbox.style.accentColor = color;
    checkbox.addEventListener("change", () => {
      const selection = { ...(readSelection() || {}) };
      selection[item.name] = checkbox.checked;
      writeSelection(selection);
      syncAllCheckboxState();
      renderSelectedSeries();
    });
    const swatch = document.createElement("span");
    swatch.className = "cumulative-legend-swatch";
    swatch.style.background = color;
    const latest = item.points[item.points.length - 1];
    const text = document.createElement("span");
    text.textContent = `${item.name} (${formatMetricValue(readMetricValue(latest))})`;
    legendItem.appendChild(checkbox);
    legendItem.appendChild(swatch);
    legendItem.appendChild(text);
    legendRows.set(item.name, { item: legendItem, checkbox, text, seriesItem: item });
    legend.appendChild(legendItem);
  });

  const valueModes = [
    { value: "quantity", label: "Quantity" },
    { value: "profit", label: "Profit" }
  ];
  if (readValueMode() !== "quantity" && readValueMode() !== "profit") {
    writeValueMode("quantity");
  }
  const valueModeGroup = document.createElement("div");
  valueModeGroup.className = "cumulative-render-mode-group";
  valueModes.forEach((mode) => {
    const option = document.createElement("label");
    option.className = "cumulative-render-mode";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "cumulative-value-mode";
    input.value = mode.value;
    input.checked = readValueMode() === mode.value;
    input.addEventListener("change", () => {
      if (!input.checked) {
        return;
      }
      writeValueMode(mode.value);
      renderSelectedSeries();
    });
    const text = document.createElement("span");
    text.textContent = mode.label;
    option.appendChild(input);
    option.appendChild(text);
    valueModeGroup.appendChild(option);
  });

  const renderModes = [
    { value: "line", label: "Lines" },
    { value: "stacked-area", label: "Stacked Area" }
  ];
  if (readRenderMode() !== "line" && readRenderMode() !== "stacked-area") {
    writeRenderMode("line");
  }
  const renderModeGroup = document.createElement("div");
  renderModeGroup.className = "cumulative-render-mode-group";
  renderModes.forEach((mode) => {
    const option = document.createElement("label");
    option.className = "cumulative-render-mode";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "cumulative-render-mode";
    input.value = mode.value;
    input.checked = readRenderMode() === mode.value;
    input.addEventListener("change", () => {
      if (!input.checked) {
        return;
      }
      writeRenderMode(mode.value);
      renderSelectedSeries();
    });
    const text = document.createElement("span");
    text.textContent = mode.label;
    option.appendChild(input);
    option.appendChild(text);
    renderModeGroup.appendChild(option);
  });
  if (cumulativeHeaderControls instanceof HTMLElement) {
    cumulativeHeaderControls.appendChild(valueModeGroup);
    cumulativeHeaderControls.appendChild(renderModeGroup);
  }

  function renderSelectedSeries() {
    hideTooltip();
    const selection = readSelection() || {};
    const selectedSeries = series.filter((item) => selection[item.name]);
    const stackedSeries = [...selectedSeries].sort((left, right) => {
      const rankSeriesForStack = (item) => {
        const name = String(item && item.name || "").trim().toLowerCase();
        if (name === "empty cargo space") {
          return 2;
        }
        if (name === "limpets") {
          return 1;
        }
        return 0;
      };
      const rankDelta = rankSeriesForStack(left) - rankSeriesForStack(right);
      if (rankDelta !== 0) {
        return rankDelta;
      }
      return (seriesIndexByName.get(left.name) || 0) - (seriesIndexByName.get(right.name) || 0);
    });
    const pointCount = selectedSeries.length
      ? Math.min(...selectedSeries.map((item) => item.points.length))
      : 0;
    const values = selectedSeries.flatMap(
      (item) => item.points.slice(0, pointCount).map((point) => readMetricValue(point))
    );
    const stackedTotals = pointCount > 0
      ? new Array(pointCount).fill(0).map((_, pointIndex) => selectedSeries.reduce(
        (sum, item) => sum + readMetricValue(item.points[pointIndex]),
        0
      ))
      : [];
    const peak = readRenderMode() === "stacked-area"
      ? Math.max(...stackedTotals, 0)
      : Math.max(...values, 0);
    const yMax = Math.max(1, peak);

    yAxis.innerHTML = "";
    const mid = Math.round(yMax / 2);
    [yMax, mid, 0].forEach((value) => {
      const tick = document.createElement("span");
      tick.textContent = formatAxisMetricValue(value);
      yAxis.appendChild(tick);
    });

    legendRows.forEach((row) => {
      row.item.classList.toggle("cumulative-legend-item--off", !row.checkbox.checked);
      const latestPoint = row.seriesItem.points[row.seriesItem.points.length - 1];
      row.text.textContent = `${row.seriesItem.name} (${formatMetricValue(readMetricValue(latestPoint))})`;
    });

    surface.innerHTML = "";
    if (!selectedSeries.length) {
      const note = document.createElement("p");
      note.className = "chart-empty";
      note.style.padding = "8px";
      note.textContent = "No commodities selected.";
      surface.appendChild(note);
      return;
    }

    const width = 1000;
    const height = 220;
    const topPad = 10;
    const bottomPad = 14;
    const sidePad = 12;
    const drawHeight = height - topPad - bottomPad;
    const drawWidth = Math.max(1, width - (sidePad * 2));
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.classList.add("cumulative-svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("preserveAspectRatio", "none");

    const yRatios = [0, 0.5, 1];
    yRatios.forEach((ratio) => {
      const y = topPad + (drawHeight * ratio);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", sidePad.toFixed(2));
      line.setAttribute("y1", y.toFixed(2));
      line.setAttribute("x2", (width - sidePad).toFixed(2));
      line.setAttribute("y2", y.toFixed(2));
      line.setAttribute("class", "cumulative-grid-line");
      svg.appendChild(line);
    });

    const toX = (ms) => sidePad + (((ms - startMs) / duration) * drawWidth);
    const toY = (value) => {
      const ratio = yMax <= 0 ? 0 : (value / yMax);
      return topPad + (drawHeight * (1 - ratio));
    };
    if (readRenderMode() === "stacked-area") {
      const lower = new Array(pointCount).fill(0);
      stackedSeries.forEach((item) => {
        if (!item.points.length || pointCount === 0) {
          return;
        }
        const index = seriesIndexByName.get(item.name) || 0;
        const color = palette[index % palette.length];
        const upper = item.points.slice(0, pointCount).map(
          (point, pointIndex) => lower[pointIndex] + readMetricValue(point)
        );
        const topCommands = item.points.slice(0, pointCount).map((point, pointIndex) => {
          const x = toX(point.ms);
          const y = toY(upper[pointIndex]);
          return `${pointIndex === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
        });
        const bottomCommands = item.points.slice(0, pointCount).map((point, pointIndex) => {
          const reverseIndex = pointCount - pointIndex - 1;
          const reversePoint = item.points[reverseIndex];
          const x = toX(reversePoint.ms);
          const y = toY(lower[reverseIndex]);
          return `L${x.toFixed(2)} ${y.toFixed(2)}`;
        });
        const areaPath = document.createElementNS(ns, "path");
        areaPath.setAttribute("d", `${topCommands.join(" ")} ${bottomCommands.join(" ")} Z`);
        areaPath.setAttribute("fill", color);
        areaPath.setAttribute("fill-opacity", "0.24");
        areaPath.style.cursor = "crosshair";
        const areaPoints = item.points.slice(0, pointCount);
        const areaPointX = areaPoints.map((point) => toX(point.ms));
        const findNearestAreaPointIndex = (event) => {
          if (!areaPoints.length) {
            return 0;
          }
          const rect = svg.getBoundingClientRect();
          if (!rect.width) {
            return 0;
          }
          const ratio = (event.clientX - rect.left) / rect.width;
          const localX = ratio * width;
          let nearestIndex = 0;
          let nearestDistance = Math.abs(areaPointX[0] - localX);
          for (let idx = 1; idx < areaPointX.length; idx += 1) {
            const distance = Math.abs(areaPointX[idx] - localX);
            if (distance < nearestDistance) {
              nearestDistance = distance;
              nearestIndex = idx;
            }
          }
          return nearestIndex;
        };
        const showAreaTooltip = (event) => {
          const pointIndex = findNearestAreaPointIndex(event);
          const point = areaPoints[pointIndex];
          const pointMetric = readMetricValue(point);
          const totalStackedValue = readNumber(stackedTotals[pointIndex]);
          const detail = `${item.name}: ${formatMetricValue(pointMetric)}\nStacked: ${formatMetricValue(totalStackedValue)}\n${formatDateTime(new Date(point.ms).toISOString())}`;
          showTooltip(detail, event);
        };
        areaPath.addEventListener("mouseenter", (event) => {
          showAreaTooltip(event);
        });
        areaPath.addEventListener("mousemove", (event) => {
          showAreaTooltip(event);
        });
        areaPath.addEventListener("mouseleave", () => {
          hideTooltip();
        });
        svg.appendChild(areaPath);

        const outline = document.createElementNS(ns, "path");
        outline.setAttribute("d", topCommands.join(" "));
        outline.setAttribute("stroke", color);
        outline.setAttribute("class", "cumulative-line");
        svg.appendChild(outline);

        item.points.slice(0, pointCount).forEach((point, pointIndex) => {
          const marker = document.createElementNS(ns, "circle");
          marker.setAttribute("cx", toX(point.ms).toFixed(2));
          marker.setAttribute("cy", toY(upper[pointIndex]).toFixed(2));
          marker.setAttribute("r", "3");
          marker.setAttribute("fill", color);
          marker.setAttribute("class", "cumulative-point");
          const pointMetric = readMetricValue(point);
          const totalStackedValue = readNumber(stackedTotals[pointIndex]);
          const detail = `${item.name}: ${formatMetricValue(pointMetric)}\nStacked: ${formatMetricValue(totalStackedValue)}\n${formatDateTime(new Date(point.ms).toISOString())}`;
          marker.addEventListener("mouseenter", (event) => {
            showTooltip(detail, event);
          });
          marker.addEventListener("mousemove", (event) => {
            showTooltip(detail, event);
          });
          marker.addEventListener("mouseleave", () => {
            hideTooltip();
          });
          svg.appendChild(marker);
        });

        upper.forEach((value, pointIndex) => {
          lower[pointIndex] = value;
        });
      });
    } else {
      selectedSeries.forEach((item) => {
        if (!item.points.length) {
          return;
        }
        const index = seriesIndexByName.get(item.name) || 0;
        const color = palette[index % palette.length];
        const path = document.createElementNS(ns, "path");
        const commands = item.points.slice(0, pointCount).map((point, pointIndex) => {
          const x = toX(point.ms);
          const y = toY(readMetricValue(point));
          return `${pointIndex === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
        }).join(" ");
        path.setAttribute("d", commands);
        path.setAttribute("stroke", color);
        path.setAttribute("class", "cumulative-line");
        svg.appendChild(path);

        item.points.slice(0, pointCount).forEach((point) => {
          const marker = document.createElementNS(ns, "circle");
          marker.setAttribute("cx", toX(point.ms).toFixed(2));
          const pointMetric = readMetricValue(point);
          marker.setAttribute("cy", toY(pointMetric).toFixed(2));
          marker.setAttribute("r", "3");
          marker.setAttribute("fill", color);
          marker.setAttribute("class", "cumulative-point");
          const detail = `${item.name}: ${formatMetricValue(pointMetric)}\n${formatDateTime(new Date(point.ms).toISOString())}`;
          marker.addEventListener("mouseenter", (event) => {
            showTooltip(detail, event);
          });
          marker.addEventListener("mousemove", (event) => {
            showTooltip(detail, event);
          });
          marker.addEventListener("mouseleave", () => {
            hideTooltip();
          });
          svg.appendChild(marker);
        });
      });
    }

    surface.appendChild(svg);
  }

  syncAllCheckboxState();
  renderSelectedSeries();
  plot.appendChild(yAxis);
  plot.appendChild(surface);

  const axis = document.createElement("div");
  axis.className = "timeline-axis";
  axis.innerHTML = `<span>${formatClock(startMs)}</span><span>${formatClock(endMs)}</span>`;

  layout.appendChild(plot);
  layout.appendChild(axis);
  layout.appendChild(legend);
  chartCumulativeCommodities.appendChild(layout);
}
