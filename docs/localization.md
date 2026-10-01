# English / korean UI

## Scope and design

The existing React/JSX app, hash routes and form state are retained. Both headers use the same native, labelled select. Its options are `English` and `korean`, in that order. English is the initial language. Account and guest screens subscribe to a shared external store without remounting page components.

- `frontend/src/i18n/en.json`, `ko.json`: common UI keys and interpolation variables.
- `core.js`: locale validation, persistence, translation fallback, deferred error/notification messages and missing-key reporting.
- `react.jsx`: React subscription and shared language selector.
- `copy.js`: question structure, translated labels and stable saved choice values.
- `model.js`: locale-aware summary presentation without mutating answers.
- `Portal.jsx`, `App.jsx`: all existing pages, modal, validation, loading/error/empty states, accessibility labels and document titles.
- `domain.js`: date formatting with the existing `Asia/Seoul` policy.

There is no added runtime dependency, translation API, automatic patient-text translation or page reload. The preference is stored separately from patient/demo data: `localStorage["visit-notes-language"]` is `en` or `ko`. Missing, malformed or inaccessible preferences default to English. A storage failure retains the in-memory choice and displays an accessible notice. Logout and demo resets do not erase the language preference. Same-origin tabs follow preference changes through the storage event.

Changing language preserves the route, selected record, authentication, input values, questionnaire stage, list filter and review confirmation. Only presentation and the language preference change; data persistence effects retain their existing data/step dependencies. The selector retains focus. Page-heading focus is reserved for navigation, and document titles update separately.

## Data fidelity

Patient names, clinician/hospital names, free text and other record content are kept as entered. Existing Korean demo records therefore still contain Korean data in English mode. An answer selected from a predefined option carries an explicit `option` marker so its display label can change language. A typed answer is never inferred to be a translated option, even if it equals the Korean label. Legacy saved values continue to work without a migration or bulk rewrite.

New simulated handoffs retain a structured answer snapshot alongside the original summary. Both language views use that immutable snapshot. For legacy text-only snapshots, the retained answers are used only if they reproduce the original stored summary exactly. Otherwise only known section headings are localized and the historical body text is preserved. No snapshot is rewritten. Dates use `en-GB` or `ko-KR`; stored ISO dates and the `Asia/Seoul` timezone are unchanged.

## Verification

Run from `frontend`:

```sh
npm run lint
npm run build
npm test
npm run test:e2e
```

`tests/i18n.test.js` checks catalog parity, variables, static translation references, fallback behavior, deferred messages, patient-data preservation and timezone consistency. `tests/browser/i18n.spec.js` exercises English defaults, both-way switching, signup/login, errors, unavailable storage, reload/new-page persistence, forms, conditional questionnaire stages, list filters, account records, read-only handoffs, download, loading/retry/session expiry and 360px/1440px layouts. Existing intake/account browser suites explicitly choose Korean as a regression baseline.

Missing translation keys fall back to English, then a generic message, never a visible key. In development they also produce a console warning and appear in the exported `missingKeys` set. Tests compare both catalogs and their interpolation variables. Screenshots are written to `frontend/test-results/screenshots/`.

Screen-reader speech output, real mobile devices and non-Chrome browsers require separate manual verification. No medical or clinical validation is claimed for either translation.

## Recorded results — 2026-09-17

- Final `npm run lint`, `npm run build`, `npm test`: passed (26 unit tests).
- Full Chrome browser suite: 17 passed, covering existing Korean journeys and new bilingual flows.
- After the final error-title and header-alignment refinements, the three affected bilingual auth/account scenarios were rerun and passed.
- 360px and 1440px: no horizontal overflow in the tested flows; screenshots visually reviewed. Language switching retained focus, inputs, route, filter, review status and byte-identical demo storage, with no additional demo-data writes.
- Keyboard flows and automated axe checks passed. Screen-reader speech, real mobile keyboards/devices and other browsers were not tested.

| View | English | 한국어 |
| --- | --- | --- |
| Mobile home | [360px](screenshots/i18n-360-en-home.png) | [360px](screenshots/i18n-360-ko-home.png) |
| Desktop home | [1440px](screenshots/i18n-1440-en-home.png) | [1440px](screenshots/i18n-1440-ko-home.png) |
| Mobile review | [360px](screenshots/i18n-360-en-review.png) | [360px](screenshots/i18n-360-ko-review.png) |
| Desktop review | [1440px](screenshots/i18n-1440-en-review.png) | [1440px](screenshots/i18n-1440-ko-review.png) |
