/**
 * The page.
 *
 * Everything visible is a function of one state value, {layer, areaId},
 * which lives in the URL hash. Controls write the hash; a single
 * hashchange handler reads it and renders. Nothing renders from a click
 * handler directly, which is what keeps the map and the table from ever
 * disagreeing about what is selected.
 */

import { buildIndexes } from "./modules/indexes.js";
import { createLayerLoader, loadEager } from "./modules/data.js";
import { createMap } from "./modules/map.js";
import { describeTable, renderHead, renderTable } from "./modules/table.js";
import { DEFAULT_SORT, tableModel } from "./modules/rows.js";
import { areaCounts, describeCounts, plural, statewideCounts } from "./modules/counts.js";
import {
  ALL_CAMPUSES,
  AREA_NOUNS,
  DEGREE_GRANTING,
  LAYER_LABELS,
  NO_LAYER,
  defaultState,
  encodeState,
  isDegreeGrantingOnly,
  normalizeState,
  parseHash,
  statesEqual,
} from "./modules/state.js";

const dom = {
  summary: document.getElementById("summary"),
  notice: document.getElementById("notice"),
  error: document.getElementById("error"),
  layerSelect: document.getElementById("layer-select"),
  filterInput: document.getElementById("filter-input"),
  populationToggle: document.getElementById("population-toggle"),
  selectionStatus: document.getElementById("selection-status"),
  clearSelection: document.getElementById("clear-selection"),
  tableStatus: document.getElementById("table-status"),
  tableCaption: document.getElementById("table-caption"),
  table: document.getElementById("campus-table"),
  headRow: document.getElementById("table-head-row"),
  provenanceSummary: document.getElementById("provenance-summary"),
  provenanceSources: document.getElementById("provenance-sources"),
};

const view = {
  indexes: null,
  loader: createLayerLoader(),
  map: null,
  state: defaultState(),
  sort: { ...DEFAULT_SORT },
  filter: "",
  unavailableLayers: new Set(),
  renderToken: 0,
  ready: false,
};

// Exposed for the verification suite, which drives the real page.
window.maGeo = view;

/* --- notices ------------------------------------------------------------ */

function setNotice(text) {
  dom.notice.textContent = text ?? "";
  dom.notice.hidden = !text;
}

function setError(text) {
  dom.error.textContent = text ?? "";
  dom.error.hidden = !text;
}

/* --- state plumbing ----------------------------------------------------- */

function currentState() {
  const areaIndex = view.indexes?.areaIndex ?? null;
  return normalizeState(parseHash(window.location.hash), areaIndex);
}

/** Every control goes through here. Nothing renders directly. */
function goTo(next) {
  const hash = encodeState(next);
  const target = `${window.location.pathname}${window.location.search}${hash}`;
  if (encodeState(view.state) === hash && statesEqual(view.state, currentState())) {
    return;
  }
  window.history.pushState(null, "", target || window.location.pathname);
  render();
}

function selectArea(layer, areaId) {
  goTo({ ...view.state, layer, areaId: String(areaId) });
}

function selectPopulation(population) {
  // The population is part of the shared view, so it goes through the hash
  // like every other selection rather than being applied in place.
  goTo({ ...view.state, population });
}

function selectLayer(layer) {
  // Switching layers clears the geography: mapping a selection into the new
  // layer has no single right answer (Suffolk maps to four municipalities),
  // and silently picking one would misrepresent the visitor's selection.
  goTo({ ...view.state, layer, areaId: null });
}

function clearSelection() {
  goTo({ ...view.state, areaId: null });
}

/* --- rendering ---------------------------------------------------------- */

function renderSummary() {
  const campusList = view.indexes.campusesFor(view.state);
  const totals = statewideCounts(
    view.indexes.provenance,
    campusList.length,
    view.state
  );
  dom.summary.innerHTML = "";
  const campuses = document.createElement("strong");
  campuses.textContent = plural(totals.campuses, "campus", "campuses");
  const institutions = document.createElement("strong");
  institutions.textContent = plural(totals.institutions, "institution");
  const tail = isDegreeGrantingOnly(view.state)
    ? " across Massachusetts, counting degree-granting institutions only."
    : " across Massachusetts, including vocational and adult-education schools.";
  dom.summary.append(
    campuses,
    document.createTextNode(" at "),
    institutions,
    document.createTextNode(tail)
  );
}

function renderProvenance() {
  const provenance = view.indexes.provenance;
  dom.provenanceSummary.textContent =
    `Prepared ${provenance.generated} by this repository's data pipeline from ` +
    `the sources below. Nothing on this page is fetched from them at load.`;
  dom.provenanceSources.replaceChildren();
  for (const source of Object.values(provenance.sources ?? {})) {
    if (!source?.title) continue;
    const item = document.createElement("li");
    if (source.url) {
      const link = document.createElement("a");
      link.href = source.url;
      link.textContent = source.title;
      link.rel = "noopener noreferrer";
      item.append(link);
    } else {
      item.append(document.createTextNode(source.title));
    }
    const vintage = source.vintage ? `, ${source.vintage}` : "";
    item.append(document.createTextNode(`${vintage} (fetched ${source.fetched})`));
    dom.provenanceSources.append(item);
  }
}

function renderSelectionStatus() {
  const { layer, areaId } = view.state;
  const layerLabel = LAYER_LABELS[layer] ?? LAYER_LABELS.none;
  const population = isDegreeGrantingOnly(view.state)
    ? "Degree-granting institutions."
    : "All schools, vocational and adult education included.";
  if (areaId) {
    const name = view.indexes.areaName(layer, areaId) ?? areaId;
    const counts = describeCounts(
      areaCounts(view.indexes.assignments, layer, areaId, view.state)
    );
    dom.selectionStatus.textContent =
      `${population} Layer: ${layerLabel}. Selected ${AREA_NOUNS[layer]}: ` +
      `${name} — ${counts}.`;
    dom.clearSelection.hidden = false;
    dom.clearSelection.textContent = `Clear ${name}`;
  } else if (layer !== NO_LAYER) {
    dom.selectionStatus.textContent =
      `${population} Layer: ${layerLabel}. No ${AREA_NOUNS[layer]} selected.`;
    dom.clearSelection.hidden = true;
  } else {
    dom.selectionStatus.textContent = `${population} No layer selected.`;
    dom.clearSelection.hidden = true;
  }
}

function renderTableSection() {
  const model = tableModel({
    indexes: view.indexes,
    state: view.state,
    sort: view.sort,
    filter: view.filter,
  });
  dom.tableCaption.textContent = model.caption;
  dom.tableStatus.textContent = describeTable(model);
  renderHead(dom.headRow, view.sort, onSort);
  renderTable(dom.table, model, {
    onSelectArea: selectArea,
    onSelectCampus: (campusId) => view.map?.openCampus(campusId),
  });
  view.lastModel = model;
  return model;
}

function onSort(key) {
  if (view.sort.key === key) {
    view.sort = { key, direction: view.sort.direction === "asc" ? "desc" : "asc" };
  } else {
    view.sort = { key, direction: "asc" };
  }
  renderTableSection();
}

async function render() {
  if (!view.indexes) return;
  const token = (view.renderToken += 1);
  const previous = view.state;
  view.state = currentState();
  const { layer, areaId } = view.state;

  dom.layerSelect.value = layer;
  dom.populationToggle.checked = !isDegreeGrantingOnly(view.state);

  // Fetch this layer's geometry the first time it is drawn, and only then.
  let collection = null;
  if (layer !== NO_LAYER && !view.unavailableLayers.has(layer)) {
    if (view.loader.isLoaded(layer)) {
      collection = view.loader.get(layer);
    } else {
      setNotice(`Loading ${LAYER_LABELS[layer].toLowerCase()}…`);
      try {
        collection = await view.loader.load(layer);
      } catch (error) {
        view.unavailableLayers.add(layer);
        collection = null;
        setNotice(
          `The ${LAYER_LABELS[layer].toLowerCase()} layer could not be loaded, ` +
            `so its boundaries are not drawn. The table and the other layers ` +
            `still work.`
        );
      }
      if (token !== view.renderToken) return;
      if (collection) setNotice("");
    }
  } else if (layer === NO_LAYER) {
    setNotice("");
  }

  view.map.setAreaLayer(collection, layer === NO_LAYER ? null : layer, {
    assignments: view.indexes.assignments,
    selectedAreaId: areaId,
    state: view.state,
  });

  const campuses = areaId
    ? view.indexes.campusesIn(layer, areaId, view.state)
    : view.indexes.campusesFor(view.state);
  view.map.setCampuses(campuses);

  if (areaId) {
    if (!view.map.fitArea(areaId) && campuses.length) {
      view.map.map.fitBounds(
        campuses.map((campus) => [campus.lat, campus.lon]),
        { padding: [40, 40], maxZoom: 13 }
      );
    }
  } else if (previous?.areaId && !areaId) {
    view.map.fitState();
  }

  renderSummary();
  renderSelectionStatus();
  renderTableSection();
}

/* --- start -------------------------------------------------------------- */

function wireControls() {
  dom.layerSelect.addEventListener("change", (event) => {
    selectLayer(event.target.value);
  });
  dom.clearSelection.addEventListener("click", clearSelection);
  dom.populationToggle.addEventListener("change", (event) => {
    selectPopulation(event.target.checked ? ALL_CAMPUSES : DEGREE_GRANTING);
  });
  dom.filterInput.addEventListener("input", (event) => {
    // A view preference, not the thing being shared: deliberately not in
    // the hash, and preserved across selection changes.
    view.filter = event.target.value;
    if (view.ready) renderTableSection();
  });
  window.addEventListener("hashchange", render);
  window.addEventListener("popstate", render);
}

async function start() {
  wireControls();
  view.map = createMap("map", {
    onSelectArea: selectArea,
    onSelectCampus: () => {},
  });

  dom.tableStatus.textContent = "Loading the published data…";
  setNotice("Loading the published data…");

  let payload;
  try {
    payload = await loadEager();
  } catch (error) {
    setNotice("");
    setError(
      `The published data could not be loaded (${error.file ?? "unknown file"}), ` +
        `so no campuses can be shown. This is a loading failure, not an empty ` +
        `state: reload to try again.`
    );
    dom.summary.textContent = "Data unavailable.";
    dom.tableStatus.textContent = "Data unavailable — no campuses could be loaded.";
    dom.selectionStatus.textContent = "Data unavailable.";
    view.failed = true;
    return;
  }

  view.indexes = buildIndexes(payload);
  setNotice("");
  renderSummary();
  renderProvenance();
  view.ready = true;
  await render();
  view.map.invalidate();
}

start();
