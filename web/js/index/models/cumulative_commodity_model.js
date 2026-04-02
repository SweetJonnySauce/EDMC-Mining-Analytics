export function buildCumulativeCommoditySeries(options) {
  const {
    sessionData,
    normalizeCommodityName,
    normalizeCommodityKey,
    asNumber,
  } = options || {};
  const normalizeName = typeof normalizeCommodityName === "function"
    ? normalizeCommodityName
    : ((value) => String(value || "").trim().toLowerCase());
  const normalizeKey = typeof normalizeCommodityKey === "function"
    ? normalizeCommodityKey
    : ((value) => String(value || "").trim().toLowerCase());
  const readNumber = typeof asNumber === "function"
    ? asNumber
    : ((value) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : 0;
    });

  const meta = sessionData && typeof sessionData === "object" ? (sessionData.meta || {}) : {};
  const cargoCapacityRaw = Number(meta.cargo_capacity);
  const cargoCapacity = Number.isFinite(cargoCapacityRaw) && cargoCapacityRaw > 0
    ? cargoCapacityRaw
    : null;
  const events = Array.isArray(sessionData && sessionData.events) ? sessionData.events : [];
  const estimatedSell = meta && typeof meta.estimated_sell === "object" ? meta.estimated_sell : {};
  const byCommodity = Array.isArray(estimatedSell.by_commodity) ? estimatedSell.by_commodity : [];
  const sellPriceByCommodity = new Map();
  const sellPriceByCommodityKey = new Map();
  const setSellPriceAlias = (candidate, sellPrice) => {
    const normalizedName = normalizeName(candidate);
    if (normalizedName) {
      sellPriceByCommodity.set(normalizedName, sellPrice);
    }
    const normalizedAliasKey = normalizeKey(candidate);
    if (normalizedAliasKey) {
      sellPriceByCommodityKey.set(normalizedAliasKey, sellPrice);
    }
  };
  const resolveSellPrice = (candidate) => {
    const normalizedName = normalizeName(candidate);
    if (normalizedName && sellPriceByCommodity.has(normalizedName)) {
      return readNumber(sellPriceByCommodity.get(normalizedName));
    }
    const normalizedAliasKey = normalizeKey(candidate);
    if (normalizedAliasKey && sellPriceByCommodityKey.has(normalizedAliasKey)) {
      return readNumber(sellPriceByCommodityKey.get(normalizedAliasKey));
    }
    return 0;
  };
  byCommodity.forEach((entry) => {
    if (!entry || typeof entry !== "object") {
      return;
    }
    const sellPrice = Number(entry.sell_price);
    if (!Number.isFinite(sellPrice) || sellPrice < 0) {
      return;
    }
    [entry.name, entry.key, entry.commodity].forEach((candidate) => {
      setSellPriceAlias(candidate, sellPrice);
    });
  });
  const readCargoLimpetCount = (details, inventory) => {
    const directLimpets = Number(details && details.limpets);
    if (Number.isFinite(directLimpets) && directLimpets >= 0) {
      return directLimpets;
    }
    const source = inventory && typeof inventory === "object" ? inventory : {};
    const inventoryLimpets = Number(
      source.Limpets ?? source.limpets ?? source.Drones ?? source.drones
    );
    if (Number.isFinite(inventoryLimpets) && inventoryLimpets >= 0) {
      return inventoryLimpets;
    }
    return null;
  };
  const readInventoryCargoExcludingDrones = (inventory) => {
    const source = inventory && typeof inventory === "object" ? inventory : {};
    return Object.entries(source).reduce((sum, [name, value]) => {
      const key = String(name || "").trim().toLowerCase();
      if (!key || key === "drones") {
        return sum;
      }
      const numeric = Number(value);
      if (!Number.isFinite(numeric) || numeric <= 0) {
        return sum;
      }
      return sum + numeric;
    }, 0);
  };
  const hasLimpetsInInventory = (inventory) => {
    const source = inventory && typeof inventory === "object" ? inventory : {};
    return Object.keys(source).some((name) => String(name || "").trim().toLowerCase() === "limpets");
  };
  const cargoSnapshots = events
    .map((event, index) => {
      if (!event || event.type !== "cargo") {
        return null;
      }
      const timestamp = typeof event.timestamp === "string" ? event.timestamp : "";
      const ms = Date.parse(timestamp);
      if (!Number.isFinite(ms)) {
        return null;
      }
      const details = event.details && typeof event.details === "object" ? event.details : {};
      const inventory = details.inventory;
      if (!inventory || typeof inventory !== "object" || Array.isArray(inventory)) {
        return null;
      }
      const limpetCount = readCargoLimpetCount(details, inventory);
      const totalCargoRaw = Number(details.total_cargo);
      const totalCargo = Number.isFinite(totalCargoRaw) && totalCargoRaw >= 0 ? totalCargoRaw : null;
      return { ms, inventory, index, limpetCount, totalCargo };
    })
    .filter((snapshot) => !!snapshot)
    .sort((left, right) => {
      if (left.ms !== right.ms) {
        return left.ms - right.ms;
      }
      return left.index - right.index;
    });

  if (!cargoSnapshots.length) {
    return null;
  }

  const excluded = new Set(["drones", "limpets"]);
  const commodityNames = new Set();
  cargoSnapshots.forEach((snapshot) => {
    Object.keys(snapshot.inventory).forEach((name) => {
      const clean = typeof name === "string" ? name.trim() : "";
      if (!clean || excluded.has(clean.toLowerCase())) {
        return;
      }
      commodityNames.add(clean);
    });
    if (Number.isFinite(snapshot.limpetCount) && snapshot.limpetCount >= 0) {
      commodityNames.add("Limpets");
    }
  });

  if (!commodityNames.size) {
    return null;
  }

  const names = Array.from(commodityNames).sort((left, right) => left.localeCompare(right));
  const metaStartMs = Date.parse(meta.start_time || "");
  const metaEndMs = Date.parse(meta.end_time || "");
  const startMs = Number.isFinite(metaStartMs) ? metaStartMs : cargoSnapshots[0].ms;
  const endCandidate = Number.isFinite(metaEndMs) ? metaEndMs : cargoSnapshots[cargoSnapshots.length - 1].ms;
  const endMs = endCandidate > startMs ? endCandidate : (startMs + 1);

  const series = names.map((name) => {
    const sellPrice = resolveSellPrice(name);
    const points = cargoSnapshots.map((snapshot) => {
      const rawValue = name === "Limpets"
        ? Number(snapshot.limpetCount)
        : Number(snapshot.inventory[name]);
      const quantity = Number.isFinite(rawValue) && rawValue >= 0 ? rawValue : 0;
      const profit = sellPrice > 0 ? (quantity * sellPrice) : 0;
      return { ms: snapshot.ms, quantity, profit };
    });
    const lastPoint = points[points.length - 1] || null;
    if (lastPoint && lastPoint.ms < endMs) {
      points.push({
        ms: endMs,
        quantity: readNumber(lastPoint.quantity),
        profit: readNumber(lastPoint.profit)
      });
    }
    return { name, points };
  });

  if (cargoCapacity !== null) {
    const points = cargoSnapshots.map((snapshot) => {
      let occupied = 0;
      if (Number.isFinite(snapshot.totalCargo) && Number.isFinite(snapshot.limpetCount) && snapshot.limpetCount >= 0) {
        occupied = Math.max(0, readNumber(snapshot.totalCargo) + readNumber(snapshot.limpetCount));
      } else {
        occupied = readInventoryCargoExcludingDrones(snapshot.inventory);
        if (!hasLimpetsInInventory(snapshot.inventory) && Number.isFinite(snapshot.limpetCount) && snapshot.limpetCount >= 0) {
          occupied += snapshot.limpetCount;
        }
      }
      const quantity = Math.max(0, cargoCapacity - occupied);
      return { ms: snapshot.ms, quantity, profit: 0 };
    });
    const lastPoint = points[points.length - 1] || null;
    if (lastPoint && lastPoint.ms < endMs) {
      points.push({
        ms: endMs,
        quantity: readNumber(lastPoint.quantity),
        profit: 0
      });
    }
    series.push({
      name: "Empty Cargo Space",
      points
    });
  }

  return { startMs, endMs, series };
}
