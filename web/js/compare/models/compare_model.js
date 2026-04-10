export function percentileInclusive(values, percentile) {
  const p = Number(percentile);
  if (!Array.isArray(values) || values.length === 0 || !Number.isFinite(p)) {
    return null;
  }
  const clamped = Math.max(0, Math.min(1, p));
  const sorted = values
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b);
  if (!sorted.length) {
    return null;
  }
  if (sorted.length === 1) {
    return sorted[0];
  }
  // Inclusive percentile interpolation (equivalent to PERCENTILE.INC style ranking).
  const rank = (sorted.length - 1) * clamped;
  const lowIndex = Math.floor(rank);
  const highIndex = Math.ceil(rank);
  if (lowIndex === highIndex) {
    return sorted[lowIndex];
  }
  const weight = rank - lowIndex;
  return sorted[lowIndex] + ((sorted[highIndex] - sorted[lowIndex]) * weight);
}

export const DEFAULT_COMPARE_TARGET_TONS = 522;
export const DEFAULT_COMPARE_TONS_PER_PERCENT = 0.26;

export function buildCompareData(options) {
  const {
    records,
    normalizeTextKey,
    normalizeCommodityKey,
    pickCommodityLabel,
  } = options || {};
  const rows = Array.isArray(records) ? records : [];
  const normalizeText = typeof normalizeTextKey === "function"
    ? normalizeTextKey
    : ((value) => String(value || "").trim().toLowerCase());
  const normalizeCommodity = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const pickLabel = typeof pickCommodityLabel === "function"
    ? pickCommodityLabel
    : ((current, candidate) => {
      const next = typeof candidate === "string" ? candidate.trim() : "";
      if (!next) {
        return current || "";
      }
      if (!current) {
        return next;
      }
      const currentHasSpace = /\s/.test(current);
      const nextHasSpace = /\s/.test(next);
      if (!currentHasSpace && nextHasSpace) {
        return next;
      }
      return current;
    });

  const ringByKey = new Map();
  const commodityLabels = new Map();
  rows.forEach((row) => {
    if (!row || typeof row !== "object") {
      return;
    }
    const sessionGuid = typeof row.session_guid === "string" ? row.session_guid.trim() : "";
    const ringName = typeof row.ring_name === "string" ? row.ring_name.trim() : "";
    const commodityName = typeof row.commodity_name === "string" ? row.commodity_name.trim() : "";
    const asteroidRaw = Number(row.asteroid_id);
    const percentage = Number(row.percentage);
    if (!sessionGuid || !ringName || !commodityName || !Number.isFinite(asteroidRaw) || asteroidRaw < 1 || !Number.isFinite(percentage)) {
      return;
    }
    const ringKey = normalizeText(ringName);
    if (!ringKey) {
      return;
    }
    let ring = ringByKey.get(ringKey);
    if (!ring) {
      ring = {
        ringKey,
        ringName,
        asteroids: new Map(),
        ringTypeCounts: new Map(),
        reserveLevelCounts: new Map()
      };
      ringByKey.set(ringKey, ring);
    }
    const ringType = typeof row.ring_type === "string" ? row.ring_type.trim() : "";
    if (ringType) {
      ring.ringTypeCounts.set(ringType, (ring.ringTypeCounts.get(ringType) || 0) + 1);
    }
    const reserveLevel = typeof row.reserve_level === "string" ? row.reserve_level.trim() : "";
    if (reserveLevel) {
      ring.reserveLevelCounts.set(reserveLevel, (ring.reserveLevelCounts.get(reserveLevel) || 0) + 1);
    }
    const asteroidId = Math.floor(asteroidRaw);
    const asteroidKey = `${sessionGuid}::${asteroidId}`;
    let asteroid = ring.asteroids.get(asteroidKey);
    if (!asteroid) {
      asteroid = {
        sessionGuid,
        asteroidId,
        duplicate: false,
        commodityPercentages: new Map()
      };
      ring.asteroids.set(asteroidKey, asteroid);
    }
    asteroid.duplicate = asteroid.duplicate || row.duplicate_prospector === true;
    const commodityKey = normalizeCommodity(commodityName);
    if (!commodityKey) {
      return;
    }
    commodityLabels.set(commodityKey, pickLabel(commodityLabels.get(commodityKey) || "", commodityName));
    const safePct = Math.max(0, percentage);
    const previous = asteroid.commodityPercentages.get(commodityKey);
    if (!Number.isFinite(previous) || safePct > previous) {
      asteroid.commodityPercentages.set(commodityKey, safePct);
    }
  });
  const commodities = Array.from(commodityLabels.entries())
    .map(([key, label]) => ({ key, label: label || key }))
    .sort((a, b) => a.label.localeCompare(b.label));
  const rings = Array.from(ringByKey.values())
    .map((ring) => ({
      ...ring,
      asteroidList: Array.from(ring.asteroids.values())
    }))
    .sort((a, b) => a.ringName.localeCompare(b.ringName));
  return { rings, commodities };
}

export function buildScopedAsteroidRows(options) {
  const {
    ring,
    commodityKey,
  } = options || {};
  const asteroids = Array.isArray(ring && ring.asteroidList) ? ring.asteroidList : [];
  const allAsteroids = asteroids
    .map((asteroid) => {
      const rawValue = Number(asteroid && asteroid.commodityPercentages && asteroid.commodityPercentages.get(commodityKey));
      const present = Number.isFinite(rawValue);
      const value = present ? Math.max(0, rawValue) : 0;
      return {
        value,
        present,
        sessionGuid: asteroid.sessionGuid
      };
    })
    .filter((row) => !!row);
  const presentAsteroids = allAsteroids.filter((item) => item.present);
  const scopedAsteroids = allAsteroids;
  return { allAsteroids, presentAsteroids, scopedAsteroids };
}

export function buildAboveThresholdPlanRows(options) {
  const {
    allAsteroids,
    interval,
    xMax,
    targetTons,
    tonsPerPercentagePoint,
  } = options || {};
  const asteroidRows = Array.isArray(allAsteroids) ? allAsteroids : [];
  const safeInterval = Math.max(1, Number(interval) || 1);
  const safeTonsPerPercent = Number(tonsPerPercentagePoint) > 0
    ? Number(tonsPerPercentagePoint)
    : DEFAULT_COMPARE_TONS_PER_PERCENT;
  const safeTargetTons = Number(targetTons) > 0
    ? Number(targetTons)
    : DEFAULT_COMPARE_TARGET_TONS;
  const totalAsteroids = asteroidRows.length;
  if (!totalAsteroids) {
    return [];
  }
  const maxObserved = asteroidRows.reduce((peak, item) => (
    Math.max(peak, Math.max(0, Number(item && item.value) || 0))
  ), 0);
  const safeXMax = Number.isFinite(xMax) && xMax > 0
    ? Math.max(safeInterval, Number(xMax))
    : Math.max(safeInterval, Math.ceil(maxObserved / safeInterval) * safeInterval);
  const bins = Math.max(1, Math.ceil(safeXMax / safeInterval));
  const targetPercentTotal = safeTargetTons / safeTonsPerPercent;
  const rows = [];
  for (let index = 1; index < bins; index += 1) {
    const cutoff = index * safeInterval;
    const qualifying = asteroidRows.filter((item) => Number(item && item.value) >= cutoff);
    const qualifyingCount = qualifying.length;
    const averageYieldPercent = qualifyingCount
      ? (qualifying.reduce((total, item) => (
        total + Math.max(0, Number(item && item.value) || 0)
      ), 0) / qualifyingCount)
      : null;
    const aboveThresholdShare = totalAsteroids > 0
      ? (qualifyingCount / totalAsteroids)
      : 0;
    const asteroidsToMine = Number.isFinite(averageYieldPercent) && averageYieldPercent > 0
      ? Math.ceil(targetPercentTotal / averageYieldPercent)
      : null;
    const asteroidsToProspect = Number.isFinite(asteroidsToMine) && aboveThresholdShare > 0
      ? Math.ceil(asteroidsToMine / aboveThresholdShare)
      : null;
    rows.push({
      cutoffYieldPercent: cutoff,
      averageYieldPercent,
      aboveThresholdShare,
      qualifyingAsteroidsCount: qualifyingCount,
      totalAsteroidsCount: totalAsteroids,
      asteroidsToMine,
      asteroidsToProspect,
      hasRealData: qualifyingCount > 0,
    });
  }
  return rows;
}

export function interpolateMissingValuesBetweenRealBins(options) {
  const {
    entries,
    readValue,
    isRealEntry,
    strategy,
  } = options || {};
  const items = Array.isArray(entries) ? entries : [];
  const getValue = typeof readValue === "function"
    ? readValue
    : ((entry) => entry);
  const getIsReal = typeof isRealEntry === "function"
    ? isRealEntry
    : ((entry) => !!(entry && entry.hasRealData));
  const interpolationStrategy = strategy === "previous" || strategy === "next"
    ? strategy
    : "linear";
  const rawValues = items.map((entry, index) => {
    const value = Number(getValue(entry, index));
    return Number.isFinite(value) ? value : null;
  });
  const realFlags = items.map((entry, index) => !!getIsReal(entry, index));
  return items.map((entry, index) => {
    const rawValue = rawValues[index];
    if (realFlags[index]) {
      return { value: rawValue, inferred: false };
    }
    let previousRealIndex = index - 1;
    while (previousRealIndex >= 0 && !realFlags[previousRealIndex]) {
      previousRealIndex -= 1;
    }
    let nextRealIndex = index + 1;
    while (nextRealIndex < items.length && !realFlags[nextRealIndex]) {
      nextRealIndex += 1;
    }
    if (
      interpolationStrategy === "previous"
      && previousRealIndex >= 0
      && Number.isFinite(rawValues[previousRealIndex])
    ) {
      return { value: rawValues[previousRealIndex], inferred: true };
    }
    if (
      interpolationStrategy === "next"
      && nextRealIndex < items.length
      && Number.isFinite(rawValues[nextRealIndex])
    ) {
      return { value: rawValues[nextRealIndex], inferred: true };
    }
    if (
      previousRealIndex >= 0
      && nextRealIndex < items.length
      && Number.isFinite(rawValues[previousRealIndex])
      && Number.isFinite(rawValues[nextRealIndex])
    ) {
      const span = nextRealIndex - previousRealIndex;
      const ratio = span > 0 ? ((index - previousRealIndex) / span) : 0;
      const interpolatedValue = rawValues[previousRealIndex]
        + ((rawValues[nextRealIndex] - rawValues[previousRealIndex]) * ratio);
      return { value: interpolatedValue, inferred: true };
    }
    return { value: rawValue, inferred: false };
  });
}

export function buildRingCommodityModel(options) {
  const {
    ring,
    commodityKey,
    interval,
    forcedXMax,
    targetTons,
  } = options || {};
  const safeInterval = Math.max(1, Number(interval) || 1);
  const safeTargetTons = Number(targetTons) > 0
    ? Number(targetTons)
    : DEFAULT_COMPARE_TARGET_TONS;
  const scopedRows = buildScopedAsteroidRows({ ring, commodityKey });
  const allAsteroids = Array.isArray(scopedRows && scopedRows.allAsteroids)
    ? scopedRows.allAsteroids
    : [];
  const presentAsteroids = Array.isArray(scopedRows && scopedRows.presentAsteroids)
    ? scopedRows.presentAsteroids
    : [];
  const scopedAsteroids = Array.isArray(scopedRows && scopedRows.scopedAsteroids)
    ? scopedRows.scopedAsteroids
    : [];
  const normalizedForcedXMax = Number.isFinite(forcedXMax) && forcedXMax > 0
    ? Math.max(safeInterval, forcedXMax)
    : null;
  const percentileValues = scopedAsteroids.map((item) => item.value);
  const p90 = percentileInclusive(percentileValues, 0.9);
  const p75 = percentileInclusive(percentileValues, 0.75);
  const p50 = percentileInclusive(percentileValues, 0.5);
  const p25 = percentileInclusive(percentileValues, 0.25);
  if (!scopedAsteroids.length) {
    return {
      averageYield: null,
      p90: null,
      p75: null,
      p50: null,
      p25: null,
      asteroidsCount: 0,
      presentAsteroidsCount: presentAsteroids.length,
      sessionsCount: 0,
      points: [],
      aboveThresholdPlanRows: [],
      targetTons: safeTargetTons,
      tonsPerPercentagePoint: DEFAULT_COMPARE_TONS_PER_PERCENT,
      yMax: 1,
      xMax: normalizedForcedXMax || safeInterval
    };
  }
  const maxObserved = scopedAsteroids.reduce((peak, item) => Math.max(peak, item.value), 0);
  const xMax = normalizedForcedXMax || Math.max(safeInterval, Math.ceil(maxObserved / safeInterval) * safeInterval);
  const bins = Math.max(1, Math.ceil(xMax / safeInterval));
  const counts = new Array(bins).fill(0);
  let percentSum = 0;
  const sessionGuids = new Set();
  scopedAsteroids.forEach((item) => {
    percentSum += item.value;
    sessionGuids.add(item.sessionGuid);
    let index = item.value >= xMax ? (bins - 1) : Math.floor(item.value / safeInterval);
    if (index < 0) {
      index = 0;
    }
    if (index >= bins) {
      index = bins - 1;
    }
    counts[index] += 1;
  });
  const points = [];
  const cumulativeForwardCounts = new Array(bins).fill(0);
  const cumulativeReverseCounts = new Array(bins).fill(0);
  let running = 0;
  for (let index = 0; index < bins; index += 1) {
    running += counts[index];
    cumulativeForwardCounts[index] = running;
  }
  let reverseRunning = 0;
  for (let index = bins - 1; index >= 0; index -= 1) {
    reverseRunning += counts[index];
    cumulativeReverseCounts[index] = reverseRunning;
  }
  for (let index = 0; index < bins; index += 1) {
    const intervalStart = index * safeInterval;
    const intervalEnd = Math.min(xMax, intervalStart + safeInterval);
    const center = intervalStart + ((intervalEnd - intervalStart) / 2);
    points.push({
      index,
      intervalStart,
      intervalEnd,
      center,
      binCount: counts[index],
      hasRealData: counts[index] > 0,
      total: cumulativeForwardCounts[index],
      totalForward: cumulativeForwardCounts[index],
      totalReverse: cumulativeReverseCounts[index]
    });
  }
  const aboveThresholdPlanRows = buildAboveThresholdPlanRows({
    allAsteroids,
    interval: safeInterval,
    xMax,
    targetTons: safeTargetTons,
    tonsPerPercentagePoint: DEFAULT_COMPARE_TONS_PER_PERCENT,
  });
  return {
    averageYield: percentSum / scopedAsteroids.length,
    p90,
    p75,
    p50,
    p25,
    asteroidsCount: scopedAsteroids.length,
    presentAsteroidsCount: presentAsteroids.length,
    sessionsCount: sessionGuids.size,
    points,
    aboveThresholdPlanRows,
    targetTons: safeTargetTons,
    tonsPerPercentagePoint: DEFAULT_COMPARE_TONS_PER_PERCENT,
    yMax: Math.max(1, running),
    xMax
  };
}
