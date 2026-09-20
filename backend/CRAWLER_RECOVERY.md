# Crawler recovery and optional Selenium inspection

This change repairs confirmed code/configuration defects. It does not establish
that every government website is accessible from the deployment network.

## What changed

- Stored `crawl_policy` settings now reach the adapters. Page and document limits
  apply to production runs as well as diagnostics; paused sources do not run.
- Known obsolete endpoints are corrected when loading configurations, without
  rewriting MongoDB records or replacing custom seeds.
- Access rejection stops further requests in that run. HTTP errors and blocked
  or empty listings produce a failed run with the reason, HTTP status where
  available, and transport exception. Successfully saved documents remain counted
  if a later request fails. There is no automatic retry of a failed crawl run.
- Each production crawl has a default 120-second asynchronous work budget,
  configurable with `CRAWLER_RUN_TIMEOUT_SECONDS`. Cleanup and final database
  recording each have a separate five-second budget. Synchronous PDF parsing
  cannot be interrupted by an asyncio deadline. A database outage can still
  prevent recording the terminal status.
- Failed runs invalidate their conditional-request cache so an explicit later
  retry does not silently skip the failed work through a 304 listing response.
- Primary PDFs use PDF storage/provenance and reuse an already fetched matching
  attachment. Failed/empty extraction stays in `manual_review_required`.
- PIB can parse RSS listings when configured explicitly. RSS descriptions are
  discovery metadata, not full documents. Article retrieval is still required.

## Reviewed endpoint corrections

| Source | Effective endpoint | Verification and limits |
| --- | --- | --- |
| DoPT | `https://dopt.gov.in/` | Official homepage loaded; direct PDF links observed. This is recent homepage coverage, not the entire archive. |
| DoPT document hosts | `doptcirculars.nic.in`, `documents.doptcirculars.nic.in` | Linked by the [official homepage](https://dopt.gov.in/); added to explicit allowlists. |
| India Gazette | `https://egazette.gov.in/` | Removes the fabricated `(S(a))` session and hardcoded year directory. No claim that its form parser is complete. |
| Karnataka Gazette | `https://erajyapatra.karnataka.gov.in/` | [Official homepage](https://erajyapatra.karnataka.gov.in/) observed with current entries and session negotiation. Form-only download controls need verified interaction logic. |
| Karnataka IT-BT | `https://eitbt.karnataka.gov.in/it/public/policy5/en` | [Official policy page](https://eitbt.karnataka.gov.in/it/public/policy5/en) indexed. Replaces known obsolete seeds with limited policy coverage, not a general notifications listing. |

The corrected Gazette and IT-BT adapters use certificate verification. Existing
DPAR/Finance and robots-client TLS exceptions were not changed in this patch.

## Evidence from this editing session

- Offline regression suite: **33 tests passed**. HTTP transports, database
  operations, and storage are mocked; these tests do not prove live availability.
- DoPT homepage: HTTP **200**, **136,614 bytes**, **22** direct PDF candidates.
- First DoPT PDF, on `documents.doptcirculars.nic.in`: HTTP **502**. Full extraction
  and database ingestion were not confirmed.
- PIB RSS, corrected Karnataka Gazette, and IT-BT listing attempts each reached
  the **20-second probe budget**. Each was attempted once; no network cause was
  inferred from a timeout.
- DPAR, Finance and DOE successes were reported by the user in the supplied
  report. They were not rerun against live sites in this session.
- Selenium's command validation, rejection handling, and deadline handling are
  tested without opening Chrome. Live browser/form execution remains unverified.
- No MongoDB ingestion, AWS deployment, external branch push, or PR was performed.

## Apply and validate once

The delivery ZIP includes an installer that tries the incremental patch after
the earlier diagnostics patch, or the full patch against remote base commit
`aa4e9981c5007c1f89c03c128759db7805e52979`.

From your repository root, after extracting the ZIP elsewhere:

```bash
python /path/to/crawler-recovery/apply_fix.py --repo .
python -m unittest discover -s backend/tests -q
```

Use the project's existing Python 3.11+ virtual environment and backend
requirements. The installer checks applicability before writing, never resets
files, and stops on conflicts. Do not apply both patch files separately.

Restart the backend after applying the patch. Existing stored source entries
receive the known endpoint and policy corrections when next loaded. The patch
does not create missing source registry entries; existing admin source creation
continues to apply.

## Optional Selenium inspection

Selenium is useful for rendering an interactive page and exposing form controls.
Use its [explicit waits](https://www.selenium.dev/documentation/webdriver/waits/)
to wait for page elements instead of indefinite sleeps. It cannot establish that
AWS will permit access, repair an incorrect hostname, or guarantee passage
through a WAF.

Run locally with Google Chrome installed:

```bash
cd backend
python -m pip install -r requirements-browser.txt
python inspect_gazette.py karnataka_egazette --timeout 45
```

For India Gazette, replace `karnataka_egazette` with `egazette`. This is an
opt-in inspector, not an automatic production fallback. It first checks the
ordinary HTTP/robots path. If that fails or is rejected, it records the failure
and stops before launching Chrome. It does not retry a 403 through a browser.

For an accessible page it saves rendered HTML, official links and visible form
control identifiers in `backend/data/browser-inspection/`. The JSON result has
`ingested: false`; a browser capture is not a successful ingestion. HTTP status
for the rendered page is unknown, not fabricated as 200. The wrapper terminates
the inspection process tree when its overall budget expires, including driver
startup. Chrome/driver installation is a prerequisite for a successful capture.

`--wait-selector` and up to three `--click-selector` options support selectors
verified from the actual page. No Gazette selectors or postback parameters have
been guessed. A source-specific form adapter still needs that evidence before
automatic clicking/downloading can be considered complete.

For a single optional PIB RSS test:

```bash
python test_crawlers.py pib --rss --timeout 45 --json
```

This changes only that diagnostic invocation. To select RSS for a production PIB
source, explicitly change its `seed_urls` through the existing source-management
API to `https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3` and include
`/RssMain.aspx` in its path configuration. Do not alternate endpoints repeatedly
after a rejection.

## Remaining operational path

Continue using the sources that have demonstrated successful extraction. For a
blocked source, use the existing pasted-text ingestion path with the actual
official source URL and review the extracted content. That manual path does not
claim an HTTP fetch occurred. Subsequent AI simplification/translation still
depends on the separately configured backend services, including AWS where used.

Only repeat a failed live check after a concrete change, such as a corrected
endpoint, verified parser fix, or a site/network administrator resolving access.
Retain the error evidence instead of repeatedly running the entire source list.
