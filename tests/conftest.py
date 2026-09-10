"""Fixtures for driving the published page in a real browser.

The page is served over a plain static HTTP server, the way GitHub Pages
serves it, and opened in Chromium. The tile host is blocked by default, so
no test outcome can depend on a third party being reachable; the tests that
are about tiles allow it explicitly.
"""

import functools
import http.server
import socketserver
import threading

import pytest

from ma_geo.paths import REPO_ROOT

DOCS_DIR = REPO_ROOT / "docs"
TILE_HOST = "server.arcgisonline.com"
TILE_HOST_PATTERN = f"**{TILE_HOST}/**"
TILE_URL_TEMPLATE = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/"
    "World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
)

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "tiles: allows the real tile host, so it needs network access"
    )


@pytest.fixture(scope="session")
def playwright_module():
    playwright = pytest.importorskip(
        "playwright.sync_api",
        reason="playwright is not installed; run `uv sync` to get the dev group",
    )
    return playwright


@pytest.fixture(scope="session")
def browser(playwright_module):
    from playwright.sync_api import Error as PlaywrightError

    with playwright_module.sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch()
        except PlaywrightError as error:
            pytest.skip(
                "the Playwright browser is not installed, so the page tests "
                "cannot run; install it with `uv run playwright install "
                f"chromium` ({error})"
            )
        yield instance
        instance.close()


@pytest.fixture(scope="session")
def site():
    """Serve docs/ the way Pages does, on a loopback port."""
    if not (DOCS_DIR / "index.html").exists():
        pytest.skip("docs/index.html is missing")

    handler = functools.partial(QuietHandler, directory=str(DOCS_DIR))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        yield f"http://{host}:{port}"
        server.shutdown()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - silence the test output
        pass


class PageDriver:
    """A loaded page, plus what it asked the network for."""

    def __init__(self, page, site):
        self.page = page
        self.site = site
        self.requests = []

    def record(self):
        self.page.on("request", lambda request: self.requests.append(request.url))

    def open(self, path="/", *, wait_for_data=True):
        self.page.goto(f"{self.site}{path}")
        if wait_for_data:
            self.wait_for_data()
        return self

    def wait_for_data(self, timeout=15000):
        self.page.wait_for_function("() => window.maGeo && window.maGeo.ready", timeout=timeout)
        self.page.wait_for_timeout(120)

    def settle(self, ms=220):
        self.page.wait_for_timeout(ms)

    # --- what the page asked for ---------------------------------------

    def data_requests(self):
        return [url for url in self.requests if "/data/" in url]

    def tile_requests(self):
        return [url for url in self.requests if TILE_HOST in url]

    def same_origin_requests(self):
        return [url for url in self.requests if url.startswith(self.site)]

    def foreign_requests(self):
        return [url for url in self.requests if not url.startswith(self.site)]

    def requested(self, name):
        return [url for url in self.requests if url.endswith(name)]

    # --- reading the page ----------------------------------------------

    def state(self):
        return self.page.evaluate("() => window.maGeo.state")

    def rows(self):
        """Campus rows only: not the group headings, not the empty-state note."""
        return self.page.locator(
            "#campus-table tbody tr:not(.group-heading):not(:has(.empty-note))"
        )

    def groups(self):
        return self.page.locator("#campus-table tbody")

    def marker_count(self):
        return self.page.evaluate("() => window.maGeo.map.markerCount")

    def area_count(self):
        return self.page.evaluate("() => window.maGeo.map.areaCount")

    def text(self, selector):
        return self.page.locator(selector).inner_text()

    def select_layer(self, layer):
        self.page.select_option("#layer-select", layer)
        self.settle()

    def include_all_schools(self, included=True):
        """Operate the population control the way a visitor would."""
        self.page.set_checked("#population-toggle", included)
        self.settle(400)

    def summary(self):
        return self.text("#summary")

    def eval_module(self, module, expression):
        """Call into one of the page's ES modules directly."""
        return self.page.evaluate(
            f"async () => {{ const m = await import('./modules/{module}.js');"
            f" return ({expression}); }}"
        )


@pytest.fixture
def driver(browser, site):
    """The page with the tile host blocked -- the default for every test."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.route(TILE_HOST_PATTERN, lambda route: route.abort())
    page = context.new_page()
    driver = PageDriver(page, site)
    driver.record()
    yield driver
    context.close()


@pytest.fixture
def tiled_driver(browser, site):
    """The page with the real tile host allowed. Needs network access."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    driver = PageDriver(page, site)
    driver.record()
    yield driver
    context.close()


@pytest.fixture
def blank(browser, site):
    """A blank page on the site's origin, for exercising modules directly."""
    context = browser.new_context()
    context.route(TILE_HOST_PATTERN, lambda route: route.abort())
    page = context.new_page()
    page.goto(f"{site}/index.html")
    driver = PageDriver(page, site)
    yield driver
    context.close()
