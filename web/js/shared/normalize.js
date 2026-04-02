export function normalizeTextKey(value) {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim().toLowerCase();
}

export function normalizeCommodityKey(value) {
  return normalizeTextKey(value).replace(/[^a-z0-9]+/g, "");
}
