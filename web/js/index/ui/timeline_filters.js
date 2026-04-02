function createCountMap(entries, getLabel) {
  const counts = new Map();
  const list = Array.isArray(entries) ? entries : [];
  const resolveLabel = typeof getLabel === "function"
    ? getLabel
    : (entry) => (entry && typeof entry.label === "string" ? entry.label : "");
  list.forEach((entry) => {
    const label = String(resolveLabel(entry) || "").trim();
    if (!label) {
      return;
    }
    counts.set(label, (counts.get(label) || 0) + 1);
  });
  return counts;
}

function sortFilterLabels(counts) {
  return Array.from(counts.keys()).sort((left, right) => {
    const delta = (counts.get(right) || 0) - (counts.get(left) || 0);
    if (delta !== 0) {
      return delta;
    }
    return left.localeCompare(right);
  });
}

export function wireTimelineCheckboxFilters(options) {
  const {
    container,
    entries,
    getLabel,
    selection,
    emptyMessage,
    allCheckboxId,
    itemCheckboxIdPrefix,
    formatLabel,
    itemClassName,
    onSelectionChange,
  } = options || {};
  if (!container) {
    return;
  }

  const selectedMap = selection && typeof selection === "object" ? selection : {};
  const className = typeof itemClassName === "string" && itemClassName.trim()
    ? itemClassName.trim()
    : "event-filter-item";
  const labelFormatter = typeof formatLabel === "function" ? formatLabel : (value) => value;

  container.innerHTML = "";
  const counts = createCountMap(entries, getLabel);
  const sortedLabels = sortFilterLabels(counts);
  if (!sortedLabels.length) {
    const note = document.createElement("span");
    note.className = "chart-empty";
    note.textContent = typeof emptyMessage === "string" && emptyMessage.trim()
      ? emptyMessage
      : "No filters available.";
    container.appendChild(note);
    if (typeof onSelectionChange === "function") {
      onSelectionChange();
    }
    return;
  }

  const itemCheckboxes = [];
  const allWrapper = document.createElement("label");
  allWrapper.className = className;
  const allCheckbox = document.createElement("input");
  allCheckbox.type = "checkbox";
  allCheckbox.checked = true;
  if (typeof allCheckboxId === "string" && allCheckboxId.trim()) {
    allCheckbox.id = allCheckboxId;
  }
  const allText = document.createElement("span");
  allText.textContent = "All";
  allWrapper.appendChild(allCheckbox);
  allWrapper.appendChild(allText);
  container.appendChild(allWrapper);

  const syncAllCheckboxState = () => {
    const selectedCount = sortedLabels.reduce(
      (sum, label) => sum + (selectedMap[label] ? 1 : 0),
      0
    );
    allCheckbox.checked = selectedCount === sortedLabels.length;
    allCheckbox.indeterminate = selectedCount > 0 && selectedCount < sortedLabels.length;
  };

  allCheckbox.addEventListener("change", () => {
    const checked = allCheckbox.checked;
    allCheckbox.indeterminate = false;
    sortedLabels.forEach((label) => {
      selectedMap[label] = checked;
    });
    itemCheckboxes.forEach((checkbox) => {
      checkbox.checked = checked;
    });
    if (typeof onSelectionChange === "function") {
      onSelectionChange();
    }
  });

  sortedLabels.forEach((label, index) => {
    selectedMap[label] = true;
    const wrapper = document.createElement("label");
    wrapper.className = className;
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    const prefix = typeof itemCheckboxIdPrefix === "string" ? itemCheckboxIdPrefix.trim() : "";
    if (prefix) {
      checkbox.id = `${prefix}-${index}`;
    }
    checkbox.addEventListener("change", () => {
      selectedMap[label] = checkbox.checked;
      syncAllCheckboxState();
      if (typeof onSelectionChange === "function") {
        onSelectionChange();
      }
    });
    itemCheckboxes.push(checkbox);

    const text = document.createElement("span");
    const displayLabel = String(labelFormatter(label) || "").trim() || label;
    text.textContent = `${displayLabel} (${counts.get(label) || 0})`;

    wrapper.appendChild(checkbox);
    wrapper.appendChild(text);
    container.appendChild(wrapper);
  });

  syncAllCheckboxState();
  if (typeof onSelectionChange === "function") {
    onSelectionChange();
  }
}
