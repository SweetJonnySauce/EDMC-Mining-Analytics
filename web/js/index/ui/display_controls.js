export function wireDisplaySettingsControls(options) {
  const {
    materialPercentShowCollectedInput,
    materialPercentShowGridlinesInput,
    materialPercentIncludeDuplicatesInput,
    materialPercentIntervalInputs,
    materialPercentReverseCumulativeInput,
    initialState,
    onCollectedModeToggle,
    onGridlinesToggle,
    onIncludeDuplicatesToggle,
    onBinSizeSelect,
    onReverseCumulativeToggle,
  } = options || {};

  const state = initialState && typeof initialState === "object" ? initialState : {};

  if (materialPercentShowCollectedInput) {
    materialPercentShowCollectedInput.checked = !!state.materialPercentShowOnlyCollected;
    materialPercentShowCollectedInput.addEventListener("change", () => {
      if (typeof onCollectedModeToggle === "function") {
        onCollectedModeToggle(!!materialPercentShowCollectedInput.checked);
      }
    });
  }

  if (materialPercentShowGridlinesInput) {
    materialPercentShowGridlinesInput.checked = state.materialPercentShowGridlines !== false;
    materialPercentShowGridlinesInput.addEventListener("change", () => {
      if (typeof onGridlinesToggle === "function") {
        onGridlinesToggle(!!materialPercentShowGridlinesInput.checked);
      }
    });
  }

  if (materialPercentIncludeDuplicatesInput) {
    materialPercentIncludeDuplicatesInput.checked = state.prospectFrequencyIncludeDuplicates !== false;
    materialPercentIncludeDuplicatesInput.addEventListener("change", () => {
      if (typeof onIncludeDuplicatesToggle === "function") {
        onIncludeDuplicatesToggle(!!materialPercentIncludeDuplicatesInput.checked);
      }
    });
  }

  if (materialPercentIntervalInputs && materialPercentIntervalInputs.length) {
    materialPercentIntervalInputs.forEach((input) => {
      if (!(input instanceof HTMLInputElement)) {
        return;
      }
      const value = Number(input.value);
      input.checked = value === (Number(state.prospectFrequencyBinSize) === 10 ? 10 : 5);
      input.addEventListener("change", () => {
        if (!input.checked) {
          return;
        }
        if (typeof onBinSizeSelect === "function") {
          onBinSizeSelect(value);
        }
      });
    });
  }

  if (materialPercentReverseCumulativeInput) {
    materialPercentReverseCumulativeInput.checked = !!state.prospectFrequencyReverseCumulative;
    materialPercentReverseCumulativeInput.addEventListener("change", () => {
      if (typeof onReverseCumulativeToggle === "function") {
        onReverseCumulativeToggle(!!materialPercentReverseCumulativeInput.checked);
      }
    });
  }
}
