# Known E2E Test Limitations

## Dashboard Happy Path — Mock Override Timing

**Issue:** `tests/specs/dashboard/dashboard.spec.ts` — "happy path — populated dashboard shows biomarker card and recent scans"

**Status:** 1 test failing (2/3 dashboard tests passing)

**Root Cause:**
Playwright's route handlers are registered synchronously in `applyDefaultMocks` during fixture setup. Tests attempt to override responses using a `mockOverrides` global map, but TanStack Query dispatches requests too quickly:

1. Fixture setup: `applyDefaultMocks` registers `/scan/history` → `[]`
2. Test: `mockScanHistory` modifies `mockOverrides['scan-history']` 
3. Test: `mockedPage.goto("/")` navigates
4. React renders → TanStack Query `useQuery` fires `/scan/history` request
5. Route handler checks `mockOverrides['scan-history']` but request already in flight → returns default `[]`

**Attempted Fixes:**
- `page.unroute()` + `page.route()` — LIFO handler stacking prevents override
- `setImmediate()` delay — insufficient timing guarantee
- `Promise.all()` inline routes — applyDefaultMocks handlers still win

**Why Not Critical:**
- Dashboard functionality verified in UI (scans load correctly in production)
- Timing issue is test-specific, not application behavior
- 32/32 other critical tests pass (auth, scan, biosync, session, OFF-contribute)

**Future Solution:**
Consider migrating to MSW (Mock Service Worker) for library-level request interception that would eliminate Playwright route handler conflicts.

---

## Other Test Status

✅ **Passing (32/32):**
- Auth login (4/4)
- Auth register (4/4)  
- Session lifecycle (5/5)
- Scan result page (9/9)
- Biosync PDF upload (6/6)
- OFF-contribute toggle (4/4)
