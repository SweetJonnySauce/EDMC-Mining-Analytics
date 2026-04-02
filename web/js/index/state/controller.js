function normalizeString(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeBinSize(value) {
  return Number(value) === 10 ? 10 : 5;
}

function normalizeKey(value, normalizeCommodityKey) {
  const normalize = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((entry) => normalizeString(entry).toLowerCase());
  return normalize(value);
}

export function createIndexStateController(store) {
  const targetStore = store && typeof store.patch === "function" ? store : null;
  if (!targetStore) {
    throw new Error("createIndexStateController requires a valid store.");
  }

  const patch = (partialState) => targetStore.patch(partialState);

  return {
    getState: () => targetStore.getState(),
    subscribe: (listener) => targetStore.subscribe(listener),
    setRuntimeAnalysisSettings: (settings) => {
      const nextSettings = settings && typeof settings === "object" ? settings : {};
      patch({ runtimeAnalysisSettings: nextSettings });
    },
    setActiveSession: (sessionData, filename) => {
      patch({
        activeSessionData: sessionData || null,
        activeSessionFilename: normalizeString(filename)
      });
    },
    clearActiveSession: () => {
      patch({
        activeSessionData: null,
        activeSessionFilename: ""
      });
    },
    clearHistogramCommoditySelection: () => {
      patch({
        selectedHistogramCommodity: "",
        materialPercentHighlightedCommodityKey: "",
        histogramSelectionClearedByMaterial: false
      });
    },
    setSelectedHistogramCommodity: (commodityName) => {
      patch({
        selectedHistogramCommodity: normalizeString(commodityName),
        histogramSelectionClearedByMaterial: false
      });
    },
    setHistogramCommoditySelectionWithHighlight: (commodityName, commodityKey, normalizeCommodityKey) => {
      const normalizedName = normalizeString(commodityName);
      const highlightedKey = normalizeKey(commodityKey || commodityName, normalizeCommodityKey);
      patch({
        selectedHistogramCommodity: normalizedName,
        materialPercentHighlightedCommodityKey: highlightedKey,
        histogramSelectionClearedByMaterial: false
      });
    },
    applyMaterialCommoditySelection: (commodityName, commodityKey, isCollected, normalizeCommodityKey) => {
      const highlightedKey = normalizeKey(commodityKey || commodityName, normalizeCommodityKey);
      if (!highlightedKey) {
        return false;
      }
      const collected = !!isCollected;
      patch({
        materialPercentHighlightedCommodityKey: highlightedKey,
        selectedHistogramCommodity: collected ? normalizeString(commodityName) : "",
        histogramSelectionClearedByMaterial: !collected
      });
      return true;
    },
    setMaterialPercentCollectedMode: (enabled) => {
      const checked = !!enabled;
      patch({
        materialPercentShowOnlyCollected: checked,
        histogramShowOnlyCollected: checked
      });
    },
    setMaterialPercentGridlines: (enabled) => {
      patch({ materialPercentShowGridlines: !!enabled });
    },
    setProspectFrequencyIncludeDuplicates: (enabled) => {
      patch({ prospectFrequencyIncludeDuplicates: !!enabled });
    },
    setProspectFrequencyBinSize: (binSize) => {
      patch({ prospectFrequencyBinSize: normalizeBinSize(binSize) });
    },
    setProspectFrequencyReverseCumulative: (enabled) => {
      patch({ prospectFrequencyReverseCumulative: !!enabled });
    },
    setProspectFrequencyShowAverageReference: (enabled) => {
      patch({ prospectFrequencyShowAverageReference: !!enabled });
    }
  };
}
