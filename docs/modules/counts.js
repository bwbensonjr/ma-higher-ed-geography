/**
 * Campus counts and institution counts.
 *
 * The two differ, and institution counts are NOT additive: an institution
 * with campuses in two areas is counted in both, so summing a layer's
 * institution counts exceeds the number of distinct institutions in the
 * state. There is deliberately no helper here that sums them. The only
 * statewide institution figure comes from the published provenance record.
 */

import { isDegreeGrantingOnly } from "./state.js";

// The assignment publishes both populations' counts, so a filtered figure
// is read rather than computed by subtracting one from the other -- which
// would be wrong for institutions, since one with campuses in two areas is
// counted in both.
// Keyed by whether the population is filtered rather than by the
// population's name, so this module names published *fields* and never
// reads a campus's own flag -- filtering happens in one place, the index.
const AREA_FIELDS = {
  whole: { campuses: "campus_count", institutions: "institution_count" },
  filtered: {
    campuses: "degree_granting_campus_count",
    institutions: "degree_granting_institution_count",
  },
};

const STATEWIDE_INSTITUTION_FIELD = {
  whole: "institution_count",
  filtered: "degree_granting_institution_count",
};

function fieldsFor(state) {
  return isDegreeGrantingOnly(state) ? AREA_FIELDS.filtered : AREA_FIELDS.whole;
}

/** Per-area counts, read from the published assignment. Never derived. */
export function areaCounts(assignments, layer, areaId, state) {
  const entry = assignments?.[layer]?.[String(areaId)];
  if (!entry) return null;
  const fields = fieldsFor(state);
  return {
    campuses: entry[fields.campuses],
    institutions: entry[fields.institutions],
  };
}

/** The statewide figures for a population, both as published. */
export function statewideCounts(provenance, campusCount, state) {
  const field = isDegreeGrantingOnly(state)
    ? STATEWIDE_INSTITUTION_FIELD.filtered
    : STATEWIDE_INSTITUTION_FIELD.whole;
  return {
    campuses: campusCount,
    institutions: provenance?.[field] ?? null,
  };
}

/** Campus counts are additive, so this is a legitimate sum. */
export function totalCampuses(groups) {
  return groups.reduce((sum, group) => sum + group.rows.length, 0);
}

export function plural(count, singular, pluralForm = `${singular}s`) {
  return `${count.toLocaleString("en-US")} ${count === 1 ? singular : pluralForm}`;
}

/** "38 campuses, 35 institutions" -- both labeled, never interchangeable. */
export function describeCounts(counts) {
  if (!counts) return "";
  return `${plural(counts.campuses, "campus", "campuses")}, ${plural(
    counts.institutions,
    "institution"
  )}`;
}
