export function buildMaterialPercentAmountModel(options) {
  const {
    sessionData,
    showOnlyCollected,
    includeDuplicates,
    collectRefinedCommodityKeys,
    normalizeCommodityKey,
    normalizeTextKey,
  } = options || {};
  const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
  const commodityMap = new Map();
  const collectedCommodityKeys = typeof collectRefinedCommodityKeys === "function"
    ? collectRefinedCommodityKeys(events)
    : new Set();
  const normalizeCommodity = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const normalizeText = typeof normalizeTextKey === "function"
    ? normalizeTextKey
    : ((value) => String(value || "").trim().toLowerCase());
  const sourceCommodities = sessionData && typeof sessionData === "object" && sessionData.commodities && typeof sessionData.commodities === "object"
    ? sessionData.commodities
    : {};
  const refinedTonsByCommodity = new Map();
  Object.entries(sourceCommodities).forEach(([name, details]) => {
    const commodityKey = normalizeCommodity(name) || normalizeText(name) || String(name || "").trim().toLowerCase();
    if (!commodityKey) {
      return;
    }
    const gathered = details && typeof details === "object" && details.gathered && typeof details.gathered === "object"
      ? details.gathered
      : {};
    const tons = Number(gathered.tons);
    if (!Number.isFinite(tons) || tons <= 0) {
      return;
    }
    refinedTonsByCommodity.set(commodityKey, (refinedTonsByCommodity.get(commodityKey) || 0) + tons);
  });
  let asteroidNumber = 0;

  events.forEach((event) => {
    if (!event || event.type !== "prospected_asteroid") {
      return;
    }
    const details = event.details && typeof event.details === "object" ? event.details : {};
    if (!includeDuplicates && details.duplicate === true) {
      return;
    }
    asteroidNumber += 1;
    const materials = Array.isArray(details.materials) ? details.materials : [];
    materials.forEach((material) => {
      if (!material || typeof material !== "object") {
        return;
      }
      const name = typeof material.name === "string" ? material.name.trim() : "";
      const percentage = Number(material.percentage);
      if (!name || !Number.isFinite(percentage) || percentage <= 0) {
        return;
      }
      const commodityKey = normalizeCommodity(name) || normalizeText(name);
      if (!commodityKey) {
        return;
      }
      const commodityIsCollected = collectedCommodityKeys.has(commodityKey);
      if (showOnlyCollected && !commodityIsCollected) {
        return;
      }
      let item = commodityMap.get(commodityKey);
      if (!item) {
        item = {
          key: commodityKey,
          name,
          isCollected: commodityIsCollected,
          refinedTons: Number(refinedTonsByCommodity.get(commodityKey) || 0),
          totalPercentage: 0,
          count: 0,
          points: []
        };
        commodityMap.set(commodityKey, item);
      } else if (commodityIsCollected) {
        item.isCollected = true;
      }
      const safePercentage = Math.max(0, Math.min(100, percentage));
      item.totalPercentage += safePercentage;
      item.count += 1;
      item.points.push({
        asteroidNumber,
        percentage: safePercentage
      });
    });
  });

  const commodities = Array.from(commodityMap.values()).sort((left, right) => {
    const leftRefinedTons = Number(left && left.refinedTons);
    const rightRefinedTons = Number(right && right.refinedTons);
    if (rightRefinedTons !== leftRefinedTons) {
      return rightRefinedTons - leftRefinedTons;
    }
    if (right.count !== left.count) {
      return right.count - left.count;
    }
    if (right.totalPercentage !== left.totalPercentage) {
      return right.totalPercentage - left.totalPercentage;
    }
    return left.name.localeCompare(right.name);
  });

  if (!commodities.length || asteroidNumber <= 0) {
    return null;
  }

  return {
    commodities,
    maxAsteroidNumber: asteroidNumber
  };
}
