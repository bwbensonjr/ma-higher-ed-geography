"""Campus and institution counts, presented honestly (tasks 11.1 - 11.3)."""

import json
import re

from ma_geo.paths import OUT_DIR, REPO_ROOT

DOCS = REPO_ROOT / "docs"
BOSTON = "35"


# --- 11.1 the helpers -------------------------------------------------------

def test_area_counts_come_from_the_published_assignment(blank):
    result = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/counts.js');
            const assignments = await fetch('data/assignments.json').then(r => r.json());
            return { boston: m.areaCounts(assignments, 'municipality', '35'),
                     described: m.describeCounts(m.areaCounts(assignments, 'municipality', '35')),
                     missing: m.areaCounts(assignments, 'county', 'nope') };
        }"""
    )
    assert result["boston"] == {"campuses": 38, "institutions": 35}
    assert result["described"] == "38 campuses, 35 institutions"
    assert result["missing"] is None


def test_both_figures_are_labeled_and_never_interchangeable(blank):
    described = blank.eval_module(
        "counts", "m.describeCounts({campuses: 38, institutions: 35})"
    )
    assert "38 campuses" in described
    assert "35 institutions" in described
    assert described.index("campus") < described.index("institution")


def test_the_statewide_institution_figure_comes_only_from_provenance(blank):
    result = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/counts.js');
            const provenance = await fetch('data/provenance.json').then(r => r.json());
            return { published: m.statewideCounts(provenance, 206),
                     absent: m.statewideCounts({}, 206) };
        }"""
    )
    assert result["published"] == {"campuses": 206, "institutions": 160}
    # With no published figure there is nothing to fall back on: better null
    # than a number the page invented.
    assert result["absent"]["institutions"] is None


def test_there_is_no_helper_that_sums_institution_counts(blank):
    exported = blank.page.evaluate(
        """async () => {
            const m = await import('./modules/counts.js');
            return Object.keys(m);
        }"""
    )
    assert "totalCampuses" in exported  # campus counts are additive
    assert not [
        name for name in exported if "institution" in name.lower() and "total" in name.lower()
    ], exported


def test_no_module_sums_an_institution_count():
    """Inspect every accumulation in the page's own code.

    A grep, so a later contributor cannot quietly add the one figure this
    data cannot support: summed per-area institution counts exceed the
    statewide 160, because an institution with campuses in two areas is
    counted in both.
    """
    offenders = []
    for path in [*(DOCS / "modules").glob("*.js"), DOCS / "app.js"]:
        text = path.read_text()
        for match in re.finditer(r"\.reduce\(", text):
            callback = text[match.end() : match.end() + 160]
            if "institution" in callback:
                offenders.append((path.name, callback.strip()[:120]))
    assert offenders == [], offenders


# --- 11.2 the statewide summary --------------------------------------------

def test_the_summary_states_both_published_figures(driver):
    driver.open()
    summary = driver.text("#summary")
    assert "206 campuses" in summary
    assert "160 institutions" in summary


def test_the_summary_is_read_from_the_data_not_written_into_the_page():
    html = (DOCS / "index.html").read_text()
    assert "206" not in html
    assert "160" not in html
    provenance = json.loads((OUT_DIR / "provenance.json").read_text())
    assert provenance["institution_count"] == 160


# --- 11.3 no summed institution total --------------------------------------

def test_no_summed_institution_total_appears_anywhere(driver):
    """Summing a layer's institution counts exceeds the statewide 160."""
    driver.open()
    sums = driver.page.evaluate(
        """() => {
            const assignments = window.maGeo.indexes.assignments;
            const out = {};
            for (const layer of ['county', 'municipality', 'cbsa']) {
                out[layer] = Object.values(assignments[layer])
                    .reduce((total, entry) => total + entry.institution_count, 0);
            }
            return out;
        }"""
    )
    assert sums == {"county": 182, "municipality": 196, "cbsa": 169}

    for layer in ("county", "municipality", "cbsa"):
        driver.select_layer(layer)
        driver.settle(900)
        text = f"{driver.text('#summary')} {driver.text('#table-status')} {driver.text('#selection-status')}"
        assert str(sums[layer]) not in text, (layer, text)
        assert "160 institutions" in driver.text("#summary")


def test_a_campus_total_may_be_a_sum(driver):
    """Campus counts are additive, so the grouped view states 206."""
    driver.open()
    driver.select_layer("county")
    driver.settle(700)
    assert "206 campuses" in driver.text("#table-status")


def test_the_grouped_headings_report_per_area_counts_not_shares(driver):
    driver.open()
    driver.select_layer("cbsa")
    driver.settle(900)
    headings = driver.page.evaluate(
        """() => [...document.querySelectorAll('.group-heading th')]
            .map(th => th.innerText.trim())"""
    )
    published = driver.page.evaluate(
        """() => {
            const index = window.maGeo.indexes;
            const out = {};
            for (const [areaId, area] of Object.entries(index.areaIndex.cbsa)) {
                out[area.name] = index.assignments.cbsa[areaId];
            }
            return out;
        }"""
    )
    assert len(headings) == len([e for e in published.values() if e["campus_count"]])
    for heading in headings:
        name = heading.split("—")[0].strip()
        entry = published[name]
        assert str(entry["campus_count"]) in heading
        assert str(entry["institution_count"]) in heading
