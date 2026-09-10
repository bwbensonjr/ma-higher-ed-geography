/**
 * The page's selection state, and the URL hash it is encoded in.
 *
 * The hash is the single source of truth: every control writes it, and one
 * hashchange handler reads it and renders. That is what makes a view
 * shareable, makes the browser's back button step through selections, and
 * makes it impossible for the map and the table to disagree about what is
 * selected.
 *
 * No DOM, no Leaflet, no fetch: this module is pure so it can be tested
 * directly.
 */

export const NO_LAYER = "none";
export const AREA_LAYERS = ["county", "municipality", "cbsa"];

export const LAYER_LABELS = {
  none: "No layer",
  county: "Counties",
  municipality: "Municipalities",
  cbsa: "Statistical areas",
};

/** How to refer to one area of a layer in a sentence. */
export const AREA_NOUNS = {
  county: "county",
  municipality: "municipality",
  cbsa: "statistical area",
};

/**
 * Which population the page is reporting on. This is part of the shared
 * view rather than a local preference: sort order and the text filter
 * change what a visitor is looking at within a fixed set of facts, while
 * the population changes which facts are being reported. A link saying
 * "Middlesex has 22 institutions" has to carry it or it misleads.
 */
export const DEGREE_GRANTING = "degree_granting";
export const ALL_CAMPUSES = "all";
export const POPULATIONS = [DEGREE_GRANTING, ALL_CAMPUSES];
export const DEFAULT_POPULATION = DEGREE_GRANTING;

export const POPULATION_LABELS = {
  [DEGREE_GRANTING]: "degree-granting institutions",
  [ALL_CAMPUSES]: "all schools, including vocational and adult education",
};

export const DEFAULT_STATE = Object.freeze({
  layer: NO_LAYER,
  areaId: null,
  population: DEFAULT_POPULATION,
});

export function defaultState() {
  return { ...DEFAULT_STATE };
}

/** Read a raw, unvalidated state out of a location hash. */
export function parseHash(hash = "") {
  const text = String(hash).replace(/^#/, "");
  const params = new URLSearchParams(text);
  const layer = params.get("layer");
  const area = params.get("area");
  const population = params.get("population");
  return {
    layer: layer === null ? null : layer,
    areaId: area === null || area === "" ? null : area,
    population: population === null || population === "" ? null : population,
  };
}

/** The hash for a state. The default view has no hash at all. */
export function encodeState(state) {
  const params = new URLSearchParams();
  const layer = state?.layer;
  if (layer && layer !== NO_LAYER) {
    params.set("layer", layer);
    if (state.areaId) params.set("area", String(state.areaId));
  }
  // The default population is what an address that says nothing produces,
  // so links made before this distinction existed still open coherently.
  if (state?.population && state.population !== DEFAULT_POPULATION) {
    params.set("population", state.population);
  }
  const query = params.toString();
  return query ? `#${query}` : "";
}

/**
 * Turn a raw state into one the page can render.
 *
 * `areaIndex` is `{layer: {areaId: ...}}` -- the published area index or the
 * assignment, either of which knows every area of every layer without any
 * geometry being loaded. Anything unrecognized falls back to the default
 * view rather than erroring: an unknown layer, an area that does not exist,
 * and an area belonging to a different layer than the one named.
 */
export function normalizeState(raw, areaIndex) {
  const layer = raw?.layer ?? null;
  const areaId = raw?.areaId == null ? null : String(raw.areaId);
  // An unrecognized population degrades to the default rather than erroring.
  const population = POPULATIONS.includes(raw?.population)
    ? raw.population
    : DEFAULT_POPULATION;

  if (layer === null || layer === NO_LAYER) return { ...defaultState(), population };
  if (!AREA_LAYERS.includes(layer)) return { ...defaultState(), population };
  if (areaId === null) return { layer, areaId: null, population };

  const areas = areaIndex?.[layer];
  const known = !!areas && Object.prototype.hasOwnProperty.call(areas, areaId);
  return known
    ? { layer, areaId, population }
    : { ...defaultState(), population };
}

export function statesEqual(a, b) {
  return (
    (a?.layer ?? null) === (b?.layer ?? null) &&
    (a?.areaId ?? null) === (b?.areaId ?? null) &&
    (a?.population ?? null) === (b?.population ?? null)
  );
}

/** True when the state's population excludes the sub-associate campuses. */
export function isDegreeGrantingOnly(state) {
  return (state?.population ?? DEFAULT_POPULATION) === DEGREE_GRANTING;
}

/** Which of the three table modes a state calls for. */
export function tableMode(state) {
  if (state?.areaId) return "area";
  if (state?.layer && state.layer !== NO_LAYER) return "grouped";
  return "all";
}
