import { formatNumber } from "../shared/number.js";

export function buildSessionTooltipText(options) {
  const {
    commodityLabel,
    ringName,
    session,
  } = options || {};
  return [
    `${commodityLabel} | ${ringName}`,
    session.sessionLabel,
    `Asteroids: ${formatNumber(session.asteroidCount, 0)}`,
    `P25-P75: ${formatNumber(session.p25, 2)}% to ${formatNumber(session.p75, 2)}%`,
    `Max Yield: ${formatNumber(session.maxValue, 2)}%`,
  ].join("\n");
}
