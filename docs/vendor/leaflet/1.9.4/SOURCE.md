# Leaflet 1.9.4 (vendored)

Committed rather than loaded from a CDN so the library the page runs is the
library in this repository, reviewable and pinned. The page's one external
request is its base map tiles; its own code is all served from here.

- Upstream: <https://unpkg.com/leaflet@1.9.4/dist/>
- Mirror cross-checked against: <https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/>
- License: BSD-2-Clause, (c) Volodymyr Agafonkin and Leaflet contributors

Both mirrors were downloaded independently and every file's SHA-256 matched,
which is what verifies these bytes are the published release.

| File | SHA-256 |
| --- | --- |
| `leaflet.js` | `db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a` |
| `leaflet.css` | `a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6` |

`images/` holds `layers.png`, `layers-2x.png`, `marker-icon.png`,
`marker-icon-2x.png`, and `marker-shadow.png`, which `leaflet.css`
references by relative `url(images/...)`. Their checksums were cross-checked
the same way. The page draws circle markers rather than image pins, so the
marker files are here for completeness and for Leaflet's own defaults.

To re-verify:

```sh
cd docs/vendor/leaflet/1.9.4 && shasum -a 256 leaflet.js leaflet.css images/*.png
```
