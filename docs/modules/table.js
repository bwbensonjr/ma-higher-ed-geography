/**
 * Rendering the table model into a real table.
 *
 * A real <table> with header cells, one <tbody> per group in grouped mode,
 * and buttons (not links) for the geography actions, so the whole thing is
 * reachable by keyboard and readable by assistive technology. The model is
 * rebuilt and swapped in whole: at 206 rows that is well under a frame, and
 * it keeps the three modes one pure function of state.
 */

import { COLUMNS } from "./rows.js";
import { describeCounts, plural } from "./counts.js";

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child == null) continue;
    node.append(child);
  }
  return node;
}

export function renderHead(headRow, sort, onSort) {
  headRow.replaceChildren();
  for (const column of COLUMNS) {
    const active = sort?.key === column.key;
    const arrow = !active ? "" : sort.direction === "desc" ? " ↓" : " ↑";
    const cell = el("th", {
      scope: "col",
      "aria-sort": !active
        ? null
        : sort.direction === "desc"
          ? "descending"
          : "ascending",
    });
    if (column.sortable) {
      const button = el("button", {
        type: "button",
        text: `${column.label}${arrow}`,
        title: `Sort by ${column.label}`,
      });
      button.addEventListener("click", () => onSort(column.key));
      cell.append(button);
    } else {
      cell.textContent = column.label;
    }
    headRow.append(cell);
  }
}

function areaCell(row, column, onSelectArea) {
  const cell = el("td");
  const area = column.layer ? row.areas[column.layer] : null;
  if (!column.layer) {
    cell.textContent = row.cells[column.key];
    return cell;
  }
  if (!area || !area.name) {
    // A campus outside every statistical area gets plain text, not a
    // control that would select nothing.
    cell.textContent = "—";
    cell.setAttribute("aria-label", "no statistical area");
    return cell;
  }
  const button = el("button", {
    type: "button",
    class: "area-link",
    text: area.name,
    title: `Show ${area.name}`,
  });
  button.addEventListener("click", () => onSelectArea(area.layer, area.areaId));
  cell.append(button);
  return cell;
}

function renderRow(row, { onSelectArea, onSelectCampus }) {
  const tr = el("tr", { dataset: { campusId: row.campusId } });
  for (const column of COLUMNS) {
    tr.append(areaCell(row, column, onSelectArea));
  }
  tr.addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    onSelectCampus?.(row.campusId);
  });
  return tr;
}

function emptyBody(note, columnCount) {
  const tbody = el("tbody");
  tbody.append(
    el("tr", {}, [
      el("td", { colspan: String(columnCount), class: "empty-note", text: note }),
    ])
  );
  return tbody;
}

export function renderTable(table, model, handlers) {
  const bodies = [];

  if (model.empty) {
    bodies.push(emptyBody(model.emptyNote, COLUMNS.length));
  } else if (model.mode === "grouped") {
    for (const group of model.groups) {
      const tbody = el("tbody");
      const heading = el("tr", { class: "group-heading" });
      const counts = describeCounts(group.counts);
      const shown =
        model.filtering && group.shownCount !== group.counts.campuses
          ? ` · ${group.shownCount} shown`
          : "";
      const th = el("th", { colspan: String(COLUMNS.length), scope: "colgroup" });
      const button = el("button", {
        type: "button",
        class: "area-link",
        text: group.name,
        title: `Show only ${group.name}`,
      });
      button.addEventListener("click", () =>
        handlers.onSelectArea(group.layer, group.areaId)
      );
      th.append(button, el("span", { class: "group-counts", text: ` — ${counts}${shown}` }));
      heading.append(th);
      tbody.append(heading);
      for (const row of group.rows) tbody.append(renderRow(row, handlers));
      bodies.push(tbody);
    }
  } else {
    const tbody = el("tbody");
    for (const row of model.rows) tbody.append(renderRow(row, handlers));
    bodies.push(tbody);
  }

  for (const existing of [...table.tBodies]) existing.remove();
  table.append(...bodies);
}

/** The line above the table: what it holds, and what it is restricted to. */
export function describeTable(model) {
  if (model.mode === "area") {
    const { name, counts } = model.restriction;
    if (counts && counts.campuses === 0) {
      return `${name} contains no campuses.`;
    }
    const shown = model.filtering ? ` Showing ${model.rowCount}.` : "";
    return `Restricted to ${name}: ${describeCounts(counts)}.${shown}`;
  }
  if (model.mode === "grouped") {
    const groups = plural(model.groups.length, "group");
    const omitted =
      model.omittedGroups > 0
        ? ` ${model.omittedGroups} with no campuses are not listed.`
        : "";
    return `${plural(model.rowCount, "campus", "campuses")} in ${groups}.${omitted}`;
  }
  const of =
    model.rowCount === model.totalCount
      ? ""
      : ` of ${model.totalCount.toLocaleString("en-US")}`;
  return `${plural(model.rowCount, "campus", "campuses")}${of}.`;
}
