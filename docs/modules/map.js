/**
 * The Leaflet map: base tiles, campus markers, one area layer at a time.
 *
 * Both the polygons and the markers are drawn on a canvas renderer. 351
 * polygons and 206 markers as individual SVG nodes is where a page like
 * this becomes slow to pan on a phone; on canvas it is one surface.
 *
 * The base map is a third party, so it is added and never awaited, and its
 * errors are swallowed rather than routed into the page's data-failure
 * state: losing the tiles costs the map its backdrop and nothing else.
 */

import { areaStyle, legendEntries } from "./shading.js";
import { areaCounts, describeCounts } from "./counts.js";
import { typeLabel } from "./rows.js";

// Esri's light gray canvas: muted cartography by design, keyless, so there
// is no credential for a public static page to try to keep secret. Note the
// {z}/{y}/{x} order, which is Esri's, not the usual {z}/{x}/{y}.
//
// Basemap history: this page started on CARTO Positron, which now stamps an
// "API KEY REQUIRED" watermark across keyless tiles -- served with HTTP 200,
// so nothing errors and the map looks broken only to a human. Esri's light
// gray is the closest muted keyless equivalent. It renders only through zoom
// 16, so TILE_MAX_NATIVE_ZOOM lets Leaflet upscale beyond that rather than
// leave the closest zooms blank.
export const TILE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/" +
  "World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}";
export const TILE_ATTRIBUTION =
  'Tiles &copy; <a href="https://www.esri.com/">Esri</a> — Esri, HERE, Garmin, ' +
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
  "contributors";
export const TILE_MAX_NATIVE_ZOOM = 16;

// The whole state, comfortably.
export const MASSACHUSETTS_BOUNDS = [
  [41.18, -73.55],
  [42.92, -69.85],
];

const MARKER_STYLE = {
  radius: 5,
  weight: 1.5,
  color: "#6d1b0d",
  fillColor: "#e8442a",
  fillOpacity: 0.95,
  opacity: 1,
};

export function createMap(container, { onSelectArea, onSelectCampus } = {}) {
  const map = L.map(container, {
    renderer: L.canvas({ padding: 0.3 }),
    preferCanvas: true,
    minZoom: 7,
    maxZoom: 19,
    zoomControl: true,
  });
  map.fitBounds(MASSACHUSETTS_BOUNDS);

  const tiles = L.tileLayer(TILE_URL, {
    attribution: TILE_ATTRIBUTION,
    maxZoom: 19,
    maxNativeZoom: TILE_MAX_NATIVE_ZOOM,
    crossOrigin: true,
  });
  let tileErrors = 0;
  // Deliberately silent: a tile that fails is not a data failure.
  tiles.on("tileerror", () => {
    tileErrors += 1;
  });
  tiles.addTo(map);

  // Panes keep the ordering explicit: tiles beneath areas beneath markers.
  map.createPane("areas");
  map.getPane("areas").style.zIndex = 400;
  map.createPane("markers");
  map.getPane("markers").style.zIndex = 500;

  const areaPane = L.layerGroup([], { pane: "areas" }).addTo(map);
  const markerPane = L.layerGroup([], { pane: "markers" }).addTo(map);

  let areaLayer = null;
  let markers = [];
  let legend = null;

  function clearAreas() {
    areaPane.clearLayers();
    areaLayer = null;
  }

  function renderLegend(layer) {
    if (legend) {
      legend.remove();
      legend = null;
    }
    if (!layer) return;
    const entries = legendEntries(layer);
    legend = L.control({ position: "bottomleft" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "legend");
      const heading = document.createElement("h3");
      heading.textContent = "Campuses per area";
      const list = document.createElement("ul");
      for (const entry of entries) {
        const item = document.createElement("li");
        const swatch = document.createElement("span");
        swatch.className = "swatch";
        swatch.style.background = entry.color;
        swatch.style.opacity = String(entry.opacity);
        const label = document.createElement("span");
        label.textContent = entry.label;
        item.append(swatch, label);
        list.append(item);
      }
      div.append(heading, list);
      return div;
    };
    legend.addTo(map);
  }

  return {
    map,
    get tileErrors() {
      return tileErrors;
    },
    get markerCount() {
      return markers.length;
    },
    get areaCount() {
      return areaLayer ? Object.keys(areaLayer._layers ?? {}).length : 0;
    },

    /** Draw one area layer, or none. */
    setAreaLayer(collection, layer, { assignments, selectedAreaId = null } = {}) {
      clearAreas();
      renderLegend(collection ? layer : null);
      if (!collection) return;

      areaLayer = L.geoJSON(collection, {
        pane: "areas",
        renderer: L.canvas({ padding: 0.3 }),
        style: (feature) => {
          const areaId = String(feature.properties.area_id);
          const counts = areaCounts(assignments, layer, areaId);
          return areaStyle(layer, counts?.campuses ?? 0, {
            selected: selectedAreaId != null && areaId === String(selectedAreaId),
            dimmed: selectedAreaId != null && areaId !== String(selectedAreaId),
          });
        },
        onEachFeature: (feature, featureLayer) => {
          const areaId = String(feature.properties.area_id);
          const counts = areaCounts(assignments, layer, areaId);
          const name = feature.properties.name;
          featureLayer.bindTooltip(
            `<span class="area-tooltip"><strong>${name}</strong>${describeCounts(
              counts
            )}</span>`,
            { sticky: true }
          );
          featureLayer.on("click", () => onSelectArea?.(layer, areaId));
        },
      });
      areaPane.addLayer(areaLayer);
    },

    /** Draw exactly these campuses as markers. */
    setCampuses(campuses) {
      markerPane.clearLayers();
      markers = campuses.map((campus) => {
        const marker = L.circleMarker([campus.lat, campus.lon], {
          ...MARKER_STYLE,
          pane: "markers",
          bubblingMouseEvents: false,
        });
        marker.campusId = campus.id;
        marker.bindTooltip(campus.institution, { direction: "top" });
        marker.bindPopup(() => campusPopup(campus), { minWidth: 220 });
        marker.on("click", () => onSelectCampus?.(campus.id));
        markerPane.addLayer(marker);
        return marker;
      });
    },

    openCampus(campusId) {
      const marker = markers.find((candidate) => candidate.campusId === campusId);
      if (marker) marker.openPopup();
    },

    /** Bring one area into view. */
    fitArea(areaId) {
      if (!areaLayer) return false;
      let bounds = null;
      areaLayer.eachLayer((featureLayer) => {
        if (String(featureLayer.feature.properties.area_id) === String(areaId)) {
          bounds = featureLayer.getBounds();
        }
      });
      if (bounds && bounds.isValid()) {
        map.fitBounds(bounds, { padding: [24, 24] });
        return true;
      }
      return false;
    },

    fitState() {
      map.fitBounds(MASSACHUSETTS_BOUNDS);
    },

    invalidate() {
      map.invalidateSize();
    },
  };
}

/** The campus popup. Empty attributes are omitted, never shown blank. */
export function campusPopup(campus) {
  const wrapper = document.createElement("div");
  wrapper.className = "popup";

  const heading = document.createElement("h3");
  heading.textContent = campus.institution;
  wrapper.append(heading);

  if (campus.campus) {
    const campusName = document.createElement("p");
    campusName.className = "campus-name";
    campusName.textContent = campus.campus;
    wrapper.append(campusName);
  }

  const list = document.createElement("dl");
  const place = [campus.city, campus.zip_code].filter(Boolean).join(" ");
  const fields = [
    ["Address", campus.address ? campus.address.trim() : ""],
    ["City", place],
    ["Telephone", campus.telephone],
    ["Type", typeLabel(campus.institution_type)],
    ["Category", campus.category],
    ["Degrees", campus.degrees_offered],
  ];
  for (const [label, value] of fields) {
    if (!value) continue;
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  }
  if (campus.website) {
    const dt = document.createElement("dt");
    dt.textContent = "Website";
    const dd = document.createElement("dd");
    const link = document.createElement("a");
    link.href = campus.website;
    link.textContent = campus.website.replace(/^https?:\/\//, "").replace(/\/$/, "");
    link.rel = "noopener noreferrer";
    link.target = "_blank";
    dd.append(link);
    list.append(dt, dd);
  }
  wrapper.append(list);
  return wrapper;
}
