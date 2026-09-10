/**
 * Campus counts and institution counts.
 *
 * The two differ, and institution counts are NOT additive: an institution
 * with campuses in two areas is counted in both, so summing a layer's
 * institution counts exceeds the number of distinct institutions in the
 * state. There is deliberately no helper here that sums them. The only
 * statewide institution figure comes from the published provenance record.
 */

/** Per-area counts, read from the published assignment. Never derived. */
export function areaCounts(assignments, layer, areaId) {
  const entry = assignments?.[layer]?.[String(areaId)];
  if (!entry) return null;
  return {
    campuses: entry.campus_count,
    institutions: entry.institution_count,
  };
}

/** The statewide figures: campuses counted, institutions as published. */
export function statewideCounts(provenance, campusCount) {
  return {
    campuses: campusCount,
    institutions: provenance?.institution_count ?? null,
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
