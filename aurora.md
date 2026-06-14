# BeePOVMap — Architecture & Data Notes

## Architecture (what actually exists)

```
OSM GeoJSON + VBB transit CSV
        │
        ▼
build_database.py   ← run once locally to regenerate data
        │  classifies POIs, spatial-joins to districts, exports
        ▼
data/berlin_pois.parquet   ← the "database", committed to the repo
        │
        ▼
app.py  ← Streamlit app reads the parquet via DuckDB
        │
        ▼
Streamlit Cloud   ← hosting (reads parquet from the repo)
```

**Is Streamlit connected to DuckDB?** Yes. `app.py` opens a cached in-memory DuckDB connection and queries the parquet file directly with SQL. No separate database server needed.

---

## What's in the parquet (current state)

**47,962 rows total, 12 districts:**

| District | Rows |
|---|---|
| Mitte | 7,992 |
| Charlottenburg-Wilmersdorf | 6,353 |
| Tempelhof-Schöneberg | 5,252 |
| Friedrichshain-Kreuzberg | 4,583 |
| Pankow | 4,145 |
| Steglitz-Zehlendorf | 3,781 |
| Neukölln | 3,701 |
| Treptow-Köpenick | 3,087 |
| Lichtenberg | 2,548 |
| Marzahn-Hellersdorf | 2,509 |
| Reinickendorf | 2,093 |
| Spandau | 1,918 |

**Category + subcategory breakdown:**

| Category | Subcategory | Count |
|---|---|---|
| Culture & Heritage | Landmark or Trail | 8,230 |
| Culture & Heritage | Churches | 642 |
| Culture & Heritage | Galleries | 356 |
| Culture & Heritage | Museums | 247 |
| Culture & Heritage | Hiking & Bike Trails | 10 |
| Food & Drink | Restaurants | 7,565 |
| Food & Drink | Cafes | 2,582 |
| Food & Drink | Bakeries | 1,244 |
| Nature & Outdoors | Parks & Gardens | 6,090 |
| Nature & Outdoors | Hiking & Bike Trails | 463 |
| Nature & Outdoors | Lakes & Swimming | 95 |
| Nature & Outdoors | Landmark or Trail | 2 |
| Nightlife | Bars | 973 |
| Nightlife | Clubs | 141 |
| Nightlife | Breweries & Wine Bars | 132 |
| Nightlife | Markets | 113 |
| Public Transport | Transit Stop | 19,071 |

**Boolean filter flags (rows where TRUE):**

| Column | Count |
|---|---|
| is_free | 25,942 |
| is_accessible | 26,455 |
| is_vegan_friendly | 3,219 |
| is_lgbtq | 57 |

---

## What's working well

- Full pipeline works end-to-end: `build_database.py` → parquet → `app.py` renders the map
- All 4 refinement filters (`is_free`, `is_accessible`, `is_vegan_friendly`, `is_lgbtq`) are in the parquet and wired up in the app
- "Max results + shuffle" (Step 4 in the sidebar) is implemented — this is the core anti-overload mechanic
- All 12 Berlin districts are in the data
- Hiking & Bike Trails is now a real subcategory — the checkbox in the app actually works

---

## Curation changes made (June 14 2026)

These changes were added to reduce what Mara sees to only well-documented, relevant places — without her having to do anything differently.

### 1. Quality score (`build_database.py`)
Added a `quality_score` column (0–3) based purely on data completeness signals:
- +1 if the place has a real name (not "Unnamed...")
- +1 if the `fee` tag is present
- +1 if the `wheelchair` tag is present

**lgbtq and diet tags are intentionally excluded** — those are user preference filters and should not affect whether a place appears by default for users who don't care about them.

Transit stops get a fixed score of 3 (they're always reliable).

The app filters by: `quality_score >= 1` for Nature & Outdoors (parks don't typically get fee/wheelchair tags in OSM so >= 2 would be too strict), `quality_score >= 2` for everything else.

### 2. Diversity in results (`app.py`)
Instead of returning up to 50 random pins, the app now:
1. Fetches a pool of 200 results (ordered randomly so shuffle button still works)
2. Splits them evenly across selected subcategories in Python

So if Mara selects Food & Drink with max 15 and has Restaurants + Cafés + Bakeries ticked, she gets 5 of each instead of a random pile dominated by restaurants.

### 3. Named-only LineStrings (`build_database.py`)
Unnamed trails and paths (LineString geometries with no name) are now excluded from the database entirely. They were previously being turned into pins on the map even though:
- The base map already draws them visually
- They had no useful information to add (just "Unnamed Landmark or Trail")

Named trails (Berliner Mauerweg, Wannsee-Route etc.) are kept and classified as "Hiking & Bike Trails".

### 4. Trail deduplication (`build_database.py`)
OSM represents long trails as many connected line segments — Berliner Mauerweg had 26 entries. After deduplication, each trail gets one entry per district it passes through (so Berliner Mauerweg becomes ~9 entries, one per district). Chain restaurants like McDonald's are NOT deduplicated because each branch is a genuinely distinct location.

---

## Data problems still to fix

### 1. "Landmark or Trail" catch-all is still large (8,230 rows)
Entries that didn't match any specific subcategory tag land here. The quality filter reduces what's shown in the app but the underlying data is still noisy. Tighter OSM tag matching in `build_database.py` would help.

### 2. `is_lgbtq` is nearly empty (57 rows)
OSM tagging for LGBTQ+ spaces is sparse. The filter exists in the UI but almost never returns results. Options:
- [ ] Find a richer OSM query or external source
- [ ] Flag it as "data limited" in the UI
- [ ] Remove the filter temporarily until data improves

### 3. Only 6 of 12 districts are selectable in the app
The parquet has all 12 but `app.py` hardcodes only 6 in `DISTRICT_CENTERS`. The missing 6 are: Steglitz-Zehlendorf, Treptow-Köpenick, Marzahn-Hellersdorf, Lichtenberg, Reinickendorf, Spandau.

---

## Filters designed but not yet implemented

| Filter | Status |
|---|---|
| Open Now | No `opening_hours` column in parquet — not fetched from OSM |
| Open Late (after 22:00) | Same — no opening hours data |
| Near Public Transport (≤5 min walk) | Transit stops are in the data but no distance calculation exists |
| Outdoor Seating | No `outdoor_seating` column |

"Open Now/Late" and "Near Public Transport" are the most complex — they require parsing OSM opening hours strings or computing geospatial distance at query time.

---

## What the product team needs from the data team

| What they need | Current status | What's needed |
|---|---|---|
| Working app on Streamlit Cloud | Not deployed yet | Push repo + connect Streamlit Cloud |
| All 12 districts selectable | Only 6 in `app.py` | Add 6 missing districts to `DISTRICT_CENTERS` |
| District multi-select | Currently single-select (`selectbox`) | Change to `multiselect` in `app.py` |
| "Open Now" filter working | Not possible yet | Add `opening_hours` to OSM fetch + parse logic |
| Rating system | Not in data or UI at all | Needs design decision first |
| LGBTQ+ filter returning results | 57 rows total | Richer OSM query or flag as limited |

**Biggest blocker for product team right now: Streamlit Cloud deployment.** Once there's a live URL they can test it and give UI feedback. Everything else is refinement.

---

## Branch merge notes

### Merging `aurora` → `main`
Safe to do. Changes: `build_database.py` (quality score, LineString fix, trail deduplication), `app.py` (quality filter, diversity logic), `data/berlin_pois.parquet` (rebuilt), `aurora.md` (new file). No conflicts with any other branch.

### Merging `feature-rating-system` after `aurora` is in main
There will be a **merge conflict on `app.py`** — both branches changed the query section. When resolving, the final SELECT must include **both**:

```python
SELECT name, district_name, master_category, subcategory, wkt_geometry, quality_score
```

- `district_name` — added by the rating branch, **required** for `get_place_id()`. If it's missing, every bee rating gets stored under `"placename|Unknown district|..."` and is never retrieved correctly. All ratings break silently.
- `quality_score` — added by aurora branch, required for the quality filter in the WHERE clause.

The WHERE clause from `aurora` also needs to be kept:
```python
AND (
    (master_category = 'Nature & Outdoors' AND quality_score >= 1) OR
    (master_category != 'Nature & Outdoors' AND quality_score >= 2)
)
```

The shuffle/limit logic (their hash-based seed vs aurora's diversity spread) is a style choice — either works, but the diversity spread is better for anti-overload.

### `feature-ui-map-prototype`
Obsolete — reads from `berlin_pois.csv` which no longer exists. Whoever owns it needs to switch to the parquet/DuckDB approach before it can be merged.

---

## Scheduled data extraction (planned, not done)

The README mentions GitHub Actions for automatic scheduled re-fetching of OSM data. **This does not exist yet.** Currently the raw data was fetched manually:
1. Someone ran Overpass Turbo queries in the browser
2. Downloaded the results as GeoJSON files
3. Merged them into `data/layer_master_berlin_pois.geojson` and committed it

This means the data is a snapshot — if a café opens or closes in Berlin, the app won't know. To fix this, a GitHub Actions workflow (`.github/workflows/fetch_data.yml`) would need to be created that runs the Overpass queries on a schedule (e.g. weekly) and re-runs `build_database.py` to regenerate the parquet.

---

## OSM tags used to fetch and classify the data

All raw data comes from Overpass API (OpenStreetMap). `build_database.py` reads the raw GeoJSON and maps OSM tags to our categories.

### Food & Drink
| Subcategory | OSM tags used |
|---|---|
| Restaurants | `amenity` = restaurant, fast_food, food_court |
| Cafes | `amenity` = cafe, coffee_shop |
| Bakeries | `amenity` = bakery OR `shop` = bakery |

### Nightlife
| Subcategory | OSM tags used |
|---|---|
| Bars | `amenity` = bar |
| Clubs | `amenity` = nightclub |
| Breweries & Wine Bars | `amenity` = brewery, wine_bar OR `shop` = wine OR `craft` = brewery |
| Markets | `amenity` = marketplace |

### Culture & Heritage
| Subcategory | OSM tags used |
|---|---|
| Museums | `tourism` = museum |
| Galleries | `tourism` = gallery |
| Churches | `amenity` = place_of_worship |
| Landmark or Trail *(catch-all)* | `tourism` = attraction, viewpoint OR `historic` = memorial, monument, city_gate, castle, building, ruins, checkpoint |

### Nature & Outdoors
| Subcategory | OSM tags used |
|---|---|
| Parks & Gardens | `leisure` = park, garden |
| Lakes & Swimming | `natural` = water OR `leisure` = bathing_place |
| Hiking & Bike Trails | LineString or MultiLineString geometry **with a name** — unnamed paths excluded |

### Boolean flags
| Flag | OSM tags used |
|---|---|
| `is_free` | `fee` = no OR `leisure` = park OR category = Nature & Outdoors |
| `is_accessible` | `wheelchair` = yes, limited |
| `is_lgbtq` | `lgbtq`, `gay`, `lesbian`, or `transgender` tag present and not = "no" |
| `is_vegan_friendly` | `diet:vegan` or `diet:vegetarian` = yes, only |

### Quality score (0–3)
One point each for: has a real name, `fee` tag present, `wheelchair` tag present. lgbtq and diet tags excluded — those are user preference filters, not data quality signals. Threshold to appear in app: Nature & Outdoors ≥ 1, everything else ≥ 2.
