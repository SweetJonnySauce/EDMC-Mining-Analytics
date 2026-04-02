function normalizeString(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeSet(value, fallbackValues) {
  if (value instanceof Set) {
    return new Set(value);
  }
  if (Array.isArray(value)) {
    return new Set(value.map((item) => normalizeString(item)).filter((item) => !!item));
  }
  return new Set(fallbackValues || []);
}

export function createCompareStateController(store) {
  const targetStore = store && typeof store.patch === "function" ? store : null;
  if (!targetStore) {
    throw new Error("createCompareStateController requires a valid store.");
  }

  const patch = (partialState) => targetStore.patch(partialState);

  return {
    getState: () => targetStore.getState(),
    subscribe: (listener) => targetStore.subscribe(listener),
    setCompareData: (data) => {
      patch({
        compareData: data && typeof data === "object" ? data : null
      });
    },
    setRequestedCommodityKey: (commodityKey) => {
      patch({ requestedCommodityKey: normalizeString(commodityKey) });
    },
    setSelectedCommodityKey: (commodityKey) => {
      patch({ selectedCommodityKey: normalizeString(commodityKey) });
    },
    setSelectedYieldPopulationMode: (mode) => {
      const nextMode = normalizeString(mode);
      patch({ selectedYieldPopulationMode: nextMode || "all" });
    },
    setSelectedReferenceCrosshairs: (crosshairs) => {
      patch({ selectedReferenceCrosshairs: normalizeSet(crosshairs, ["avg"]) });
    },
    setReferenceCrosshairEnabled: (key, enabled) => {
      const entryKey = normalizeString(key);
      if (!entryKey) {
        return;
      }
      const current = targetStore.getState();
      const next = normalizeSet(current && current.selectedReferenceCrosshairs, ["avg"]);
      if (enabled) {
        next.add(entryKey);
      } else {
        next.delete(entryKey);
      }
      patch({ selectedReferenceCrosshairs: next });
    },
    setCompareShowGridlines: (enabled) => {
      patch({ compareShowGridlines: !!enabled });
    },
    setCompareNormalizeMetrics: (enabled) => {
      patch({ compareNormalizeMetrics: !!enabled });
    },
    setCompareReverseCumulative: (enabled) => {
      patch({ compareReverseCumulative: !!enabled });
    },
    setCompareShowHistogram: (enabled) => {
      patch({ compareShowHistogram: !!enabled });
    },
    setFavoriteRingNames: (ringNames) => {
      patch({ favoriteRingNames: normalizeSet(ringNames, []) });
    }
  };
}
