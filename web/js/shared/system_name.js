export function extractSystemNameFromRingName(value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) {
    return "";
  }

  const ringMatch = text.match(/^(.*?)(?:\s+([A-Z]))\s+Ring$/);
  if (!ringMatch) {
    return text;
  }

  const base = String(ringMatch[1] || "").trim();
  if (!base) {
    return text;
  }

  const suffixPatterns = [
    /^(.*)\s+[A-Z]{1,2}\s+\d+$/,
    /^(.*)\s+\d+\s+[A-Z]$/,
    /^(.*)\s+\d+$/,
  ];
  for (const pattern of suffixPatterns) {
    const match = base.match(pattern);
    const candidate = match && typeof match[1] === "string" ? match[1].trim() : "";
    if (candidate) {
      return candidate;
    }
  }

  return base;
}
