## Completed
- switch to the non-reasoning model -> DONE
- release app on google console -> DONE

## Search
- use [Tavily](https://www.tavily.com/) for search -> TBD

## Security & Hardening
- add security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Content-Security-Policy) -> TBD
- add API rate limiting (per-user / per-IP) beyond daily billing quota -> TBD
- add request timeout on agent execution (prevent infinite hang) -> TBD
- review CORS configuration and document the expected behavior -> TBD

## Observability & Monitoring
- add structured JSON logging for log aggregation -> TBD
- integrate error tracking (e.g. Sentry) -> TBD
- add uptime / health monitoring (e.g. Better Uptime, UptimeRobot) -> TBD
- add TLS cert renewal monitoring -> TBD

## Database & Data
- set up Alembic for schema migrations -> TBD
- define a session data retention policy and implement cleanup -> TBD
- set up automated Postgres backups -> TBD

## CI/CD
- add GitHub Actions workflow: run tests on every PR -> TBD
- add GitHub Actions workflow: build and push Docker image on merge to main -> TBD

## Frontend / UX
- add a timeout and user-facing message for long-running assessments -> TBD
- add pagination to session history list -> TBD

## Documentation
- write a deployment / operations runbook (credential rotation, DB recovery, scaling) -> TBD
- clean up README TODOs -> TBD
