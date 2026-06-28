# BeePOV Map — UI Merge Handoff

**Branch:** `feature-ui-Freddi` · **From:** Freddi · **For:** Karina · **Date:** 2026-06-28

## What this is

My task this week was to bring the existing UI work together into a single, working result you
can keep building on. This branch takes **your design from `karina/design`** as the base —
your layout *and* your charcoal-and-amber visual scheme — and layers on a handful of
usability improvements, all wired to the **real app logic from `main`** (the DuckDB queries,
the actual Berlin POI data, geolocation, and the bee-rating persistence).

To be clear on the direction: you're the decision-maker for the UI, and the Figma was only one
reference among several, not the source of truth. So I kept your visual design intact and only
added things that help on top of it. None of this is final — it's a starting point for you to
take forward next week.

## Your design, kept as-is

Everything that defines the look and feel is yours and unchanged: the near-fullscreen map with
the Streamlit chrome hidden, the compact top bar (brand, district dropdown, search, location,
the five honeycomb category toggles, and the Filters popover), the animated right-hand panel
that slides in on a marker click, the hexagon map pins, the persisted pan/zoom, and the
**charcoal + muted-amber palette** with your muted category colours.

## What I added on top

These are purely additive — they don't change your visual language, just make the app a little
easier to use:

- A **floating legend** in the bottom-left that keys the map pin colours, with a live
  **"N places shown"** count built into it (your pins were colour-coded but had no key).
- **Contextual prompts** that guide a first-time user through the flow — pick a district, then
  choose a category, plus a friendly message when nothing matches the filters.
- **Loading spinners** while the large GeoJSON and the queries run, so the app never looks
  frozen on first load.
- The **short district description** now also appears under the district name in the Overview
  panel, not only inside the Filters popover.

All of these are themed off your design tokens (`INK`, `PAPER`, `ACCENT`, `CATEGORY_COLORS`
at the top of `app.py`), so they automatically follow any palette change you make.

## Ideas of mine I left out (on purpose)

I had a brighter Figma-style palette and per-category-coloured toggle buttons in an earlier
version, but those overrode your design choices, so I dropped them. If you ever want to see
them, they're easy to reintroduce via the design tokens — but the default here is your scheme.

## One small code change

Beyond the visual layer, I added a single defensive line in the query section: if the shared
DuckDB connection briefly returns `None` during overlapping reruns (which crashed the app once
under rapid clicking), it's now treated as an empty result instead. This is a latent edge case
in the shared-connection setup that also exists on `main` — the guard just stops it from
crashing. Nothing else in the logic changed.

## Things worth knowing

- The **floating chips** (legend and prompts) are positioned with `position: fixed`, so on a
  narrow window they can overlap the right-hand panel. They could be made responsive.
- The **search box** only matches district names right now; extending it to places would be a
  natural next step.
- The district description now shows in **two places** (Overview panel and the Filters
  popover) — minor redundancy that's easy to trim.

I ran the merged app end-to-end before handing it over: it loads, the queries return places,
the panel, legend, and description all render, with no errors.
