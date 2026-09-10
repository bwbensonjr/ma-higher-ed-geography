/**
 * How an area is shaded by the number of campuses it holds.
 *
 * Breaks are fixed and per-layer. The distributions differ by an order of
 * magnitude -- a statistical area holds up to 134 campuses while 268 of the
 * 351 municipalities hold none -- so one set of breaks across all three
 * layers would put nearly every county in the top class. Fixed breaks are
 * preferred over quantiles because quantile classes shift meaning as the
 * data changes and cannot be compared between layers.
 *
 * Zero is its own style, not the lightest shade, so "no campuses" is never
 * read as "few campuses".
 */

/** Lower bound of each class, ascending. The last class is open-ended. */
export const BREAKS = {
  county: [1, 5, 10, 20, 40],
  municipality: [1, 2, 4, 10, 20],
  cbsa: [1, 5, 15, 25, 50],
};

/** Sequential blues, light to dark. Chosen to read over grey tiles. */
export const COLORS = ["#dbe6f2", "#a9c6e3", "#6c9fcd", "#2f6fa8", "#14456e"];

export const EMPTY_COLOR = "#f2f2ef";

// Enough to separate the classes over a grey basemap, sheer enough that the
// streets beneath stay visible.
export const FILL_OPACITY = 0.62;
export const EMPTY_FILL_OPACITY = 0.28;

/** -1 for an area with no campuses, otherwise the index into COLORS. */
export function classIndex(layer, count) {
  const breaks = BREAKS[layer];
  if (!breaks || !count || count <= 0) return -1;
  let index = -1;
  for (let i = 0; i < breaks.length; i += 1) {
    if (count >= breaks[i]) index = i;
  }
  return index;
}

export function colorFor(layer, count) {
  const index = classIndex(layer, count);
  return index < 0 ? EMPTY_COLOR : COLORS[index];
}

/** The label for one class: "5-9", "40+", or "No campuses". */
export function classLabel(layer, index) {
  const breaks = BREAKS[layer];
  if (index < 0) return "No campuses";
  const low = breaks[index];
  const next = breaks[index + 1];
  if (next === undefined) return `${low}+`;
  if (next - low === 1) return `${low}`;
  return `${low}–${next - 1}`;
}

/** Legend rows, densest first, with the empty class last. */
export function legendEntries(layer) {
  const breaks = BREAKS[layer];
  if (!breaks) return [];
  const entries = breaks
    .map((_, index) => ({
      label: classLabel(layer, index),
      color: COLORS[index],
      opacity: FILL_OPACITY,
    }))
    .reverse();
  entries.push({
    label: classLabel(layer, -1),
    color: EMPTY_COLOR,
    opacity: EMPTY_FILL_OPACITY,
  });
  return entries;
}

/** The Leaflet path style for one area. */
export function areaStyle(layer, count, { selected = false, dimmed = false } = {}) {
  const empty = classIndex(layer, count) < 0;
  return {
    color: selected ? "#b8331f" : "#5a6472",
    weight: selected ? 3 : 0.7,
    opacity: dimmed ? 0.35 : 1,
    fillColor: colorFor(layer, count),
    fillOpacity: dimmed
      ? 0.12
      : empty
        ? EMPTY_FILL_OPACITY
        : FILL_OPACITY,
  };
}
