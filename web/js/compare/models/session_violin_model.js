import { percentileInclusive } from "./compare_model.js";

function gaussianKernel(u) {
  const value = Number(u);
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.exp(-0.5 * value * value) / Math.sqrt(2 * Math.PI);
}

function estimateBandwidth(values) {
  const samples = Array.isArray(values)
    ? values.map((value) => Number(value)).filter((value) => Number.isFinite(value))
    : [];
  if (samples.length <= 1) {
    return 2.5;
  }
  const mean = samples.reduce((total, value) => total + value, 0) / samples.length;
  const variance = samples.reduce((total, value) => total + ((value - mean) ** 2), 0) / Math.max(1, samples.length - 1);
  const standardDeviation = Math.sqrt(Math.max(0, variance));
  const q25 = percentileInclusive(samples, 0.25);
  const q75 = percentileInclusive(samples, 0.75);
  const iqr = Number.isFinite(q25) && Number.isFinite(q75) ? Math.max(0, q75 - q25) : 0;
  const sigmaCandidates = [
    Number.isFinite(standardDeviation) && standardDeviation > 0 ? standardDeviation : null,
    Number.isFinite(iqr) && iqr > 0 ? (iqr / 1.34) : null,
  ].filter((value) => Number.isFinite(value) && value > 0);
  const sigma = sigmaCandidates.length ? Math.min(...sigmaCandidates) : 1;
  const bandwidth = 0.9 * sigma * Math.pow(samples.length, -0.2);
  return Math.max(1.25, Number.isFinite(bandwidth) && bandwidth > 0 ? bandwidth : 2.5);
}

function buildDensityPoints(values, yMax, step) {
  const samples = Array.isArray(values)
    ? values.map((value) => Number(value)).filter((value) => Number.isFinite(value))
    : [];
  const upperBound = Math.max(5, Number.isFinite(yMax) ? yMax : 100);
  const increment = Math.max(0.5, Number.isFinite(step) ? step : 1);
  const bandwidth = estimateBandwidth(samples);
  const densityPoints = [];
  for (let y = 0; y <= upperBound + 0.0001; y += increment) {
    let density = 0;
    if (samples.length) {
      density = samples.reduce((total, value) => total + gaussianKernel((y - value) / bandwidth), 0)
        / (samples.length * bandwidth);
    }
    densityPoints.push({
      y: Number(y.toFixed(4)),
      density,
    });
  }
  return {
    bandwidth,
    densityPoints,
    peakDensity: densityPoints.reduce((peak, point) => Math.max(peak, Number(point.density) || 0), 0),
  };
}

function roundUpToStep(value, step) {
  const safeStep = Math.max(1, Number(step) || 1);
  const safeValue = Math.max(0, Number(value) || 0);
  return Math.ceil(safeValue / safeStep) * safeStep;
}

export function clusterSessionValueMarkers(values, proximityThreshold) {
  const samples = Array.isArray(values)
    ? values
      .map((entry) => {
        if (entry && typeof entry === "object") {
          const value = Number(entry.value);
          if (!Number.isFinite(value)) {
            return null;
          }
          return {
            value,
            source: entry,
          };
        }
        const value = Number(entry);
        if (!Number.isFinite(value)) {
          return null;
        }
        return {
          value,
          source: { value },
        };
      })
      .filter((entry) => !!entry)
      .sort((left, right) => left.value - right.value)
    : [];
  if (!samples.length) {
    return [];
  }
  const threshold = Math.max(0, Number(proximityThreshold) || 0);
  const clusters = [];
  let currentCluster = [samples[0]];

  const pushCluster = () => {
    if (!currentCluster.length) {
      return;
    }
    const sum = currentCluster.reduce((total, entry) => total + entry.value, 0);
    clusters.push({
      value: sum / currentCluster.length,
      count: currentCluster.length,
      minValue: currentCluster[0].value,
      maxValue: currentCluster[currentCluster.length - 1].value,
      values: currentCluster.map((entry) => entry.value),
      members: currentCluster.map((entry) => entry.source),
    });
    currentCluster = [];
  };

  for (let index = 1; index < samples.length; index += 1) {
    const value = samples[index];
    const previousValue = currentCluster[currentCluster.length - 1];
    if ((value.value - previousValue.value) <= threshold) {
      currentCluster.push(value);
      continue;
    }
    pushCluster();
    currentCluster.push(value);
  }
  pushCluster();
  return clusters;
}

export function buildSessionViolinModel(options) {
  const {
    ring,
    commodityKey,
    excludeZeroValueAsteroids = false,
    yStep = 1,
    yAxisStep = 5,
  } = options || {};
  const asteroidList = Array.isArray(ring && ring.asteroidList) ? ring.asteroidList : [];
  const sessionMap = new Map();
  asteroidList.forEach((asteroid, index) => {
    const sessionGuid = typeof asteroid && typeof asteroid.sessionGuid === "string"
      ? asteroid.sessionGuid.trim()
      : "";
    if (!sessionGuid) {
      return;
    }
    const rawValue = Number(asteroid && asteroid.commodityPercentages && asteroid.commodityPercentages.get(commodityKey));
    const value = Number.isFinite(rawValue) ? Math.max(0, rawValue) : 0;
    if (excludeZeroValueAsteroids && value <= 0) {
      return;
    }
    let session = sessionMap.get(sessionGuid);
    if (!session) {
      session = {
        sessionGuid,
        orderIndex: index,
        asteroidSamples: [],
        values: [],
      };
      sessionMap.set(sessionGuid, session);
    }
    session.asteroidSamples.push({
      asteroidId: Number.isFinite(Number(asteroid && asteroid.asteroidId))
        ? Math.trunc(Number(asteroid.asteroidId))
        : null,
      duplicate: !!(asteroid && asteroid.duplicate),
      present: Number.isFinite(rawValue),
      value,
    });
    session.values.push(value);
  });

  const sessions = Array.from(sessionMap.values())
    .sort((left, right) => left.orderIndex - right.orderIndex)
    .map((session, index) => {
      const sortedValues = [...session.values].sort((left, right) => left - right);
      const sortedAsteroidSamples = [...session.asteroidSamples].sort((left, right) => left.value - right.value);
      const count = sortedValues.length;
      const maxValue = count ? sortedValues[count - 1] : 0;
      const minValue = count ? sortedValues[0] : 0;
      const meanValue = count
        ? (sortedValues.reduce((total, value) => total + value, 0) / count)
        : 0;
      return {
        sessionGuid: session.sessionGuid,
        sessionIndex: index,
        sessionLabel: `S${index + 1}`,
        asteroidSamples: sortedAsteroidSamples,
        values: sortedValues,
        asteroidCount: count,
        minValue,
        maxValue,
        averageYield: meanValue,
        median: percentileInclusive(sortedValues, 0.5),
        p25: percentileInclusive(sortedValues, 0.25),
        p75: percentileInclusive(sortedValues, 0.75),
        nonZeroCount: sortedValues.filter((value) => value > 0).length,
      };
    });

  const observedPeak = sessions.reduce((peak, session) => Math.max(peak, Number(session.maxValue) || 0), 0);
  const yMax = Math.max(10, roundUpToStep(observedPeak, yAxisStep));
  const nextSessions = sessions.map((session) => {
    const density = buildDensityPoints(session.values, yMax, yStep);
    return {
      ...session,
      bandwidth: density.bandwidth,
      densityPoints: density.densityPoints,
      peakDensity: density.peakDensity,
    };
  });
  const maxDensity = nextSessions.reduce((peak, session) => Math.max(peak, Number(session.peakDensity) || 0), 0);
  const totalAsteroids = nextSessions.reduce((total, session) => total + session.asteroidCount, 0);
  const totalPercent = nextSessions.reduce((sum, session) => (
    sum + session.values.reduce((sessionSum, value) => sessionSum + value, 0)
  ), 0);

  return {
    sessions: nextSessions,
    maxDensity,
    totalAsteroids,
    averageYield: totalAsteroids > 0 ? (totalPercent / totalAsteroids) : null,
    yMax,
  };
}
