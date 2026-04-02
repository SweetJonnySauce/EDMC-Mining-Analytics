export function normalizeHistogramBinSize(value) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) {
    return 10;
  }
  const rounded = Math.floor(raw);
  return Math.max(1, Math.min(100, rounded));
}

function normalizeYieldPopulationMode(value) {
  return String(value || "").trim().toLowerCase() === "present" ? "present" : "all";
}

export function resolveSessionGuid(meta, filename) {
  const source = meta && typeof meta === "object" ? meta : {};
  const direct = typeof source.session_guid === "string" ? source.session_guid.trim() : "";
  if (direct) {
    return direct;
  }
  const cleanName = typeof filename === "string" ? filename.trim() : "";
  if (/^session_data_\d+\.json$/.test(cleanName)) {
    return `sim-${cleanName.replace(/\.json$/i, "")}`;
  }
  return "";
}

export function resolveSessionRingLabel(sessionData) {
  const payload = sessionData && typeof sessionData === "object" ? sessionData : {};
  const meta = payload.meta && typeof payload.meta === "object" ? payload.meta : {};
  const location = meta.location && typeof meta.location === "object" ? meta.location : {};
  const ringCandidate = (
    (typeof location.ring === "string" && location.ring.trim() ? location.ring.trim() : "")
    || (typeof location.body === "string" && location.body.trim() ? location.body.trim() : "")
    || (typeof location.system === "string" && location.system.trim() ? location.system.trim() : "")
    || (typeof meta.ring === "string" && meta.ring.trim() ? meta.ring.trim() : "")
    || (typeof meta.body === "string" && meta.body.trim() ? meta.body.trim() : "")
    || (typeof meta.system === "string" && meta.system.trim() ? meta.system.trim() : "")
  );
  return ringCandidate || "Unknown";
}

export function parseProspectedAsteroidSummaryText(payload) {
  const lines = String(payload || "").split(/\r?\n/);
  const parsed = [];
  for (const line of lines) {
    const text = String(line || "").trim();
    if (!text) {
      continue;
    }
    try {
      const row = JSON.parse(text);
      if (!row || typeof row !== "object") {
        continue;
      }
      const sessionGuid = typeof row.session_guid === "string" ? row.session_guid.trim() : "";
      const ringName = typeof row.ring_name === "string" && row.ring_name.trim()
        ? row.ring_name.trim()
        : "Unknown";
      const commodityName = typeof row.commodity_name === "string" ? row.commodity_name.trim() : "";
      const asteroidRaw = Number(row.asteroid_id);
      const percentage = Number(row.percentage);
      if (!sessionGuid || !commodityName || !Number.isFinite(asteroidRaw) || asteroidRaw < 1 || !Number.isFinite(percentage)) {
        continue;
      }
      parsed.push({
        session_guid: sessionGuid,
        asteroid_id: Math.floor(asteroidRaw),
        ring_name: ringName,
        commodity_name: commodityName,
        percentage: Math.max(0, percentage),
        duplicate_prospector: row.duplicate_prospector === true
      });
    } catch (_error) {
      // Skip invalid JSON lines.
    }
  }
  return parsed;
}

export function buildProspectHistogramModel(options) {
  const {
    sessionData,
    includeDuplicates,
    showOnlyCollected,
    histogramBinSizeOverride,
    selectedYieldPopulationMode,
    runtimeAnalysisSettings,
    collectRefinedCommodityKeys,
    normalizeCommodityKey,
    normalizeTextKey,
  } = options || {};
  const payload = sessionData && typeof sessionData === "object" ? sessionData : {};
  const meta = payload.meta && typeof payload.meta === "object" ? payload.meta : {};
  const configuredBinSize = (
    histogramBinSizeOverride
    ?? meta.histogram_bin_size
    ?? (runtimeAnalysisSettings && runtimeAnalysisSettings.histogram_bin_size)
  );
  const binSize = normalizeHistogramBinSize(configuredBinSize);
  const normalizeCommodity = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const normalizeText = typeof normalizeTextKey === "function"
    ? normalizeTextKey
    : ((value) => String(value || "").trim().toLowerCase());
  const yieldPopulationMode = normalizeYieldPopulationMode(selectedYieldPopulationMode);

  const events = Array.isArray(payload.events) ? payload.events : [];
  const collectedCommodityKeys = typeof collectRefinedCommodityKeys === "function"
    ? collectRefinedCommodityKeys(events)
    : new Set();
  const commodityLabelByKey = new Map();
  const asteroids = [];
  events.forEach((event) => {
    if (!event || event.type !== "prospected_asteroid") {
      return;
    }
    const details = event.details && typeof event.details === "object" ? event.details : {};
    if (!includeDuplicates && details.duplicate === true) {
      return;
    }
    const materials = Array.isArray(details.materials) ? details.materials : [];
    const asteroid = {
      commodityPercentages: new Map()
    };
    materials.forEach((material) => {
      if (!material || typeof material !== "object") {
        return;
      }
      const name = typeof material.name === "string" ? material.name.trim() : "";
      const pctRaw = Number(material.percentage);
      if (!name || !Number.isFinite(pctRaw)) {
        return;
      }
      const key = normalizeCommodity(name) || normalizeText(name) || name.toLowerCase();
      if (!key) {
        return;
      }
      if (!commodityLabelByKey.has(key)) {
        commodityLabelByKey.set(key, name);
      }
      const pct = Math.max(0, pctRaw);
      const prior = asteroid.commodityPercentages.get(key);
      if (!Number.isFinite(prior) || pct > prior) {
        asteroid.commodityPercentages.set(key, pct);
      }
    });
    asteroids.push(asteroid);
  });

  const eventCommodityMap = new Map();
  asteroids.forEach((asteroid) => {
    asteroid.commodityPercentages.forEach((_value, key) => {
      if (showOnlyCollected && !collectedCommodityKeys.has(key)) {
        return;
      }
      if (!eventCommodityMap.has(key)) {
        eventCommodityMap.set(key, {
          name: commodityLabelByKey.get(key) || key,
          percentages: [],
          total: 0,
          presentTotal: 0
        });
      }
    });
  });
  asteroids.forEach((asteroid) => {
    eventCommodityMap.forEach((item, key) => {
      const raw = Number(asteroid.commodityPercentages.get(key));
      const present = Number.isFinite(raw);
      if (!present && yieldPopulationMode === "present") {
        return;
      }
      const value = present ? Math.max(0, raw) : 0;
      item.percentages.push(value);
      item.total += 1;
      if (present) {
        item.presentTotal += 1;
      }
    });
  });

  const eventResult = Array.from(eventCommodityMap.values())
    .filter((item) => item.total > 0 && Array.isArray(item.percentages) && item.percentages.length > 0)
    .map((item) => {
      const maxObserved = item.percentages.reduce((peak, value) => Math.max(peak, value), 0);
      const xMax = Math.max(binSize, Math.ceil(maxObserved / binSize) * binSize);
      const bins = Math.max(1, Math.ceil(xMax / binSize));
      const counts = new Array(bins).fill(0);
      item.percentages.forEach((pct) => {
        let index = pct >= xMax ? (bins - 1) : Math.floor(pct / binSize);
        if (index < 0) {
          index = 0;
        } else if (index >= bins) {
          index = bins - 1;
        }
        counts[index] += 1;
      });
      return {
        name: item.name,
        counts,
        total: item.total,
        presentTotal: item.presentTotal,
        xMax
      };
    });
  if (eventResult.length) {
    eventResult.sort((left, right) => {
      const leftPresent = Number.isFinite(Number(left.presentTotal)) ? Number(left.presentTotal) : Number(left.total);
      const rightPresent = Number.isFinite(Number(right.presentTotal)) ? Number(right.presentTotal) : Number(right.total);
      if (rightPresent !== leftPresent) {
        return rightPresent - leftPresent;
      }
      if (right.total !== left.total) {
        return right.total - left.total;
      }
      return left.name.localeCompare(right.name);
    });
    return {
      commodities: eventResult,
      binSize,
      bins: Math.max(1, ...eventResult.map((item) => item.counts.length))
    };
  }

  const source = payload.commodities && typeof payload.commodities === "object" ? payload.commodities : {};
  const totalAsteroidsRaw = Number(
    payload
    && payload.meta
    && payload.meta.prospected
    && payload.meta.prospected.total
  );
  const totalAsteroids = Number.isFinite(totalAsteroidsRaw) && totalAsteroidsRaw > 0
    ? Math.floor(totalAsteroidsRaw)
    : null;
  const result = [];
  Object.entries(source).forEach(([name, details]) => {
    const commodityKey = normalizeCommodity(name) || normalizeText(name) || String(name || "").trim().toLowerCase();
    if (showOnlyCollected && (!commodityKey || !collectedCommodityKeys.has(commodityKey))) {
      return;
    }
    const model = details && typeof details === "object" ? details : {};
    const breakdown = Array.isArray(model.percentage_breakdown) ? model.percentage_breakdown : [];
    const percentages = [];
    let total = 0;
    let presentTotal = 0;
    breakdown.forEach((entry) => {
      if (!entry || typeof entry !== "object") {
        return;
      }
      const pctRaw = Number(entry.percentage);
      if (!Number.isFinite(pctRaw)) {
        return;
      }
      const qtyRaw = Number(entry.count);
      const qty = Number.isFinite(qtyRaw) && qtyRaw > 0 ? Math.floor(qtyRaw) : 1;
      const pct = Math.max(0, pctRaw);
      for (let offset = 0; offset < qty; offset += 1) {
        percentages.push(pct);
      }
      total += qty;
      presentTotal += qty;
    });
    if (total > 0 && percentages.length > 0) {
      if (yieldPopulationMode === "all" && Number.isFinite(totalAsteroids) && totalAsteroids > total) {
        const zeroCount = totalAsteroids - total;
        for (let offset = 0; offset < zeroCount; offset += 1) {
          percentages.push(0);
        }
        total += zeroCount;
      }
      const maxObserved = percentages.reduce((peak, value) => Math.max(peak, value), 0);
      const xMax = Math.max(binSize, Math.ceil(maxObserved / binSize) * binSize);
      const bins = Math.max(1, Math.ceil(xMax / binSize));
      const counts = new Array(bins).fill(0);
      percentages.forEach((pct) => {
        let index = pct >= xMax ? (bins - 1) : Math.floor(pct / binSize);
        if (index < 0) {
          index = 0;
        } else if (index >= bins) {
          index = bins - 1;
        }
        counts[index] += 1;
      });
      result.push({ name, counts, total, presentTotal, xMax });
    }
  });
  result.sort((left, right) => {
    const leftPresent = Number.isFinite(Number(left.presentTotal)) ? Number(left.presentTotal) : Number(left.total);
    const rightPresent = Number.isFinite(Number(right.presentTotal)) ? Number(right.presentTotal) : Number(right.total);
    if (rightPresent !== leftPresent) {
      return rightPresent - leftPresent;
    }
    if (right.total !== left.total) {
      return right.total - left.total;
    }
    return left.name.localeCompare(right.name);
  });
  return {
    commodities: result,
    binSize,
    bins: Math.max(1, ...result.map((item) => item.counts.length))
  };
}

export function buildProspectCumulativeFrequencyModel(options) {
  const {
    sessionData,
    filename,
    summaryRecords,
    selectedHistogramCommodity,
    prospectFrequencyIncludeDuplicates,
    prospectFrequencyReverseCumulative,
    prospectFrequencyBinSize,
    selectedYieldPopulationMode,
    normalizeCommodityKey,
    normalizeTextKey,
  } = options || {};
  const normalizeCommodity = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const normalizeText = typeof normalizeTextKey === "function"
    ? normalizeTextKey
    : ((value) => String(value || "").trim().toLowerCase());
  const yieldPopulationMode = normalizeYieldPopulationMode(selectedYieldPopulationMode);

  const commodity = String(selectedHistogramCommodity || "").trim();
  if (!commodity) {
    return { error: "Select a commodity in Asteroid Percentage Histogram to view cumulative frequency." };
  }
  if (!Array.isArray(summaryRecords) || summaryRecords.length === 0) {
    return { error: "No long-term prospect summary data found yet." };
  }

  const ringLabel = resolveSessionRingLabel(sessionData);
  const ringKey = normalizeText(ringLabel);
  const commodityKey = normalizeCommodity(commodity);
  const payload = sessionData && typeof sessionData === "object" ? sessionData : {};
  const meta = payload.meta && typeof payload.meta === "object" ? payload.meta : {};
  const currentSessionGuid = resolveSessionGuid(meta, filename);

  const asteroidMap = new Map();
  summaryRecords.forEach((row) => {
    if (!row || typeof row !== "object") {
      return;
    }
    if (normalizeText(row.ring_name) !== ringKey) {
      return;
    }
    const sessionGuid = typeof row.session_guid === "string" ? row.session_guid.trim() : "";
    const asteroidRaw = Number(row.asteroid_id);
    if (!sessionGuid || !Number.isFinite(asteroidRaw) || asteroidRaw < 1) {
      return;
    }
    const asteroidId = Math.floor(asteroidRaw);
    const key = `${sessionGuid}::${asteroidId}`;
    let asteroid = asteroidMap.get(key);
    if (!asteroid) {
      asteroid = {
        sessionGuid,
        asteroidId,
        duplicate: false,
        commodityPercentages: new Map()
      };
      asteroidMap.set(key, asteroid);
    }
    asteroid.duplicate = asteroid.duplicate || row.duplicate_prospector === true;
    const rowCommodity = normalizeCommodity(row.commodity_name);
    if (!rowCommodity) {
      return;
    }
    const pct = Number(row.percentage);
    if (!Number.isFinite(pct)) {
      return;
    }
    const safePct = Math.max(0, pct);
    const prior = asteroid.commodityPercentages.get(rowCommodity);
    if (!Number.isFinite(prior) || safePct > prior) {
      asteroid.commodityPercentages.set(rowCommodity, safePct);
    }
  });

  let asteroids = Array.from(asteroidMap.values());
  if (!prospectFrequencyIncludeDuplicates) {
    asteroids = asteroids.filter((asteroid) => !asteroid.duplicate);
  }
  if (!asteroids.length) {
    return { error: "No asteroid records match the current ring and duplicate filter." };
  }

  const allAsteroids = asteroids
    .map((asteroid) => {
      const raw = Number(asteroid.commodityPercentages.get(commodityKey));
      return {
        value: Number.isFinite(raw) ? Math.max(0, raw) : 0,
        present: Number.isFinite(raw),
        sessionGuid: asteroid.sessionGuid,
        isCurrentSession: currentSessionGuid ? asteroid.sessionGuid === currentSessionGuid : false
      };
    });
  const sessionGuidsWithCommodityPresent = new Set(
    allAsteroids
      .filter((asteroid) => asteroid.present)
      .map((asteroid) => asteroid.sessionGuid)
      .filter((value) => !!value)
  );
  const eligibleAllAsteroids = allAsteroids.filter((asteroid) => (
    !!asteroid.sessionGuid && sessionGuidsWithCommodityPresent.has(asteroid.sessionGuid)
  ));
  const presentAsteroids = eligibleAllAsteroids.filter((asteroid) => asteroid.present);
  const scopedAsteroids = yieldPopulationMode === "present" ? presentAsteroids : eligibleAllAsteroids;
  if (!scopedAsteroids.length) {
    return { error: "No asteroids in this ring contain the selected commodity for the current duplicate filter." };
  }

  const sessionGuids = new Set(scopedAsteroids.map((asteroid) => asteroid.sessionGuid).filter((value) => !!value));

  const interval = Number(prospectFrequencyBinSize) === 10 ? 10 : 5;
  const maxObserved = scopedAsteroids.reduce((peak, item) => Math.max(peak, item.value), 0);
  const xMax = Math.max(interval, Math.ceil(maxObserved / interval) * interval);
  const bins = Math.max(1, Math.ceil(xMax / interval));
  const totalCounts = new Array(bins).fill(0);
  const currentCounts = new Array(bins).fill(0);
  const otherCounts = new Array(bins).fill(0);
  let percentSum = 0;

  scopedAsteroids.forEach((item) => {
    percentSum += item.value;
    let index = item.value >= xMax ? (bins - 1) : Math.floor(item.value / interval);
    if (index < 0) {
      index = 0;
    }
    if (index >= bins) {
      index = bins - 1;
    }
    totalCounts[index] += 1;
    if (item.isCurrentSession) {
      currentCounts[index] += 1;
    } else {
      otherCounts[index] += 1;
    }
  });

  const cumulativeTotalCounts = [];
  const cumulativeCurrentCounts = [];
  const cumulativeOtherCounts = [];
  let runningTotal = 0;
  let runningCurrent = 0;
  let runningOther = 0;
  for (let index = 0; index < bins; index += 1) {
    runningTotal += totalCounts[index];
    runningCurrent += currentCounts[index];
    runningOther += otherCounts[index];
    cumulativeTotalCounts.push(runningTotal);
    cumulativeCurrentCounts.push(runningCurrent);
    cumulativeOtherCounts.push(runningOther);
  }
  const reverseCumulativeTotalCounts = new Array(bins).fill(0);
  const reverseCumulativeCurrentCounts = new Array(bins).fill(0);
  const reverseCumulativeOtherCounts = new Array(bins).fill(0);
  let reverseRunningTotal = 0;
  let reverseRunningCurrent = 0;
  let reverseRunningOther = 0;
  for (let index = bins - 1; index >= 0; index -= 1) {
    reverseRunningTotal += totalCounts[index];
    reverseRunningCurrent += currentCounts[index];
    reverseRunningOther += otherCounts[index];
    reverseCumulativeTotalCounts[index] = reverseRunningTotal;
    reverseCumulativeCurrentCounts[index] = reverseRunningCurrent;
    reverseCumulativeOtherCounts[index] = reverseRunningOther;
  }
  const selectedCumulativeTotalCounts = prospectFrequencyReverseCumulative
    ? reverseCumulativeTotalCounts
    : cumulativeTotalCounts;
  const selectedCumulativeCurrentCounts = prospectFrequencyReverseCumulative
    ? reverseCumulativeCurrentCounts
    : cumulativeCurrentCounts;
  const selectedCumulativeOtherCounts = prospectFrequencyReverseCumulative
    ? reverseCumulativeOtherCounts
    : cumulativeOtherCounts;

  const points = selectedCumulativeTotalCounts.map((total, index) => {
    const intervalStart = index * interval;
    const intervalEnd = Math.min(xMax, intervalStart + interval);
    const center = intervalStart + ((intervalEnd - intervalStart) / 2);
    return {
      index,
      intervalStart,
      intervalEnd,
      center,
      binTotal: totalCounts[index],
      binCurrent: currentCounts[index],
      binOther: otherCounts[index],
      total,
      current: selectedCumulativeCurrentCounts[index],
      other: selectedCumulativeOtherCounts[index]
    };
  });
  const yMax = Math.max(1, runningTotal);
  const averageYield = scopedAsteroids.length > 0 ? (percentSum / scopedAsteroids.length) : 0;

  return {
    ringLabel,
    commodity,
    points,
    xMax,
    yMax,
    sessionsCount: sessionGuids.size,
    asteroidsCount: scopedAsteroids.length,
    presentAsteroidsCount: presentAsteroids.length,
    averageYield
  };
}
