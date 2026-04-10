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

export function renderCompareModeControls(options) {
  const {
    container,
    compareUseCdf,
    onModeChange,
  } = options || {};
  if (!container) {
    return;
  }
  container.innerHTML = "";
  const entries = [
    { key: "cumulative", label: "Cumulative Frequency" },
    { key: "above-threshold", label: "Above-Threshold %" }
  ];
  const selectedMode = compareUseCdf ? "above-threshold" : "cumulative";
  entries.forEach((entry) => {
    const wrapper = document.createElement("label");
    wrapper.className = "compare-population-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "compare-chart-mode";
    input.value = entry.key;
    input.checked = selectedMode === entry.key;
    input.addEventListener("change", () => {
      if (!input.checked) {
        return;
      }
      if (typeof onModeChange === "function") {
        onModeChange(entry.key);
      }
    });
    const text = document.createElement("span");
    text.textContent = entry.label;
    wrapper.appendChild(input);
    wrapper.appendChild(text);
    container.appendChild(wrapper);
  });
}

export function renderCompareTargetControl(options) {
  const {
    container,
    compareUseCdf,
    compareTargetTons,
    onTargetTonsChange,
  } = options || {};
  if (!container) {
    return;
  }
  container.innerHTML = "";
  const panel = container.parentElement;
  if (panel) {
    panel.classList.toggle("compare-control-pill--disabled", !compareUseCdf);
    panel.title = !compareUseCdf
      ? "Cargo target only applies to Above-Threshold % projections."
      : "";
  }

  const wrapper = document.createElement("div");
  wrapper.className = "compare-text-control";
  if (!compareUseCdf) {
    wrapper.classList.add("compare-text-control--disabled");
  }

  const label = document.createElement("span");
  label.className = "compare-text-control-label";
  label.textContent = "Cargo Target";

  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = "numeric";
  input.className = "compare-text-input";
  input.value = String(compareTargetTons || "");
  input.disabled = !compareUseCdf;
  input.setAttribute("aria-label", "Cargo target in tons");

  const suffix = document.createElement("span");
  suffix.className = "compare-text-input-suffix";
  suffix.textContent = "t";

  const commitValue = () => {
    if (typeof onTargetTonsChange !== "function") {
      return;
    }
    onTargetTonsChange(input.value);
  };

  input.addEventListener("change", commitValue);
  input.addEventListener("blur", commitValue);
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    input.blur();
  });

  wrapper.appendChild(label);
  wrapper.appendChild(input);
  wrapper.appendChild(suffix);
  container.appendChild(wrapper);
}

export function renderGridlineControls(options) {
  const {
    container,
    compareShowGridlines,
    compareUseCdf,
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
  normalizeInput.disabled = !!compareUseCdf;
  normalizeInput.checked = !!compareNormalizeMetrics;
  normalizeInput.addEventListener("change", () => {
    if (typeof onNormalizeChange === "function") {
      onNormalizeChange(normalizeInput.checked);
    }
  });
  const normalizeText = document.createElement("span");
  normalizeText.textContent = "Normalize by Sessions";
  if (compareUseCdf) {
    normalizeWrapper.classList.add("compare-population-option--disabled");
    normalizeWrapper.title = "Above-Threshold % already uses a normalized 0-1 probability scale.";
  }
  normalizeWrapper.appendChild(normalizeInput);
  normalizeWrapper.appendChild(normalizeText);
  container.appendChild(normalizeWrapper);

  const reverseWrapper = document.createElement("label");
  reverseWrapper.className = "compare-population-option";
  const reverseInput = document.createElement("input");
  reverseInput.type = "checkbox";
  reverseInput.disabled = !!compareUseCdf;
  reverseInput.checked = compareUseCdf ? true : !!compareReverseCumulative;
  reverseInput.addEventListener("change", () => {
    if (typeof onReverseChange === "function") {
      onReverseChange(reverseInput.checked);
    }
  });
  const reverseText = document.createElement("span");
  reverseText.textContent = "Reverse Cumulative Freq.";
  if (compareUseCdf) {
    reverseWrapper.classList.add("compare-population-option--disabled");
    reverseWrapper.title = "Above-Threshold % uses the normalized above-threshold view from EliteMiners graphs.";
  }
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
  histogramText.textContent = compareUseCdf ? "Show Data Grid" : "Show Histogram";
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
