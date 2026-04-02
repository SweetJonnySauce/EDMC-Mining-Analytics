export function buildSmoothLinePath(points) {
  if (!Array.isArray(points) || points.length === 0) {
    return "";
  }
  let command = `M${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
  for (let index = 1; index < points.length; index += 1) {
    const point = points[index];
    command += ` L${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
  }
  return command;
}

export function inferStep(yMaxInt) {
  const targetTickCount = 7;
  const minStep = Math.max(1, yMaxInt / (targetTickCount - 1));
  let magnitude = Math.pow(10, Math.floor(Math.log10(minStep)));
  if (!Number.isFinite(magnitude) || magnitude <= 0) {
    magnitude = 1;
  }
  let step = 0;
  for (let attempts = 0; attempts < 8 && step <= 0; attempts += 1) {
    [1, 2, 5].forEach((multiplier) => {
      const candidate = multiplier * magnitude;
      if (candidate >= minStep && (step <= 0 || candidate < step)) {
        step = candidate;
      }
    });
    magnitude *= 10;
  }
  return step > 0 ? step : 1;
}
