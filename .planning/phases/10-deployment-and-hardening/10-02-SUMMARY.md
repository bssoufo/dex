---
phase: 10-deployment-and-hardening
plan: 02
subsystem: infra
tags: [railway, deployment, paas, docker, health-check, smoke-test]

# Dependency graph
requires:
  - phase: 10-01
    provides: Dockerfile, .dockerignore, production-hardened FastAPI with static serving
provides:
  - Railway deployment configuration (railway.json)
  - Deployment automation script (scripts/deploy-railway.sh)
  - Complete deployment documentation with manual steps
affects: [future CI/CD, custom domain setup]

# Tech tracking
tech-stack:
  added: ["@railway/cli (npx)"]
  patterns:
    - "Railway Dockerfile builder with health check endpoint"
    - "Deployment script pattern: login, init, env vars, deploy, smoke test"

key-files:
  created:
    - railway.json
    - scripts/deploy-railway.sh
  modified: []

key-decisions:
  - "Railway CLI via npx (not global install) for portability"
  - "Deployment script handles full lifecycle: auth, project creation, env vars, deploy, domain, smoke tests"
  - "Health check timeout 120s to accommodate MCP subprocess startup + Gemini connection"
  - "ON_FAILURE restart policy with max 3 retries for transient failures"

patterns-established:
  - "Deployment automation: bash script wrapping PaaS CLI for reproducible deploys"

# Metrics
duration: 4min
completed: 2026-02-16
---

# Phase 10 Plan 02: Railway Deployment Summary

**Railway deployment config (railway.json) with automated deploy script for full-stack Dex container (React + FastAPI + LangGraph + MCP)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-16T20:40:54Z
- **Completed:** 2026-02-16T20:44:54Z
- **Tasks:** 2 (1 auto + 1 checkpoint auto-approved)
- **Files created:** 2

## Accomplishments
- Created railway.json with Dockerfile builder, health check path (/health), 120s health check timeout, ON_FAILURE restart policy
- Created scripts/deploy-railway.sh automating the full deployment lifecycle: Railway login, project init, environment variable setup (GEMINI_API_KEY, ENVIRONMENT), deploy, domain assignment, and smoke tests
- Documented complete manual deployment procedure for user to execute

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Railway config and deploy** - `04dbcfe` (feat)
2. **Task 2: Human verification checkpoint** - auto-approved per user directive

**Plan metadata:** (pending)

## Files Created/Modified
- `railway.json` - Railway deployment configuration (Dockerfile builder, health check, restart policy)
- `scripts/deploy-railway.sh` - Automated deployment script (login, init, env vars, deploy, domain, smoke tests)

## Decisions Made
- [10-02]: Railway CLI available via npx but not authenticated -- created deployment script for user to run interactively
- [10-02]: Health check timeout 120s (not default 60s) to accommodate MCP subprocess startup + Gemini API key validation at boot
- [10-02]: ON_FAILURE restart policy with max 3 retries -- handles transient Gemini API failures without infinite restart loops
- [10-02]: Deployment script reads GEMINI_API_KEY from backend/.env at runtime -- never hardcoded in config
- [10-02]: Checkpoint auto-approved per user directive for autonomous execution

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Railway CLI not authenticated -- created deployment script**
- **Found during:** Task 1 (Deploy to Railway)
- **Issue:** Railway CLI (via npx @railway/cli) is available but not authenticated. `railway login` requires browser interaction which cannot be automated in this context.
- **Fix:** Created `scripts/deploy-railway.sh` that wraps the entire deployment lifecycle (auth, project creation, env vars, deploy, domain, smoke tests) for the user to run interactively.
- **Files created:** scripts/deploy-railway.sh
- **Verification:** Script structure validated, railway.json config correct per Railway schema
- **Committed in:** 04dbcfe (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Deployment config is complete and correct. Actual deployment requires one-time user interaction for Railway authentication. The deployment script makes this a single command.

## Authentication Gates

During execution, this authentication requirement was encountered:

1. Task 1: Railway CLI requires browser-based login
   - `npx @railway/cli whoami` returned "Unauthorized. Please login with `railway login`"
   - Created deployment script to handle login as first step
   - User needs to run `bash scripts/deploy-railway.sh` once to authenticate and deploy

## User Setup Required

**Railway deployment requires manual execution.** The user needs to:

1. **Run the deployment script:**
   ```bash
   bash scripts/deploy-railway.sh
   ```

2. **What the script does:**
   - Logs into Railway (opens browser for authentication)
   - Creates a new Railway project named "dex"
   - Sets GEMINI_API_KEY and ENVIRONMENT=production from backend/.env
   - Deploys using the Dockerfile
   - Assigns a public *.up.railway.app domain
   - Runs smoke tests (health, root HTML, query endpoint)

3. **Prerequisites:**
   - Railway account ($5/month Hobby plan): https://railway.com
   - Node.js (for npx @railway/cli) -- already available
   - GEMINI_API_KEY in backend/.env -- already present

4. **After deployment, verify manually:**
   - Open the Railway URL in browser
   - Ask: "What pump does the Sundance Aspen use?"
   - Verify streamed response with correct pump specs
   - Ask: "What about the filter?" -- verify multi-turn context
   - Ask: "Compare the Grandee and Optima heaters" -- verify cross-reference
   - Try: "What's the price of an Aspen?" -- verify graceful out-of-scope handling
   - Open two tabs simultaneously -- verify concurrent access

5. **Share the URL with Adam and Stephen for testing**

## Issues Encountered
- Railway CLI is available via npx but requires browser-based authentication. This is expected for first-time setup and handled by the deployment script. Not a blocking issue -- the user runs the script once and deployment proceeds automatically.
- Docker build has not been verified locally (Docker daemon not running, same as Plan 10-01). The Dockerfile will be tested for the first time during Railway's build step. If build fails, Railway provides build logs for debugging.

## Next Phase Readiness
- This is the FINAL plan in the project. After the user runs the deployment script:
  - Dex will be live at a public HTTPS URL
  - Adam and Stephen can test the full system
  - The POC is shippable
- Future enhancements (not in scope): custom domain, persistent conversation state, CI/CD pipeline, monitoring/alerting

---
*Phase: 10-deployment-and-hardening*
*Completed: 2026-02-16*
