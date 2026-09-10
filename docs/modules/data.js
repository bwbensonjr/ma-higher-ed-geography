/**
 * Fetching the published data.
 *
 * The small files are fetched at load; an area layer's geometry is fetched
 * only when that layer is first drawn, and once fetched it is reused for the
 * rest of the visit. The area geometry is six times the size of everything
 * else put together, and most visits do not draw all three layers.
 */

export const DATA_DIR = "data/";

export const EAGER_FILES = {
  campusCollection: "campus.geojson",
  assignments: "assignments.json",
  areaIndex: "area.json",
  provenance: "provenance.json",
};

export const LAYER_FILES = {
  county: "county.geojson",
  municipality: "municipality.geojson",
  cbsa: "cbsa.geojson",
};

export class DataError extends Error {
  constructor(file, cause) {
    super(`could not load ${file}`);
    this.name = "DataError";
    this.file = file;
    this.cause = cause;
  }
}

export async function fetchJson(path, { base = DATA_DIR, fetchImpl = fetch } = {}) {
  let response;
  try {
    response = await fetchImpl(`${base}${path}`, { cache: "no-cache" });
  } catch (error) {
    throw new DataError(path, error);
  }
  if (!response.ok) {
    throw new DataError(path, new Error(`HTTP ${response.status}`));
  }
  try {
    return await response.json();
  } catch (error) {
    throw new DataError(path, error);
  }
}

/** The four files the first view needs, fetched in parallel. */
export async function loadEager(options = {}) {
  const keys = Object.keys(EAGER_FILES);
  const payloads = await Promise.all(
    keys.map((key) => fetchJson(EAGER_FILES[key], options))
  );
  return Object.fromEntries(keys.map((key, index) => [key, payloads[index]]));
}

/**
 * A loader that fetches each layer's geometry at most once.
 *
 * The in-flight promise is memoized, so two rapid switches to the same
 * layer cannot start two requests. A rejected load is forgotten, so the
 * page can offer the layer again rather than caching the failure forever.
 */
export function createLayerLoader(options = {}) {
  const cache = new Map();
  const loaded = new Map();

  return {
    isLoaded(layer) {
      return loaded.has(layer);
    },
    get(layer) {
      return loaded.get(layer) ?? null;
    },
    load(layer) {
      const file = LAYER_FILES[layer];
      if (!file) return Promise.reject(new DataError(String(layer)));
      if (loaded.has(layer)) return Promise.resolve(loaded.get(layer));
      if (cache.has(layer)) return cache.get(layer);
      const pending = fetchJson(file, options)
        .then((collection) => {
          loaded.set(layer, collection);
          cache.delete(layer);
          return collection;
        })
        .catch((error) => {
          cache.delete(layer);
          throw error;
        });
      cache.set(layer, pending);
      return pending;
    },
  };
}
