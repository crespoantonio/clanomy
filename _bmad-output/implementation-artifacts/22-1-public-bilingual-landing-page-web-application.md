# Story 22.1: Public Bilingual Landing Page Web Application

**Epic:** Epic 22 - Landing Page Web App, Simulation Endpoint & E2E LLM Evaluation Suite
**Status:** Completed
**Author:** Amelia & Caravaggio
**Date:** 2026-09-03

---

## 1. Overview & Context

To create a stunning first impression for new visitors and provide a clear showcase of Clanomy's features, privacy model, pricing tiers, and open-source self-hosting instructions, Clanomy includes a responsive, modern landing page served directly by FastAPI.

---

## 2. Technical Implementation

### 2.1 Static Assets & Frontend Code
- In `landing/`:
  - `index.html`: Modern semantic HTML structure featuring hero section, interactive demo simulation, feature grid, pricing comparison table, self-hosting section, and FAQ.
  - `styles.css`: Custom CSS with responsive layouts, CSS variables, glassmorphism effects, smooth animations, and dark mode palette.
  - `script.js`: Interactive UI logic for the simulated chat demo, FAQ accordions, and language switcher.
  - `translations.js`: Full bilingual dictionaries (English and Spanish) enabling instant client-side localization toggle without page reloads.
  - `landing/assets/`: Optimized brand assets (`clanomy_logo.jpg`, `dashboard_preview.jpg`, `favicon.jpg`).

### 2.2 FastAPI Static Mounting
- In `src/main.py`:
  - Mounted `/static` directory pointing to `landing/`.
  - Added root route `@app.get("/")` serving `landing/index.html` with appropriate cache-control headers.

---

## 3. Verification & Acceptance

- Validated via `tests/api/test_landing_page.py`.
- Verified HTTP 200 responses on `/` returning valid HTML and proper content type.
- Verified dynamic language switching between English and Spanish.
