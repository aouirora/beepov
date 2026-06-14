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

## What's in the parquet right now

**51,630 rows total, 12 districts:**

| District | Rows |
|---|---|
| Mitte | 8,357 |
| Charlottenburg-Wilmersdorf | 6,701 |
| Tempelhof-Schöneberg | 5,620 |
| Friedrichshain-Kreuzberg | 4,791 |
| Pankow | 4,420 |
| Neukölln | 4,025 |
| Steglitz-Zehlendorf | 4,020 |
| Treptow-Köpenick | 3,637 |
| Marzahn-Hellersdorf | 2,818 |
| Lichtenberg | 2,753 |
| Reinickendorf | 2,278 |
| Spandau | 2,210 |

**Category + subcategory breakdown:**

| Category | Subcategory | Count |
|---|---|---|
| Culture & Heritage | Landmark or Trail | 8,243 |
| Culture & Heritage | Churches | 642 |
| Culture & Heritage | Galleries | 356 |
| Culture & Heritage | Museums | 247 |
| Food & Drink | Restaurants | 7,565 |
| Food & Drink | Cafes | 2,582 |
| Food & Drink | Bakeries | 1,244 |
| Nature & Outdoors | Parks & Gardens | 6,090 |
| Nature & Outdoors | Landmark or Trail | 4,130 |
| Nature & Outdoors | Lakes & Swimming | 95 |
| Nightlife | Bars | 973 |
| Nightlife | Clubs | 141 |
| Nightlife | Breweries & Wine Bars | 132 |
| Nightlife | Markets | 113 |
| Public Transport | Transit Stop | 19,071 |

**Boolean filter flags (rows where TRUE):**

| Column | Count |
|---|---|
| is_free | 29,607 |
| is_accessible | 26,500 |
| is_vegan_friendly | 3,219 |
| is_lgbtq | 57 |

---

## What's working well

- Full pipeline works end-to-end: `build_database.py` → parquet → `app.py` renders the map
- All 4 refinement filters (`is_free`, `is_accessible`, `is_vegan_friendly`, `is_lgbtq`) are in the parquet and wired up in the app
- "Max results + shuffle" (Step 4 in the sidebar) is implemented — this is the core anti-overload mechanic
- All 12 Berlin districts are in the data

---

## Data problems to fix (data team)

### 1. Misclassified subcategories in `build_database.py`
`np.select` picks the first matching condition, so some POIs land in the wrong category:
- "Parks & Gardens" → 4 rows under Culture & Heritage (should be 0)
- "Lakes & Swimming" → 2 rows under Culture & Heritage (should be 0)
- "Landmark or Trail" → 8,243 under Culture & Heritage + 4,130 under Nature & Outdoors = **12,373 rows** (~24% of all POIs) hitting the catch-all default. This means their OSM tags didn't match any specific subcategory. Needs tighter tag matching.

### 2. `is_lgbtq` is nearly empty (57 rows)
OSM tagging for LGBTQ+ spaces is sparse across Berlin. The filter exists in the UI but almost never returns results. Options:
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
| Cleaner category counts | "Landmark or Trail" = 12k rows (catch-all bloat) | Tighten classification in `build_database.py` |
| District multi-select | Currently single-select (`selectbox`) | Change to `multiselect` in `app.py` |
| "Open Now" filter working | Not possible yet | Add `opening_hours` to OSM fetch + parse logic |
| Rating system | Not in data or UI at all | Needs design decision first |
| LGBTQ+ filter returning results | 57 rows total | Richer OSM query or flag as limited |

**Biggest blocker for product team right now: Streamlit Cloud deployment.** Once there's a live URL they can test it and give UI feedback. Everything else is refinement.
