export function parseRequestedSessionGuid(searchText) {
  try {
    const params = new URLSearchParams(typeof searchText === "string" ? searchText : "");
    return String(params.get("session_guid") || "").trim();
  } catch (_error) {
    return "";
  }
}

export function chooseInitialSessionFilename(filenames, detailsByFilename, requestedSessionGuid) {
  const sessionFiles = Array.isArray(filenames)
    ? filenames
      .map((filename) => String(filename || "").trim())
      .filter((filename) => !!filename)
    : [];
  if (!sessionFiles.length) {
    return "";
  }

  const requested = String(requestedSessionGuid || "").trim();
  if (requested) {
    for (const filename of sessionFiles) {
      const details = detailsByFilename instanceof Map
        ? detailsByFilename.get(filename)
        : (detailsByFilename && typeof detailsByFilename === "object" ? detailsByFilename[filename] : null);
      const sessionGuid = String(details && details.sessionGuid || "").trim();
      if (sessionGuid && sessionGuid === requested) {
        return filename;
      }
    }
  }

  return sessionFiles[0];
}

export function buildSessionAnalysisUrl(options) {
  const sessionGuid = String(options && options.sessionGuid || "").trim();
  const themeId = String(options && options.themeId || "").trim();
  const query = new URLSearchParams();
  if (sessionGuid) {
    query.set("session_guid", sessionGuid);
  }
  if (themeId) {
    query.set("theme", themeId);
  }
  const serialized = query.toString();
  return serialized ? `/web/index.html?${serialized}` : "/web/index.html";
}
