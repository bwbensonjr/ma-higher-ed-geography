/**
 * The table's content, as a pure function of the selection.
 *
 * One row is one campus, never one institution: a row's address,
 * municipality, county, and statistical area are then all single-valued and
 * each row corresponds to exactly one map marker. An institution with
 * campuses in several places occupies several rows.
 *
 * A row's geography names come from the published area index, not from the
 * campus's mailing city, which names a different place for 18 of the 206
 * campuses -- Boston College's main campus is addressed Chestnut Hill and
 * sits in Newton.
 */

import { compareText } from "./indexes.js";
import { areaCounts } from "./counts.js";
import { AREA_NOUNS, isDegreeGrantingOnly, tableMode } from "./state.js";

export const COLUMNS = [
  { key: "institution", label: "Institution", sortable: true },
  { key: "campus", label: "Campus", sortable: true },
  { key: "address", label: "Address", sortable: false },
  { key: "municipality", label: "Municipality", sortable: true, layer: "municipality" },
  { key: "county", label: "County", sortable: true, layer: "county" },
  { key: "cbsa", label: "Statistical area", sortable: true, layer: "cbsa" },
  { key: "institution_type", label: "Type", sortable: true },
  { key: "category", label: "Category", sortable: true },
  { key: "degrees_offered", label: "Degrees", sortable: false },
];

export const DEFAULT_SORT = Object.freeze({ key: "institution", direction: "asc" });

/** The source publishes this as a two-valued code. */
export const TYPE_LABELS = { PUB: "Public", PRI: "Private" };

export function typeLabel(code) {
  if (!code) return "";
  return TYPE_LABELS[code] ?? code;
}

/** One table row: text cells plus the areas its geography cells link to. */
export function buildRow(campus, indexes) {
  const areas = {};
  for (const layer of ["county", "municipality", "cbsa"]) {
    const areaId = campus.areaIds[layer];
    areas[layer] = areaId
      ? { layer, areaId, name: indexes.areaName(layer, areaId) }
      : null;
  }
  return {
    campusId: campus.id,
    institutionId: campus.institution_id,
    campus,
    areas,
    cells: {
      institution: campus.institution,
      campus: campus.campus || "",
      address: campus.address ? campus.address.trim() : "",
      municipality: areas.municipality?.name ?? "",
      county: areas.county?.name ?? "",
      cbsa: areas.cbsa?.name ?? "",
      institution_type: typeLabel(campus.institution_type),
      category: campus.category || "",
      degrees_offered: campus.degrees_offered || "",
    },
  };
}

export function matchesFilter(row, filter) {
  if (!filter) return true;
  const needle = filter.trim().toLowerCase();
  if (!needle) return true;
  return (
    row.cells.institution.toLowerCase().includes(needle) ||
    row.cells.campus.toLowerCase().includes(needle)
  );
}

export function sortRows(rows, sort = DEFAULT_SORT) {
  const key = sort?.key ?? DEFAULT_SORT.key;
  const sign = sort?.direction === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const primary = compareText(a.cells[key], b.cells[key]) * sign;
    if (primary !== 0) return primary;
    return (
      compareText(a.cells.institution, b.cells.institution) ||
      compareText(a.cells.campus, b.cells.campus) ||
      compareText(a.campusId, b.campusId)
    );
  });
}

/**
 * The whole table, in one of three modes:
 *
 *   all      nothing selected: every campus, alphabetical
 *   grouped  a layer selected: grouped by that layer's areas
 *   area     one geography selected: only its campuses
 */
export function tableModel({ indexes, state, sort = DEFAULT_SORT, filter = "" }) {
  const mode = tableMode(state);
  // The population is applied once, in the index; nothing here re-filters.
  const allRows = indexes.campusesFor(state).map((campus) => buildRow(campus, indexes));
  const byId = new Map(allRows.map((row) => [row.campusId, row]));
  const filtered = allRows.filter((row) => matchesFilter(row, filter));
  const filtering = !!filter && filter.trim().length > 0;

  if (mode === "all") {
    const rows = sortRows(filtered, sort);
    return {
      mode,
      rows,
      groups: [],
      rowCount: rows.length,
      totalCount: allRows.length,
      filtering,
      degreeGrantingOnly: isDegreeGrantingOnly(state),
      caption: isDegreeGrantingOnly(state)
        ? "Degree-granting campuses, alphabetical by institution"
        : "All campuses, alphabetical by institution",
      restriction: null,
      empty: rows.length === 0,
      emptyNote: filtering
        ? "No institution matches that text."
        : "No campuses to show.",
      omittedGroups: 0,
    };
  }

  if (mode === "area") {
    const { layer, areaId } = state;
    const name = indexes.areaName(layer, areaId) ?? areaId;
    const counts = areaCounts(indexes.assignments, layer, areaId, state);
    const held = indexes.allCampusesIn(layer, areaId).length;
    const rows = sortRows(
      indexes
        .campusesIn(layer, areaId, state)
        .map((campus) => byId.get(campus.id))
        .filter((row) => row && matchesFilter(row, filter)),
      sort
    );
    return {
      mode,
      rows,
      groups: [],
      rowCount: rows.length,
      totalCount: counts?.campuses ?? rows.length,
      filtering,
      degreeGrantingOnly: isDegreeGrantingOnly(state),
      caption: `Campuses in ${name}`,
      restriction: { layer, areaId, name, counts, noun: AREA_NOUNS[layer] },
      empty: rows.length === 0,
      // An area emptied by the population is not an area holding nothing:
      // 17 municipalities hold campuses of which none are degree-granting,
      // and reporting those as simply empty would misstate the data.
      emptiedByPopulation:
        counts?.campuses === 0 && held > 0 && isDegreeGrantingOnly(state),
      heldRegardless: held,
      emptyNote:
        counts && counts.campuses === 0
          ? held > 0 && isDegreeGrantingOnly(state)
            ? `${name} holds no degree-granting campuses. It holds ` +
              `${held === 1 ? "one campus" : `${held} campuses`} in total, ` +
              `which the control above will show.`
            : `${name} contains no campuses.`
          : "No institution in this area matches that text.",
      omittedGroups: 0,
    };
  }

  // Grouped by the selected layer. Areas holding no campuses are counted
  // and reported rather than listed as empty groups: 268 of the 351
  // municipalities hold none, and listing them would bury the data.
  const { layer } = state;
  const groups = [];
  let omittedGroups = 0;
  let shownRows = 0;
  for (const area of indexes.areasByName(layer)) {
    const counts = areaCounts(indexes.assignments, layer, area.areaId, state);
    const rows = sortRows(
      indexes
        .campusesIn(layer, area.areaId, state)
        .map((campus) => byId.get(campus.id))
        .filter((row) => row && matchesFilter(row, filter)),
      sort
    );
    if ((counts?.campuses ?? 0) === 0) {
      omittedGroups += 1;
      continue;
    }
    if (rows.length === 0 && filtering) continue;
    shownRows += rows.length;
    groups.push({
      layer,
      areaId: area.areaId,
      name: area.name,
      counts,
      rows,
      shownCount: rows.length,
    });
  }

  return {
    mode,
    rows: [],
    groups,
    rowCount: shownRows,
    totalCount: allRows.length,
    filtering,
    degreeGrantingOnly: isDegreeGrantingOnly(state),
    caption: isDegreeGrantingOnly(state)
      ? `Degree-granting campuses grouped by ${AREA_NOUNS[layer]}`
      : `Campuses grouped by ${AREA_NOUNS[layer]}`,
    restriction: null,
    empty: groups.length === 0,
    emptyNote: filtering
      ? "No institution matches that text."
      : "No campuses to show.",
    omittedGroups,
  };
}
