# Plan: Install Dokploy and Migrate from Custom Traefik to Dokploy's Traefik

## Context

The project currently uses a custom Traefik reverse proxy defined in `docker-compose.yml` (HTTP) and `docker-compose.prod.yml` (HTTPS/Let's Encrypt overlay). The goal is to install Dokploy on the VPS, deploy the app as a Docker Compose project through Dokploy, and let **Dokploy's built-in Traefik** handle routing, TLS, and certificate management — replacing the custom Traefik entirely. The VPS will host multiple apps, so Dokploy's shared Traefik must be properly configured.

---

## Phase 1: Install Dokploy on VPS

1. **SSH into your VPS** and run the official Dokploy install script:
   ```bash
   curl -sSL https://dokploy.com/install.sh | sh
   ```
2. **Access the Dokploy dashboard** at `http://<VPS_IP>:3000` and create your admin account.
3. **Configure your domain** — in Dokploy Settings > Server, set the server IP/domain. This is used for Dokploy's own dashboard and as the base for Traefik routing.
4. **(Optional) Secure the Dokploy dashboard** — In Settings > Server, assign a domain (e.g., `dokploy.goodbyeplanet.dev`) and enable HTTPS via Dokploy's built-in Let's Encrypt integration.

> Dokploy automatically installs and manages its own Traefik instance. It listens on ports **80** and **443** by default. No manual Traefik setup is needed.

---

## Phase 2: Stop and Remove the Existing Custom Traefik

Before deploying through Dokploy, ensure there are no port conflicts on 80/443.

1. **SSH into the VPS** and stop any running compose stack:
   ```bash
   cd /path/to/eu-ai-act-compliance-agent
   docker compose -f docker-compose.yml -f docker-compose.prod.yml down
   ```
2. **Verify ports 80/443 are free** (Dokploy's Traefik needs them):
   ```bash
   ss -tlnp | grep -E ':80|:443'
   ```
   Only Dokploy's Traefik (container `dokploy-traefik`) should be listening.

---

## Phase 3: Create a Dokploy-Compatible Docker Compose File

Create a new file `docker-compose.dokploy.yml` that:
- **Removes** the `traefik` service entirely
- **Removes** the `docker-compose.prod.yml` overlay (Dokploy's Traefik handles TLS)
- **Connects** services to Dokploy's external network (`dokploy-network`)
- **Keeps** Traefik labels on `backend` and `frontend` for Dokploy's Traefik to discover
- **Updates** Traefik labels to use `websecure` entrypoint + `letsencrypt` certresolver (Dokploy's naming)

### File: `docker-compose.dokploy.yml`

```yaml
services:
  db:
    image: postgres:15-alpine
    container_name: agent-memory-db
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-agent_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-agent_password}
      POSTGRES_DB: ${POSTGRES_DB:-agent_sessions}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-agent_user} -d ${POSTGRES_DB:-agent_sessions}"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - ai_act_network

  backend:
    build:
      context: .
      dockerfile: dockerfiles/Dockerfile.api
    container_name: compliance-api
    restart: unless-stopped
    env_file:
      - .env.prod
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-agent_user}:${POSTGRES_PASSWORD:-agent_password}@db:5432/${POSTGRES_DB:-agent_sessions}
      STREAMLIT_APP_URL: ${STREAMLIT_APP_URL:-https://eu-ai-audit.com/app}
    expose:
      - "8000"
    depends_on:
      db:
        condition: service_healthy
    labels:
      traefik.enable: "true"
      # API routes
      traefik.http.routers.backend-api.rule: ${TRAEFIK_BACKEND_RULE}
      traefik.http.routers.backend-api.entrypoints: websecure
      traefik.http.routers.backend-api.tls: "true"
      traefik.http.routers.backend-api.tls.certresolver: letsencrypt
      traefik.http.routers.backend-api.priority: "100"
      traefik.http.routers.backend-api.middlewares: backend-strip-api,compress
      traefik.http.routers.backend-api.service: backend
      # Landing page routes
      traefik.http.routers.backend-landing.rule: ${TRAEFIK_LANDING_RULE}
      traefik.http.routers.backend-landing.entrypoints: websecure
      traefik.http.routers.backend-landing.tls: "true"
      traefik.http.routers.backend-landing.tls.certresolver: letsencrypt
      traefik.http.routers.backend-landing.priority: "200"
      traefik.http.routers.backend-landing.middlewares: compress
      traefik.http.routers.backend-landing.service: backend
      # Middlewares
      traefik.http.middlewares.backend-strip-api.stripprefix.prefixes: /api
      traefik.http.middlewares.compress.compress: "true"
      traefik.http.services.backend.loadbalancer.server.port: "8000"
    networks:
      - ai_act_network
      - dokploy-network

  frontend:
    build:
      context: .
      dockerfile: dockerfiles/Dockerfile.ui
    container_name: assessment-ui
    restart: unless-stopped
    env_file:
      - .env.prod
    environment:
      API_URL: http://backend:8000
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-agent_user}:${POSTGRES_PASSWORD:-agent_password}@db:5432/${POSTGRES_DB:-agent_sessions}
      STREAMLIT_SERVER_BASE_URL_PATH: /app
    expose:
      - "8501"
    depends_on:
      - backend
    labels:
      traefik.enable: "true"
      traefik.http.routers.frontend.rule: ${TRAEFIK_FRONTEND_RULE}
      traefik.http.routers.frontend.entrypoints: websecure
      traefik.http.routers.frontend.tls: "true"
      traefik.http.routers.frontend.tls.certresolver: letsencrypt
      traefik.http.routers.frontend.priority: "50"
      traefik.http.routers.frontend.middlewares: compress
      traefik.http.services.frontend.loadbalancer.server.port: "8501"
    networks:
      - ai_act_network
      - dokploy-network

networks:
  ai_act_network:
    driver: bridge
  dokploy-network:
    external: true

volumes:
  postgres_data:
```

### Key differences from the current setup

| Change | Why |
|---|---|
| No `traefik` service | Dokploy provides its own Traefik |
| No `docker-compose.prod.yml` overlay | TLS/Let's Encrypt handled by Dokploy's Traefik certresolver |
| `dokploy-network` (external) on backend + frontend | Dokploy's Traefik can only route to containers on its network |
| `db` stays on internal network only | No need to expose Postgres to Dokploy's Traefik |
| `TRAEFIK_*_RULE` + `STREAMLIT_APP_URL` env vars | Reuses the same env var pattern from the original compose files |
| `env_file: .env.prod` hardcoded | Dokploy manages env vars; simplifies config |
| Idle/read timeout labels removed | These are set globally in Dokploy's Traefik config (see Phase 5) |

---

## Phase 4: Deploy Through Dokploy

1. **Push your repo** (with the new `docker-compose.dokploy.yml`) to GitHub/GitLab.
2. In the Dokploy dashboard:
   - Go to **Projects** > **Create Project** (e.g., "EU AI Act Compliance Agent").
   - Click **Create Service** > **Compose**.
   - Connect your Git repository and select the branch.
   - Set the **Compose File Path** to `docker-compose.dokploy.yml`.
3. **Configure environment variables** in Dokploy's Environment tab:
   ```
   # Traefik routing rules
   TRAEFIK_FRONTEND_RULE=Host(`eu-ai-audit.com`,`www.eu-ai-audit.com`) && PathPrefix(`/app`)
   TRAEFIK_BACKEND_RULE=Host(`eu-ai-audit.com`,`www.eu-ai-audit.com`) && PathPrefix(`/api`)
   TRAEFIK_LANDING_RULE=Host(`eu-ai-audit.com`,`www.eu-ai-audit.com`) && (Path(`/`) || Path(`/about-eu-ai-act`) || Path(`/login`) || Path(`/favicon.ico`) || PathPrefix(`/static`))
   STREAMLIT_APP_URL=https://eu-ai-audit.com/app

   # Database
   POSTGRES_USER=<your_user>
   POSTGRES_PASSWORD=<your_password>
   POSTGRES_DB=agent_sessions

   # API keys
   ANTHROPIC_API_KEY=<your_key>
   SERPER_API_KEY=<your_key>

   # Auth
   GOOGLE_OIDC_AUDIENCE=<your_client_id>
   GOOGLE_OIDC_ISSUER=https://accounts.google.com

   # App config
   AI_MODEL=anthropic/claude-sonnet-4-6
   BILLING_ENABLED=true
   DAILY_FREE_CREDITS=20
   ```
4. **Set the `.env.prod` file** — In Dokploy, you can either:
   - Use Dokploy's environment variable injection (preferred — no `.env.prod` file needed, Dokploy passes vars to compose), OR
   - Upload `.env.prod` as a config file in Dokploy's "Advanced" > "Volumes" section.

   > **Note:** If using Dokploy's env injection, remove `env_file: .env.prod` from the compose file, and rely purely on Dokploy's environment config + the `environment:` block.

5. **Deploy** — Click "Deploy" in Dokploy. It will build the images, create containers, and connect them to Dokploy's Traefik.

---

## Phase 5: Configure Dokploy's Traefik for Long Timeouts

The current setup has 3600s idle/read timeouts for SSE streaming. Dokploy's Traefik needs the same config.

In the Dokploy dashboard:
1. Go to **Settings** > **Server** > **Traefik Config** (or the Traefik tab).
2. Add these to the entrypoints configuration (Dokploy exposes a Traefik config editor):
   ```yaml
   entryPoints:
     websecure:
       transport:
         respondingTimeouts:
           idleTimeout: 3600s
           readTimeout: 3600s
   ```
   Alternatively, Dokploy may expose this via its Traefik TOML/YAML file — edit it there.

---

## Phase 6: DNS Setup

1. Point your domain's DNS A records to the VPS IP:
   ```
   eu-ai-audit.com      →  A  →  <VPS_IP>
   www.eu-ai-audit.com  →  A  →  <VPS_IP>
   ```
2. Wait for DNS propagation (or set a low TTL beforehand).
3. Dokploy's Traefik will automatically request Let's Encrypt certificates for both `eu-ai-audit.com` and `www.eu-ai-audit.com` on the first HTTPS request.

---

## Phase 7: Verify

1. **Check Dokploy dashboard** — all 3 services (db, backend, frontend) should show "Running".
2. **Test endpoints**:
   - `https://eu-ai-audit.com/` — should serve the landing page
   - `https://eu-ai-audit.com/app` — should serve the Streamlit UI
   - `https://eu-ai-audit.com/api/health` — should return API health check
3. **Check TLS** — certificate should be valid Let's Encrypt cert for your domain.
4. **Check SSE streaming** — run a compliance assessment and verify the streaming response doesn't timeout.
5. **Check logs** in Dokploy dashboard if anything fails.

---

## Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `docker-compose.dokploy.yml` | **Create** | Dokploy-compatible compose file (no Traefik service, dokploy-network) |
| `docker-compose.yml` | **No change** | Keep for local development |
| `docker-compose.prod.yml` | **No change** | Keep as reference / fallback for non-Dokploy deploys |
