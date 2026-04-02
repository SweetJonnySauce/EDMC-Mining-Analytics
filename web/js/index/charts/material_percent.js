export function renderMaterialPercentAmountChart(options) {
  const {
    chartMaterialPercentAmount,
    materialPercentCard,
    model,
    materialPercentShowOnlyCollected,
    materialPercentShowGridlines,
    activeThemeId,
    commodityAbbreviationMap,
    selectedHistogramCommodity,
    materialPercentHighlightedCommodityKey,
    normalizeCommodityKey,
    asNumber,
    formatNumber,
    showCursorTooltip,
    hideCursorTooltip,
    highlightFromMaterialPercentDotEntry,
    clearCrossChartHoverHighlights,
    applyMaterialPercentCommoditySelection,
  } = options || {};

  const normalizeCommodity = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const readNumber = typeof asNumber === "function"
    ? asNumber
    : ((value) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : 0;
    });
  const formatNumeric = typeof formatNumber === "function"
    ? formatNumber
    : ((value) => String(value ?? ""));
  const showTooltip = typeof showCursorTooltip === "function"
    ? showCursorTooltip
    : (() => {});
  const hideTooltip = typeof hideCursorTooltip === "function"
    ? hideCursorTooltip
    : (() => {});
  const highlightDot = typeof highlightFromMaterialPercentDotEntry === "function"
    ? highlightFromMaterialPercentDotEntry
    : (() => {});
  const clearHighlights = typeof clearCrossChartHoverHighlights === "function"
    ? clearCrossChartHoverHighlights
    : (() => {});
  const applyCommoditySelection = typeof applyMaterialPercentCommoditySelection === "function"
    ? applyMaterialPercentCommoditySelection
    : (() => {});

  if (!(chartMaterialPercentAmount instanceof HTMLElement)) {
    return {
      hoverContext: {
        commodityKey: "",
        dots: []
      }
    };
  }

  chartMaterialPercentAmount.innerHTML = "";
  if (!model) {
    if (materialPercentCard instanceof HTMLElement) {
      materialPercentCard.style.minHeight = "170px";
    }
    const note = document.createElement("p");
    note.className = "chart-empty";
    note.textContent = materialPercentShowOnlyCollected
      ? "No prospected commodities match collected/refined materials for this session."
      : "No prospected asteroid material percentages found in this session.";
    chartMaterialPercentAmount.appendChild(note);
    return {
      hoverContext: {
        commodityKey: "",
        dots: []
      }
    };
  }

  const palette = (activeThemeId === "green-light" || activeThemeId === "green-dark")
    ? [
        "#b8d63f",
        "#90cc59",
        "#61bfa1",
        "#4fb5d2",
        "#6ba3f1",
        "#998fe4",
        "#c486d6",
        "#df80b4",
        "#ef8e88"
      ]
    : [
        "#f7c948",
        "#72d572",
        "#47d6a7",
        "#5ec8ff",
        "#60a4ff",
        "#9d8bff",
        "#ca7fff",
        "#ff7fa5",
        "#ffa45f"
      ];

  const commodityCount = Math.max(1, model.commodities.length);
  const preferredRowSpacing = materialPercentShowOnlyCollected ? 24 : 28;
  const topPad = 12;
  const bottomPad = 12;
  const sidePad = 12;
  const minimumVisualRows = materialPercentShowOnlyCollected ? 2 : 4;
  const effectiveRowCount = Math.max(minimumVisualRows, commodityCount);
  const width = 1100;
  const height = topPad + bottomPad + (effectiveRowCount * preferredRowSpacing);
  const drawWidth = Math.max(1, width - (sidePad * 2));
  const drawHeight = Math.max(1, height - topPad - bottomPad);
  const rowSpacing = drawHeight / commodityCount;
  const selectedHighlightMaxHeight = 36;
  const selectedHighlightHeight = Math.min(rowSpacing, selectedHighlightMaxHeight);
  const axisRowHeight = 26;
  const cardChromeHeight = 72;
  const desiredCardMinHeight = Math.round(cardChromeHeight + height + axisRowHeight);
  if (materialPercentCard instanceof HTMLElement) {
    materialPercentCard.style.minHeight = `${Math.max(170, desiredCardMinHeight)}px`;
  }
  const maxAsteroidNumber = Math.max(1, Math.floor(readNumber(model.maxAsteroidNumber)));
  const selectedCommodityKeyFallback = normalizeCommodity(selectedHistogramCommodity);
  const selectedCommodityKey = model.commodities.some((commodity) => commodity.key === materialPercentHighlightedCommodityKey)
    ? materialPercentHighlightedCommodityKey
    : selectedCommodityKeyFallback;
  const bubbleDotEntries = [];
  const selectedRowIndex = model.commodities.findIndex((commodity) => commodity.key === selectedCommodityKey);
  const xDivisor = Math.max(1, maxAsteroidNumber - 1);
  const toX = (asteroidNumber) => {
    const safeAsteroidNumber = Math.max(1, Math.min(maxAsteroidNumber, Math.floor(readNumber(asteroidNumber))));
    if (maxAsteroidNumber <= 1) {
      return sidePad + (drawWidth / 2);
    }
    const ratio = (safeAsteroidNumber - 1) / xDivisor;
    return sidePad + (ratio * drawWidth);
  };
  const toRowCenterY = (index) => topPad + ((index + 0.5) * rowSpacing);
  const toPlotY = (index) => toRowCenterY(index);

  const layout = document.createElement("div");
  layout.className = "material-percent-layout";
  const plot = document.createElement("div");
  plot.className = "material-percent-plot";
  plot.style.minHeight = `${height}px`;

  const yAxis = document.createElement("div");
  yAxis.className = "material-percent-y-axis";
  yAxis.style.gridTemplateRows = `${topPad}px repeat(${commodityCount}, ${rowSpacing.toFixed(2)}px) ${bottomPad}px`;
  const yTopSpacer = document.createElement("span");
  yTopSpacer.className = "material-percent-y-spacer";
  yAxis.appendChild(yTopSpacer);
  model.commodities.forEach((commodity) => {
    const label = document.createElement("span");
    label.className = "material-percent-y-label";
    label.classList.add("material-percent-y-label--interactive");
    if (commodity.key === selectedCommodityKey) {
      label.classList.add("material-percent-y-label--selected");
    }
    const abbreviation = commodityAbbreviationMap instanceof Map
      ? (commodityAbbreviationMap.get(commodity.key) || "")
      : "";
    label.textContent = abbreviation || commodity.name;
    label.title = abbreviation ? `${commodity.name} (${abbreviation})` : commodity.name;
    label.addEventListener("click", () => {
      applyCommoditySelection(commodity.name, commodity.key, commodity.isCollected === true);
    });
    yAxis.appendChild(label);
  });
  const yBottomSpacer = document.createElement("span");
  yBottomSpacer.className = "material-percent-y-spacer";
  yAxis.appendChild(yBottomSpacer);

  const surface = document.createElement("div");
  surface.className = "material-percent-surface";
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.classList.add("material-percent-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "none");

  if (selectedRowIndex >= 0) {
    const selectedBand = document.createElementNS(ns, "rect");
    selectedBand.setAttribute("class", "material-percent-row-highlight");
    selectedBand.setAttribute("data-row-index", String(selectedRowIndex));
    selectedBand.setAttribute("x", sidePad.toFixed(2));
    selectedBand.setAttribute("y", (toRowCenterY(selectedRowIndex) - (selectedHighlightHeight / 2)).toFixed(2));
    selectedBand.setAttribute("width", drawWidth.toFixed(2));
    selectedBand.setAttribute("height", selectedHighlightHeight.toFixed(2));
    svg.appendChild(selectedBand);
  }

  model.commodities.forEach((commodity, index) => {
    const y = toPlotY(index);
    if (materialPercentShowGridlines) {
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", sidePad.toFixed(2));
      line.setAttribute("y1", y.toFixed(2));
      line.setAttribute("x2", (width - sidePad).toFixed(2));
      line.setAttribute("y2", y.toFixed(2));
      const lineClass = index === selectedRowIndex
        ? "material-percent-grid-line material-percent-grid-line--selected"
        : "material-percent-grid-line";
      line.setAttribute("class", lineClass);
      line.setAttribute("data-row-index", String(index));
      svg.appendChild(line);
    }

    const hitbox = document.createElementNS(ns, "line");
    hitbox.setAttribute("class", "material-percent-row-hitbox");
    hitbox.setAttribute("data-row-index", String(index));
    hitbox.setAttribute("x1", sidePad.toFixed(2));
    hitbox.setAttribute("y1", y.toFixed(2));
    hitbox.setAttribute("x2", (width - sidePad).toFixed(2));
    hitbox.setAttribute("y2", y.toFixed(2));
    hitbox.addEventListener("click", () => {
      applyCommoditySelection(commodity.name, commodity.key, commodity.isCollected === true);
    });
    svg.appendChild(hitbox);
  });

  const maxGridLines = 8;
  const xStep = Math.max(1, Math.ceil(maxAsteroidNumber / maxGridLines));
  const xTickValues = [];
  for (let value = 1; value <= maxAsteroidNumber; value += xStep) {
    xTickValues.push(value);
  }
  if (xTickValues[xTickValues.length - 1] !== maxAsteroidNumber) {
    xTickValues.push(maxAsteroidNumber);
  }
  if (materialPercentShowGridlines) {
    xTickValues.forEach((value) => {
      const x = toX(value);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", x.toFixed(2));
      line.setAttribute("y1", topPad.toFixed(2));
      line.setAttribute("x2", x.toFixed(2));
      line.setAttribute("y2", (topPad + drawHeight).toFixed(2));
      line.setAttribute("class", "material-percent-grid-line");
      svg.appendChild(line);
    });
  }

  const minDotRadius = 4.4;
  const maxDotRadius = 20.14;
  model.commodities.forEach((commodity, commodityIndex) => {
    const color = palette[commodityIndex % palette.length];
    const y = toPlotY(commodityIndex);
    commodity.points.forEach((point) => {
      const x = toX(point.asteroidNumber);
      const normalizedPercentage = Math.max(0, Math.min(100, point.percentage)) / 100;
      const radius = normalizedPercentage > 0
        ? (minDotRadius + (normalizedPercentage * (maxDotRadius - minDotRadius)))
        : 0;
      const dot = document.createElementNS(ns, "ellipse");
      dot.setAttribute("class", "material-percent-dot");
      dot.setAttribute("cx", x.toFixed(2));
      dot.setAttribute("cy", y.toFixed(2));
      dot.setAttribute("rx", radius.toFixed(2));
      dot.setAttribute("ry", radius.toFixed(2));
      dot.setAttribute("data-base-r", radius.toFixed(4));
      dot.setAttribute("data-row-index", String(commodityIndex));
      dot.setAttribute("fill", color);
      const detail = [
        `${commodity.name} | Asteroid #${point.asteroidNumber}`,
        `Percentage: ${formatNumeric(point.percentage, 2)}%`
      ].join("\n");
      const dotEntry = {
        element: dot,
        commodityKey: commodity.key,
        asteroidNumber: point.asteroidNumber,
        percentage: point.percentage
      };
      bubbleDotEntries.push(dotEntry);
      dot.addEventListener("mouseenter", (event) => {
        showTooltip(detail, event);
        highlightDot(dotEntry);
      });
      dot.addEventListener("mousemove", (event) => {
        showTooltip(detail, event);
        highlightDot(dotEntry);
      });
      dot.addEventListener("mouseleave", () => {
        hideTooltip();
        clearHighlights();
      });
      svg.appendChild(dot);
    });
  });

  svg.addEventListener("mouseleave", () => {
    hideTooltip();
    clearHighlights();
  });
  surface.appendChild(svg);
  plot.appendChild(yAxis);
  plot.appendChild(surface);
  layout.appendChild(plot);

  const axisRow = document.createElement("div");
  axisRow.className = "material-percent-axis-row";
  const axisSpacer = document.createElement("div");
  axisSpacer.className = "material-percent-y-axis material-percent-axis-spacer";
  axisRow.appendChild(axisSpacer);

  const axis = document.createElement("div");
  axis.className = "material-percent-axis";
  const maxDigits = Math.max(1, String(maxAsteroidNumber).length);
  const minLabelSpacing = Math.max(18, (maxDigits * 7) + 10);
  const maxLabelCount = Math.max(2, Math.floor(drawWidth / minLabelSpacing));
  const xLabelStep = maxAsteroidNumber <= maxLabelCount
    ? 1
    : Math.max(1, Math.ceil((maxAsteroidNumber - 1) / Math.max(1, (maxLabelCount - 1))));
  const xLabelValues = [];
  for (let value = 1; value <= maxAsteroidNumber; value += xLabelStep) {
    xLabelValues.push(value);
  }
  if (xLabelValues[xLabelValues.length - 1] !== maxAsteroidNumber) {
    xLabelValues.push(maxAsteroidNumber);
  }
  xLabelValues.forEach((value) => {
    const label = document.createElement("span");
    label.className = "material-percent-axis-label";
    label.textContent = String(value);
    const x = toX(value);
    label.style.left = `${((x / width) * 100).toFixed(4)}%`;
    axis.appendChild(label);
  });
  axisRow.appendChild(axis);
  layout.appendChild(axisRow);

  chartMaterialPercentAmount.appendChild(layout);
  window.requestAnimationFrame(() => {
    const svgRect = svg.getBoundingClientRect();
    const svgWidth = Number(svgRect.width);
    const svgHeight = Number(svgRect.height);
    if (Number.isFinite(svgWidth) && svgWidth > 0 && Number.isFinite(svgHeight) && svgHeight > 0) {
      const labelNodes = Array.from(yAxis.querySelectorAll(".material-percent-y-label"));
      const rowYByIndex = [];
      labelNodes.forEach((labelNode, index) => {
        const labelRect = labelNode.getBoundingClientRect();
        const centerPx = (labelRect.top + (labelRect.height / 2)) - svgRect.top;
        const mappedY = (centerPx / svgHeight) * height;
        rowYByIndex[index] = mappedY;
      });

      svg.querySelectorAll(".material-percent-grid-line[data-row-index]").forEach((node) => {
        const rowIndex = Number(node.getAttribute("data-row-index"));
        const mappedY = rowYByIndex[rowIndex];
        if (!Number.isFinite(mappedY)) {
          return;
        }
        node.setAttribute("y1", mappedY.toFixed(2));
        node.setAttribute("y2", mappedY.toFixed(2));
      });

      svg.querySelectorAll(".material-percent-row-hitbox[data-row-index]").forEach((node) => {
        const rowIndex = Number(node.getAttribute("data-row-index"));
        const mappedY = rowYByIndex[rowIndex];
        if (!Number.isFinite(mappedY)) {
          return;
        }
        node.setAttribute("y1", mappedY.toFixed(2));
        node.setAttribute("y2", mappedY.toFixed(2));
      });

      svg.querySelectorAll(".material-percent-dot[data-row-index]").forEach((node) => {
        const rowIndex = Number(node.getAttribute("data-row-index"));
        const mappedY = rowYByIndex[rowIndex];
        if (!Number.isFinite(mappedY)) {
          return;
        }
        node.setAttribute("cy", mappedY.toFixed(2));
      });

      svg.querySelectorAll(".material-percent-row-highlight[data-row-index]").forEach((node) => {
        const rowIndex = Number(node.getAttribute("data-row-index"));
        const mappedY = rowYByIndex[rowIndex];
        if (!Number.isFinite(mappedY)) {
          return;
        }
        node.setAttribute("y", (mappedY - (selectedHighlightHeight / 2)).toFixed(2));
        node.setAttribute("height", selectedHighlightHeight.toFixed(2));
      });
    }

    const rect = svg.getBoundingClientRect();
    const rectWidth = Number(rect.width);
    const rectHeight = Number(rect.height);
    if (!Number.isFinite(rectWidth) || !Number.isFinite(rectHeight) || rectWidth <= 0 || rectHeight <= 0) {
      return;
    }
    const scaleX = rectWidth / width;
    const scaleY = rectHeight / height;
    const compensation = scaleY > 0 ? (scaleX / scaleY) : 1;
    const dots = svg.querySelectorAll(".material-percent-dot[data-base-r]");
    dots.forEach((node) => {
      const baseRadius = Number(node.getAttribute("data-base-r"));
      if (!Number.isFinite(baseRadius) || baseRadius <= 0) {
        return;
      }
      node.setAttribute("ry", (baseRadius * compensation).toFixed(2));
    });
  });

  return {
    hoverContext: {
      commodityKey: selectedCommodityKey || "",
      dots: bubbleDotEntries
    }
  };
}
