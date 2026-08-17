# NextRole

A personalised job recommendation API with a Next.js workspace and Flutter Android client. CM3070 final project, Template 7.2 (NextTrack), adapted to job recommendations.

## Scope

The assessed slice covers explicit search preferences, optional candidate text, exact-title and semantic retrieval, deterministic deduplication, explainable results, saved jobs on the client, and reproducible evaluation. Accounts, payments, automated applications, messaging and recruiter tools are outside this scope.

## Run locally

Requirements: Python 3.11, Go 1.23+, Node.js 20.9+, and Flutter 3.47.1 / Dart 3.13.1 for the Android client. Verified on Apple Silicon macOS. Dependency lockfiles are included. Initial setup downloads the pinned multilingual model (approximately 470 MB); inference then runs locally on CPU. No API keys or private services are needed.

From this directory:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/embeddings.py --corpus data/demo.json
npm --prefix web ci
npm --prefix web run build
.venv/bin/python scripts/dev.py --dataset demo
```

Open **http://127.0.0.1:3000**. The demo dataset is explicitly fictional and contains 22 vacancies, including English and Arabic fixtures. Ctrl-C stops services launched by the runner. It refuses occupied ports instead of terminating an existing application.

To import actual public vacancies:

```bash
.venv/bin/python scripts/prepare_data.py --live
.venv/bin/python scripts/embeddings.py --corpus data/live.json
.venv/bin/python scripts/dev.py --dataset live
```

Stop a running demo before changing the dataset. Live data is a timestamped snapshot, not a continuous feed. The importer records source failures and response hashes. Current external APIs may return different vacancies on a later date. Source links are preserved for attribution; live snapshots and derived vectors are excluded from source control.

## Android

Start an Android emulator and the API above, then:

```bash
cd mobile
flutter pub get
flutter run -d emulator-5554
```

The emulator calls the host through `10.0.2.2:8090`. For a USB device, use `adb -s DEVICE_SERIAL reverse tcp:8090 tcp:8090` and `flutter run -d DEVICE_SERIAL --dart-define=NEXTROLE_API=http://127.0.0.1:8090`. The debug manifest permits HTTP only on these local development addresses. Release deployment needs an HTTPS API and an appropriate `NEXTROLE_API` build value. `flutter build apk --debug` produces the local demonstrator APK.

## Verification and evaluation

```bash
.venv/bin/python scripts/verify.py
cd web
npx playwright install chromium
npm test
```

Browser tests use the running public snapshot API through the Next.js server. The pagination test expects multiple results for Engineer. They cover search, details, persisted saves, error and empty states, pagination consistency, automated accessibility, narrow layout, Arabic direction and Escape dismissal.

To reproduce the comparative evaluation, also start the fixture API in a separate terminal:

```bash
cd api
NEXTROLE_DATA=../data/demo_embeddings.json NEXTROLE_ADDR=127.0.0.1:8092 go run .
```

Then, from the project root:

```bash
.venv/bin/python scripts/evaluate.py
.venv/bin/python scripts/figures.py
```

This records real local latency measurements and a **synthetic retrieval regression**, not a completed human relevance study. Semantic and hybrid ranking tied on the current held-out fixture queries. The deployment threshold remains 0.40; the 0.25 development-fixture optimum is not asserted to be suitable for real users. Blank human judgement rows are exported separately. Run `scripts/score_judgements.py` only with genuinely completed assessor data. Do not overwrite completed assessments when regenerating the pool.

## Structure

- `api/`: Go REST contract, hybrid ranking, filtering, deterministic deduplication and tests.
- `web/`: responsive Next.js client, local saved jobs, English/Arabic layout and browser tests.
- `mobile/`: Flutter Android client and widget tests.
- `scripts/`: public data import, pinned local encoder, verification, evaluation and Android smoke test.
- `data/demo.json`: openly inspectable synthetic fixtures; generated live data/model outputs remain local.
- `evidence/`: measured results and actual runtime screenshots.

## Boundaries

The API does not persist candidate text or log search content. Saved vacancy records stay on the client. The current encoder truncates long text at 128 tokens. Skills explanations use a small explicit vocabulary and literal mention matching. Country/work-type metadata can be unknown. Exact title matches deliberately take precedence in hybrid mode even when candidate context differs. Local inference is serial and not proven at production load.

English and Arabic layout and phrase boundaries have automated coverage; this is not a claim of fully translated content, full Arabic linguistic analysis, screen-reader certification or fairness. External vacancies retain their original language.

The report must accurately acknowledge reused work and assistance. Human evaluation, public repository publication and the student's own video narration are distinct submission steps; no grade or improvement in real candidate outcomes is assumed.
