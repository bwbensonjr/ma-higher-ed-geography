/**
 * The lookups the page answers every question from.
 *
 * All of it is built once, at load, out of the published files. Area
 * membership is read from the assignment rather than recomputed from
 * coordinates, and area names come from the published area index, so
 * naming a campus's geographies costs no geometry.
 */

import { AREA_LAYERS, isDegreeGrantingOnly } from "./state.js";

const collator = new Intl.Collator("en", { sensitivity: "base", numeric: true });

export function compareText(a, b) {
  return collator.compare(a ?? "", b ?? "");
}

/** The population filter itself: read from the published flag, never derived. */
function applyPopulation(campuses, state) {
  if (!isDegreeGrantingOnly(state)) return campuses;
  return campuses.filter((campus) => campus.degree_granting);
}

/** One campus: its published properties, its coordinates, its area ids. */
function toCampus(feature) {
  const p = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;
  return {
    ...p,
    id: p.campus_id,
    lon,
    lat,
    areaIds: {
      county: p.county_id == null ? null : String(p.county_id),
      municipality: p.municipality_id == null ? null : String(p.municipality_id),
      cbsa: p.cbsa_id == null || p.cbsa_id === "" ? null : String(p.cbsa_id),
    },
  };
}

export function buildIndexes({ campusCollection, assignments, areaIndex, provenance }) {
  const campuses = campusCollection.features.map(toCampus);

  const campusById = new Map(campuses.map((campus) => [campus.id, campus]));

  // Membership comes from the published assignment, not from geometry.
  const campusesByArea = {};
  for (const layer of AREA_LAYERS) {
    const byArea = new Map();
    for (const [areaId, entry] of Object.entries(assignments[layer] ?? {})) {
      byArea.set(
        areaId,
        entry.campus_ids.map((id) => campusById.get(id)).filter(Boolean)
      );
    }
    campusesByArea[layer] = byArea;
  }

  const sortedCampuses = [...campuses].sort(
    (a, b) =>
      compareText(a.institution, b.institution) ||
      compareText(a.campus, b.campus) ||
      compareText(a.id, b.id)
  );

  const institutionIds = new Set(campuses.map((campus) => campus.institution_id));

  return {
    campuses,
    campusById,
    campusesByArea,
    sortedCampuses,
    areaIndex,
    assignments,
    provenance,
    institutionIds,
    totals: {
      campuses: campuses.length,
      institutions: provenance?.institution_count ?? institutionIds.size,
    },
    areaName(layer, areaId) {
      if (areaId == null) return null;
      return areaIndex?.[layer]?.[String(areaId)]?.name ?? null;
    },
    /** Every area of a layer, ordered by display name. */
    areasByName(layer) {
      return Object.entries(areaIndex?.[layer] ?? {})
        .map(([areaId, entry]) => ({ areaId, ...entry }))
        .sort((a, b) => compareText(a.name, b.name));
    },
    /**
     * Every campus of a state's population, statewide.
     *
     * This and campusesIn below are the ONLY places the population is
     * applied. The map, the table model, and the count helpers all draw
     * from them, which is what keeps markers, rows, and stated counts from
     * disagreeing about what they are describing.
     */
    campusesFor(state) {
      return applyPopulation(sortedCampuses, state);
    },
    campusesIn(layer, areaId, state) {
      const members = campusesByArea[layer]?.get(String(areaId)) ?? [];
      return applyPopulation(members, state);
    },
    /** The unfiltered membership, for reporting what a filter left out. */
    allCampusesIn(layer, areaId) {
      return campusesByArea[layer]?.get(String(areaId)) ?? [];
    },
  };
}
