# Doctor monthly calendar

The `/doctor` welcome area is now an appointment calendar. The existing hash router,
header, daily patient queue, intake detail route, preparation notes, review actions,
and unsaved-change guard remain in use. No dependencies were added.

## Layout and interaction

- At 1400px and above, the calendar and top-aligned inspector sit beside the patient
  queue. Below 1400px the inspector follows the calendar. Below 701px the calendar
  workspace precedes the existing queue so the primary task is immediately reachable.
- At 1100px and below, cells show the day and appointment count. The selected day's
  full list provides comfortably sized event buttons. On wider screens two events
  and a “+N more” button appear in each cell; more focuses the complete day list.
- Native table semantics, header cells and buttons provide keyboard navigation with
  Tab and activation with Enter/Space. This is deliberately not an ARIA grid.
- Selection and focus have distinct styles. Mobile event selection focuses and
  scrolls to the inspector; desktop preserves event focus and offers an explicit
  move-to-details button. Reduced-motion preferences disable transitions.

## Dates and state

- Service timezone remains `Asia/Seoul`; existing English default and language
  preference storage remain unchanged. Patient-entered content is never translated.
- Weeks start Monday (new documented policy). The grid contains complete weeks,
  including adjacent-month dates. `listRange(scope, start, end)` uses inclusive Seoul
  civil dates matching this exact visible range. Appointments are sorted by instant.
- UTC arithmetic in `calendar.js` operates only on civil-date calendar values;
  appointment placement uses the existing timezone-aware `dayKey`.
- `completed` and `cancelled` are explicit stored statuses. A past scheduled visit
  is labelled “Past appointment · completion unconfirmed”. Review is independent.
- Calendar month, selected date and appointment ID live in the authenticated Doctor
  component. They survive intake-detail navigation and browser Back within that
  mounted doctor session. Reload or leaving the doctor area resets this UI state.
  Authentication epoch changes, logout and expiry unmount it and clear selections.
- Moving months clears event selection only if its appointment date leaves the new
  displayed range. Today returns to the current month/date and clears selection.
  Same-range reload retains a still-accessible ID; missing IDs clear the inspector.
- Request cleanup ignores late responses. Results are additionally keyed by range,
  appointment ID and service revision to prevent stale patient information flashing.
  Service authorization is rechecked after its mock delay.

## Data and mock boundary

The queue and calendar use the same doctor service and existing appointment store.
Daily `list` delegates to `listRange`; no calendar-specific database exists. Existing
patient-source ingestion now synchronizes appointment metadata/status and removes
source appointments that were deleted. Only handed-off snapshots are ingested;
patient drafts and completed-but-unsubmitted answers remain unavailable to doctors.
Service revisions refresh both the calendar and inspector after notes/reviews or
new submissions. Existing periodic sync imports patient-source updates.

This remains a browser/session-storage demo. Doctor scope checks and assignment
filtering are mock safeguards, **not server authorization**. A production API must
perform server-side access control and provide the same range/detail contracts.
There are no generated diagnoses, prescriptions, EMR records or risk scores.
Hospital/department/clinician appear only when the appointment supplies them; visit
completion is unconfirmed unless an explicit completed status is stored. Existing
intake detail is the place to read preparation notes and versioned review history.

Monthly and detail loading/failure/retry, empty month/day, unavailable appointment,
no submission and existing session-expiry routing are supported. Calendar demo
controls can fail the next range request, delay the next request or expire the
session. The inspector can fail its next detail reload. Retry retains the month.

## Verification

- `npm test`: calendar/date boundaries, leap year, Seoul midnight/year rollover,
  ordering, scope, snapshot exclusion, failures, expired requests and source updates.
- `npm run lint` and `npm run build`.
- `npm run test:e2e`: browser interactions and existing patient/doctor regression suite.
  Calendar coverage includes rapid requests, retry, deleted-selection clearing,
  same-range version refresh, language preservation, detail round trip, keyboard,
  360/900/1440px overflow checks, axe and screenshots in both languages.
- 200% desktop layout is checked at the equivalent 720 CSS-pixel viewport
  (1440 / 2). This is not native browser zoom or a manual screen-reader audit. Actual mobile devices, Safari/Firefox,
  production API authorization and a real clinical data integration are not tested.

Screenshots are stored in `docs/screenshots/calendar/` after successful browser runs.

Final result (2026-09-22): 54 unit tests passed; lint, production build and
`git diff --check` passed. The full browser run passed all 38 pre-existing tests.
After correcting the zoom simulation and final calendar refinements, all 7 calendar
browser tests passed (45 distinct browser scenarios across these runs). Both
languages passed axe at 360/900/1440px. Nine calendar screenshots were retained.
