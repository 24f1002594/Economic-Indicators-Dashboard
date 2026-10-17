# Production deployment

The frontend and API are deliberately packaged as separate deployables. Deploy
them to separate HTTPS origins (or separate hosting services) and use a managed
PostgreSQL instance whose networking policy permits only the API service.

## API service

Build `backend/Dockerfile` and deploy it as the only service allowed to use the
database connection string. Set the following production values in the host's
secret store, never in the repository:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql://<user>:<password>@<private-db-host>:5432/economic_dashboard?sslmode=require
JWT_SECRET_KEY=<random-secret-of-at-least-32-characters>
CORS_ORIGINS=https://<frontend-host>
COLLECTOR_ENABLED=true
COLLECTOR_RUN_ON_STARTUP=true
```

The container applies the SQL migrations before it starts Uvicorn. For a
multi-replica deployment, run `python -m app.migrate` once as a release job
instead, then start the API replicas. Route HTTPS traffic to port `8000` and
configure `/health` as the health check. Publish `/docs` only if the evaluation
panel needs the interactive API documentation.

## Frontend service

Build `frontend/Dockerfile` independently, passing the public API origin at
build time:

```bash
docker build --build-arg VITE_API_BASE_URL=https://<api-host>/api/v1 -t economic-dashboard-web frontend
```

Deploy that image as a static HTTPS website and route it to port `8080`. It has
no database credentials and never calls NSE or the other upstream data sources.

## Database network boundary

Use the hosting provider's private network/private endpoint for PostgreSQL.
Disable public database access and allow inbound PostgreSQL traffic only from
the API service's private identity or security group. Do not place a public HTTP
reverse proxy in front of PostgreSQL. Back up the database and rotate the JWT
secret through the host's secret manager.

## Release verification

1. Confirm `https://<api-host>/health` reports `status: "ok"` and `database: "ok"`.
2. Create the panel account with `python -m app.create_user` and share it only
   through the evaluation channel.
3. Sign in on `https://<frontend-host>`, check each source/as-of label, then
   verify stale and unavailable behavior by inspecting the authenticated
   `/api/v1/sources` response.
4. Record the deployed frontend, API/docs, health-check, and portfolio URLs in
   the submission checklist after the hosting account has assigned them.
