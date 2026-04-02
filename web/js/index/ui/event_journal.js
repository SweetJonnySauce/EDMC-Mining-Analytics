function computeTimelineBinIndex(timestamp, context) {
  if (!context) {
    return null;
  }
  const ms = Date.parse(timestamp || "");
  if (!Number.isFinite(ms)) {
    return null;
  }
  const duration = Math.max(1, context.duration || 1);
  let index = Math.floor(((ms - context.start) / duration) * context.bins);
  if (index < 0) {
    index = 0;
  }
  if (index >= context.bins) {
    index = context.bins - 1;
  }
  return index;
}

function summarizeEventDetails(details, eventType) {
  if (!details || typeof details !== "object") {
    return "";
  }
  if (eventType === "mining_refined") {
    const localized = typeof details.type_localised === "string" ? details.type_localised.trim() : "";
    const rawType = typeof details.type === "string" ? details.type.trim() : "";
    const commodity = localized || rawType;
    return commodity || "";
  }
  if (eventType === "prospected_asteroid") {
    const parts = [];
    const content = typeof details.content === "string" ? details.content.trim() : "";
    if (content) {
      parts.push(`Content: ${content}`);
    }

    const remainingRaw = details.remaining_percent;
    const remaining = Number(remainingRaw);
    if (Number.isFinite(remaining) && remaining < 100) {
      const remainingText = Number.isInteger(remaining)
        ? String(remaining)
        : remaining.toFixed(2).replace(/\.?0+$/, "");
      parts.push(`% remaining: ${remainingText}%`);
    }

    const materials = Array.isArray(details.materials) ? details.materials : [];
    materials.forEach((material) => {
      if (!material || typeof material !== "object") {
        return;
      }
      const name = typeof material.name === "string" ? material.name.trim() : "";
      const percentRaw = Number(material.percentage);
      if (!name || !Number.isFinite(percentRaw)) {
        return;
      }
      const percentText = Number.isInteger(percentRaw)
        ? String(percentRaw)
        : percentRaw.toFixed(2).replace(/\.?0+$/, "");
      parts.push(`${name} ${percentText}%`);
    });

    return parts.join(" | ");
  }
  const parts = [];
  Object.entries(details).forEach(([key, value]) => {
    if (parts.length >= 2) {
      return;
    }
    if (
      typeof value === "string"
      || typeof value === "number"
      || typeof value === "boolean"
    ) {
      const compact = String(value).trim();
      if (!compact) {
        return;
      }
      parts.push(`${key}: ${compact}`);
    }
  });
  return parts.join(" | ");
}

export function createEventJournalController(options) {
  const {
    eventJournal,
    formatLocalDateTime,
    formatEventTypeLabel,
  } = options || {};
  const formatDateTime = typeof formatLocalDateTime === "function"
    ? formatLocalDateTime
    : () => "--";
  const formatEventLabel = typeof formatEventTypeLabel === "function"
    ? formatEventTypeLabel
    : (value) => String(value || "").trim() || "Unknown";

  let eventTimelineContext = null;
  let eventJournalFirstRowByBin = new Map();
  let eventJournalFirstTimeByBin = new Map();
  let activeJournalRow = null;
  let activeTimelineBar = null;

  function clearHighlight() {
    if (activeJournalRow) {
      activeJournalRow.classList.remove("event-journal-item--active");
    }
    if (activeTimelineBar) {
      activeTimelineBar.classList.remove("timeline-bar--linked");
    }
    activeJournalRow = null;
    activeTimelineBar = null;
  }

  function reset(optionsValue) {
    const settings = optionsValue && typeof optionsValue === "object" ? optionsValue : {};
    eventTimelineContext = null;
    eventJournalFirstRowByBin = new Map();
    eventJournalFirstTimeByBin = new Map();
    clearHighlight();
    if (settings.clearJournal && eventJournal) {
      eventJournal.innerHTML = "";
    }
  }

  function highlightJournalLink(row, timestamp) {
    clearHighlight();
    row.classList.add("event-journal-item--active");
    activeJournalRow = row;
    if (!eventTimelineContext || !Array.isArray(eventTimelineContext.barElements)) {
      return;
    }
    const index = computeTimelineBinIndex(timestamp, eventTimelineContext);
    if (index === null) {
      return;
    }
    const bar = eventTimelineContext.barElements[index];
    if (!bar) {
      return;
    }
    bar.classList.add("timeline-bar--linked");
    activeTimelineBar = bar;
  }

  function renderJournalEntries(entries) {
    if (!eventJournal) {
      return;
    }
    eventJournal.innerHTML = "";
    if (!Array.isArray(entries) || entries.length === 0) {
      const item = document.createElement("li");
      item.className = "event-journal-item";
      const text = document.createElement("span");
      text.className = "event-journal-text";
      text.textContent = "No events for current filters.";
      item.appendChild(text);
      eventJournal.appendChild(item);
      return;
    }

    entries.forEach((entry) => {
      const item = document.createElement("li");
      item.className = "event-journal-item";
      item.dataset.timestamp = entry.timestamp;
      item.addEventListener("mouseenter", () => {
        highlightJournalLink(item, entry.timestamp);
      });
      item.addEventListener("mouseleave", () => {
        clearHighlight();
      });

      const time = document.createElement("span");
      time.className = "event-journal-time";
      time.textContent = formatDateTime(entry.timestamp);

      const text = document.createElement("span");
      text.className = "event-journal-text";
      const detailSummary = summarizeEventDetails(entry.details, entry.label);
      const eventLabel = formatEventLabel(entry.label);
      text.textContent = detailSummary ? `${eventLabel} | ${detailSummary}` : eventLabel;

      item.appendChild(time);
      item.appendChild(text);
      eventJournal.appendChild(item);

      const binIndex = computeTimelineBinIndex(entry.timestamp, eventTimelineContext);
      if (binIndex !== null) {
        const stamp = Date.parse(entry.timestamp || "");
        const currentFirst = eventJournalFirstTimeByBin.get(binIndex);
        if (!Number.isFinite(stamp)) {
          if (!eventJournalFirstRowByBin.has(binIndex)) {
            eventJournalFirstRowByBin.set(binIndex, item);
          }
        } else if (currentFirst === undefined || stamp < currentFirst) {
          eventJournalFirstTimeByBin.set(binIndex, stamp);
          eventJournalFirstRowByBin.set(binIndex, item);
        }
      }
    });
  }

  function bindTimelineClicks() {
    if (!eventJournal || !eventTimelineContext || !Array.isArray(eventTimelineContext.barElements)) {
      return;
    }
    eventTimelineContext.barElements.forEach((bar, binIndex) => {
      bar.addEventListener("click", () => {
        const row = eventJournalFirstRowByBin.get(binIndex);
        if (!row) {
          return;
        }
        const timestamp = typeof row.dataset.timestamp === "string" ? row.dataset.timestamp : "";
        highlightJournalLink(row, timestamp);
        const journalRect = eventJournal.getBoundingClientRect();
        const rowRect = row.getBoundingClientRect();
        const targetTop = eventJournal.scrollTop + (rowRect.top - journalRect.top) - 6;
        eventJournal.scrollTo({
          top: Math.max(0, targetTop),
          behavior: "smooth"
        });
      });
    });
  }

  function render(optionsValue) {
    const settings = optionsValue && typeof optionsValue === "object" ? optionsValue : {};
    eventTimelineContext = settings.timelineContext || null;
    eventJournalFirstRowByBin = new Map();
    eventJournalFirstTimeByBin = new Map();
    clearHighlight();
    renderJournalEntries(Array.isArray(settings.entries) ? settings.entries : []);
    bindTimelineClicks();
  }

  return {
    render,
    reset,
    clearHighlight,
  };
}
