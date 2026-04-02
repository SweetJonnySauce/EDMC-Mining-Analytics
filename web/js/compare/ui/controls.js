export function renderReferenceCrosshairControls(options) {
  const {
    container,
    referenceCrosshairs,
    selectedReferenceCrosshairs,
    onToggle,
  } = options || {};
  if (!container) {
    return;
  }
  const selected = selectedReferenceCrosshairs instanceof Set
    ? selectedReferenceCrosshairs
    : new Set();
  const entries = Array.isArray(referenceCrosshairs) ? referenceCrosshairs : [];
  container.innerHTML = "";
  entries.forEach((entry) => {
    const wrapper = document.createElement("label");
    wrapper.className = "compare-reference-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = selected.has(entry.key);
    input.addEventListener("change", () => {
      if (typeof onToggle === "function") {
        onToggle(entry.key, input.checked);
      }
    });
    const swatch = document.createElement("span");
    swatch.className = `compare-reference-swatch compare-reference-swatch--${entry.key}`;
    const text = document.createElement("span");
    text.textContent = entry.label;
    wrapper.appendChild(input);
    wrapper.appendChild(swatch);
    wrapper.appendChild(text);
    container.appendChild(wrapper);
  });
}

export function renderYieldPopulationControls(options) {
  const {
    container,
    modes,
    selectedYieldPopulationMode,
    onSelect,
  } = options || {};
  if (!container) {
    return;
  }
  const entries = Array.isArray(modes) ? modes : [];
  container.innerHTML = "";
  entries.forEach((mode) => {
    const wrapper = document.createElement("label");
    wrapper.className = "compare-population-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "compare-yield-population-mode";
    input.value = mode.key;
    input.checked = selectedYieldPopulationMode === mode.key;
    input.addEventListener("change", () => {
      if (!input.checked) {
        return;
      }
      if (typeof onSelect === "function") {
        onSelect(mode.key);
      }
    });
    const text = document.createElement("span");
    text.textContent = mode.label;
    wrapper.appendChild(input);
    wrapper.appendChild(text);
    container.appendChild(wrapper);
  });
}

export function renderGridlineControls(options) {
  const {
    container,
    compareShowGridlines,
    compareNormalizeMetrics,
    compareReverseCumulative,
    compareShowHistogram,
    onGridlinesChange,
    onNormalizeChange,
    onReverseChange,
    onHistogramChange,
  } = options || {};
  if (!container) {
    return;
  }
  container.innerHTML = "";

  const gridlineWrapper = document.createElement("label");
  gridlineWrapper.className = "compare-population-option";
  const gridlineInput = document.createElement("input");
  gridlineInput.type = "checkbox";
  gridlineInput.checked = !!compareShowGridlines;
  gridlineInput.addEventListener("change", () => {
    if (typeof onGridlinesChange === "function") {
      onGridlinesChange(gridlineInput.checked);
    }
  });
  const gridlineText = document.createElement("span");
  gridlineText.textContent = "Show gridlines";
  gridlineWrapper.appendChild(gridlineInput);
  gridlineWrapper.appendChild(gridlineText);
  container.appendChild(gridlineWrapper);

  const normalizeWrapper = document.createElement("label");
  normalizeWrapper.className = "compare-population-option";
  const normalizeInput = document.createElement("input");
  normalizeInput.type = "checkbox";
  normalizeInput.checked = !!compareNormalizeMetrics;
  normalizeInput.addEventListener("change", () => {
    if (typeof onNormalizeChange === "function") {
      onNormalizeChange(normalizeInput.checked);
    }
  });
  const normalizeText = document.createElement("span");
  normalizeText.textContent = "Normalize by Sessions";
  normalizeWrapper.appendChild(normalizeInput);
  normalizeWrapper.appendChild(normalizeText);
  container.appendChild(normalizeWrapper);

  const reverseWrapper = document.createElement("label");
  reverseWrapper.className = "compare-population-option";
  const reverseInput = document.createElement("input");
  reverseInput.type = "checkbox";
  reverseInput.checked = !!compareReverseCumulative;
  reverseInput.addEventListener("change", () => {
    if (typeof onReverseChange === "function") {
      onReverseChange(reverseInput.checked);
    }
  });
  const reverseText = document.createElement("span");
  reverseText.textContent = "Reverse Cumulative Freq.";
  reverseWrapper.appendChild(reverseInput);
  reverseWrapper.appendChild(reverseText);
  container.appendChild(reverseWrapper);

  const histogramWrapper = document.createElement("label");
  histogramWrapper.className = "compare-population-option";
  const histogramInput = document.createElement("input");
  histogramInput.type = "checkbox";
  histogramInput.checked = !!compareShowHistogram;
  histogramInput.addEventListener("change", () => {
    if (typeof onHistogramChange === "function") {
      onHistogramChange(histogramInput.checked);
    }
  });
  const histogramText = document.createElement("span");
  histogramText.textContent = "Show Histogram";
  histogramWrapper.appendChild(histogramInput);
  histogramWrapper.appendChild(histogramText);
  container.appendChild(histogramWrapper);
}

export function syncCommoditySelect(options) {
  const {
    selectElement,
    compareData,
    selectedCommodityKey,
    requestedCommodityKey,
    onSelectedCommodityKeyChange,
    onRequestedCommodityKeyConsume,
  } = options || {};
  if (!selectElement || !compareData) {
    return {
      selectedCommodityKey: typeof selectedCommodityKey === "string" ? selectedCommodityKey : "",
      requestedCommodityKey: typeof requestedCommodityKey === "string" ? requestedCommodityKey : ""
    };
  }
  selectElement.innerHTML = "";
  const commodities = Array.isArray(compareData.commodities) ? compareData.commodities : [];
  commodities.forEach((commodity) => {
    const option = document.createElement("option");
    option.value = commodity.key;
    option.textContent = commodity.label;
    selectElement.appendChild(option);
  });

  let nextSelected = typeof selectedCommodityKey === "string" ? selectedCommodityKey : "";
  const requested = typeof requestedCommodityKey === "string" ? requestedCommodityKey : "";
  if (requested) {
    const requestedExists = commodities.some((item) => item.key === requested);
    if (requestedExists) {
      nextSelected = requested;
      if (typeof onSelectedCommodityKeyChange === "function") {
        onSelectedCommodityKeyChange(nextSelected);
      }
    }
    if (typeof onRequestedCommodityKeyConsume === "function") {
      onRequestedCommodityKeyConsume();
    }
  }
  if (!nextSelected || !commodities.some((item) => item.key === nextSelected)) {
    nextSelected = commodities.length ? commodities[0].key : "";
    if (typeof onSelectedCommodityKeyChange === "function") {
      onSelectedCommodityKeyChange(nextSelected);
    }
  }
  selectElement.value = nextSelected;
  return {
    selectedCommodityKey: nextSelected,
    requestedCommodityKey: ""
  };
}
