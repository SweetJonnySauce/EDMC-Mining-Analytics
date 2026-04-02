export function buildAdaptiveLabelStepCandidates(count) {
  const total = Math.max(1, Math.floor(Number(count) || 1));
  if (total <= 1) {
    return [1];
  }
  const baseCandidates = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30, 40, 50, 60, 80, 100];
  const candidates = new Set();
  baseCandidates.forEach((value) => {
    const step = Math.max(1, Math.floor(Number(value) || 1));
    if (step <= total) {
      candidates.add(step);
    }
  });
  let powerOfTwo = 1;
  while (powerOfTwo <= total) {
    candidates.add(powerOfTwo);
    powerOfTwo *= 2;
  }
  candidates.add(total);
  return Array.from(candidates.values()).sort((left, right) => left - right);
}

export function shouldShowAdaptiveBinLabel(index, totalCount, step) {
  const total = Math.max(1, Math.floor(Number(totalCount) || 1));
  const safeIndex = Math.max(0, Math.floor(Number(index) || 0));
  const safeStep = Math.max(1, Math.floor(Number(step) || 1));
  return (safeIndex % safeStep) === 0 || safeIndex === (total - 1);
}

export function adaptiveLabelsFitWithoutOverlap(labelNodes, minGapPx) {
  if (!Array.isArray(labelNodes) || !labelNodes.length) {
    return true;
  }
  const minGap = Math.max(0, Number(minGapPx) || 0);
  let previousRight = Number.NEGATIVE_INFINITY;
  const range = document.createRange();
  for (const node of labelNodes) {
    if (!(node instanceof HTMLElement)) {
      continue;
    }
    const text = String(node.textContent || "").trim();
    if (!text) {
      continue;
    }
    range.selectNodeContents(node);
    let rect = range.getBoundingClientRect();
    if (!Number.isFinite(rect.left) || !Number.isFinite(rect.right) || rect.width <= 0) {
      rect = node.getBoundingClientRect();
    }
    if (!Number.isFinite(rect.left) || !Number.isFinite(rect.right) || rect.width <= 0) {
      continue;
    }
    if (rect.left < (previousRight + minGap)) {
      range.detach?.();
      return false;
    }
    previousRight = rect.right;
  }
  range.detach?.();
  return true;
}

export function applyAdaptiveBinLabels(labelsContainer, labelTexts, minGapPx) {
  if (!(labelsContainer instanceof HTMLElement)) {
    return 1;
  }
  const texts = Array.isArray(labelTexts) ? labelTexts.map((text) => String(text || "")) : [];
  const total = texts.length;
  const labelNodes = Array.from(labelsContainer.children).filter((node) => node instanceof HTMLElement);
  if (!total || !labelNodes.length) {
    return 1;
  }
  const setStep = (step) => {
    labelNodes.forEach((node, index) => {
      node.textContent = shouldShowAdaptiveBinLabel(index, total, step) ? texts[index] : "";
    });
  };
  const candidates = buildAdaptiveLabelStepCandidates(total);
  for (const step of candidates) {
    setStep(step);
    if (adaptiveLabelsFitWithoutOverlap(labelNodes, minGapPx)) {
      return step;
    }
  }
  const fallback = candidates[candidates.length - 1] || 1;
  setStep(fallback);
  return fallback;
}
