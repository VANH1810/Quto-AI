# Design QA — Dự báo khu vực

## Evidence

- Source visual truth: `E:\Documents\Quto-AI\frontend\design-qa\figma-desktop2.png` (Figma node `29:252`, frame `Desktop - 2`).
- Implementation screenshot: in-app Browser capture `finalShotLaptop3`, emitted in the current QA run at 1366 × 768 after dashboard data and commune overview data loaded.
- Previous persisted baseline screenshot: `E:\Documents\Quto-AI\frontend\design-qa\implementation-desktop.png`.
- Full-view comparison evidence: source and current browser capture were opened together in the same comparison pass.
- Focused comparison: not required after the full-view pass because typography, controls, risk dots, chart labels, action rows, and card content were readable at the comparison scale.
- Responsive evidence: measured browser layouts at 1366 × 768, 820 × 1180, and 390 × 844.

## State

- Default highest-priority commune selected from the same alert dataset as Home.
- Seven forecast days loaded from `GET /api/v1/communes/{id}/overview`.
- Current day active; warning color and level are driven by the Home/map alert for the active commune.

## Findings

- No actionable P0, P1, or P2 findings remain.
- Fonts and typography: the existing Roboto family, header hierarchy, large temperature value, blue uppercase section headings, card labels, and compact metric values retain the Figma intent. Dynamic commune and hazard labels truncate or wrap safely.
- Spacing and layout rhythm: the desktop composition keeps the Figma sidebar + overview + two lower panels, but intentionally compresses card heights and vertical gaps so all primary content fits a 1366 × 768 laptop viewport. The document measured 1366 × 768 with no horizontal or vertical document overflow.
- Colors and tokens: existing header tokens are unchanged; warning accents come from the shared risk tokens and drive day borders, active state, risk panel, chart, and action icons consistently.
- Image quality: the optimized Figma rain background and existing official logo asset remain in use; no placeholder or CSS-drawn image replaces a source asset.
- Copy and content: all seven days, location, weather metrics, risk type, danger level, chart, and recommendations are present. Dynamic copy comes from dashboard data and the commune overview API.
- Icons: existing Lucide icons are reused consistently. Their outline treatment is a minor P3 difference from the filled Figma action artwork.
- Accessibility: semantic landmarks, headings, combobox/listbox behavior, keyboard day buttons, active/pressed states, chart description, focus states, and reduced-motion/transparency handling are present.

## Interaction And Responsive Checks

- Changing the commune from Mường Nhé to Tủa Chùa updated location, all seven day cards, metrics, warning, chart, and recommendations.
- Selecting 20/7 updated rainfall to 67 mm, hazard to “Mưa lớn”, and danger level to 4/5 in the QA fixture.
- Navigating back to Home retained “Xã Tủa Chùa” in the shared picker and opened the same commune detail.
- Dropdown exposed all 45 communes with alert label and risk level; keyboard semantics are preserved.
- Laptop 1366 × 768: seven days and all detail panels fit in one viewport; document width and height matched the viewport.
- Tablet 820 × 1180: overview and lower panels remained two-column, with the day list horizontally scrollable and no document-width overflow.
- Mobile 390 × 844: overview and lower panels stack to one column, the day list scrolls horizontally, and measured content width matched the viewport.
- Browser console errors and warnings: none.

## Comparison History

### Pass 1

- P1: Forecast used an independent static dataset, so location and warnings could not match Home. Replaced it with shared dashboard data, the existing commune-overview API, and a shared location provider.
- P2: desktop content exceeded common laptop height. Reduced vertical gaps, card heights, panel padding, chart height, and overview proportions while retaining the Figma composition.
- P2: current and future days could show too few recommendations. Merged matching API tasks with the current Home/map recommendations, deduplicated, and capped at three.

### Pass 2

- Post-fix browser evidence shows seven loaded day cards, three action rows, aligned panels, correct risk colors, and no 1366 × 768 overflow.
- No further P0/P1/P2 differences were found.

## Follow-up Polish

- P3: use the exact filled action-icon assets if they become maintained production assets.
- P3: persist a fresh browser screenshot artifact for every dynamic API state if visual-regression automation is added later.

final result: passed
