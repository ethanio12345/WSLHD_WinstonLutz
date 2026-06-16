## Purpose

Define how the Streamlit application is deployed via Docker Compose with a Caddy reverse proxy. Includes volume mounts (read-only DICOM share, read-write output share, bind-mounted config/templates/assets), IP allowlist as the v1 auth mode, structured Caddyfile for escalation to HTTPS/basic-auth/OIDC, non-root container execution, and stdout logging.

## Requirements

### Requirement: Two-service Docker Compose layout

The system SHALL deploy via `docker-compose.yml` containing exactly two services:

- `streamlit`: builds from the project's `Dockerfile`, exposes port 8501 container-internally (NOT published to host), mounts the volumes specified in the volume requirements below
- `caddy`: uses the `caddy:2` image, publishes port 80 to the host, mounts the `Caddyfile` read-only, declares `depends_on: [streamlit]` so startup ordering is correct (Caddy will retry if Streamlit is not yet listening)

Both services SHALL use `restart: unless-stopped`.

#### Scenario: docker-compose up

- **WHEN** `docker compose up -d` is run on the host
- **THEN** both services start, and the app is reachable at `http://<host>:80/` via the Caddy reverse proxy

#### Scenario: Streamlit not published directly

- **WHEN** the `streamlit` service is inspected
- **THEN** port 8501 is NOT in the `ports` list (only `expose`) — direct access bypassing Caddy is impossible from outside the Docker network

### Requirement: Read-only DICOM share mount

The `streamlit` service SHALL mount the hospital DICOM share into the container at `/data` with the `:ro` (read-only) flag. The app SHALL NEVER write to `/data`.

#### Scenario: Mount is read-only

- **WHEN** the container attempts to write to `/data/LA2/WinstonLutz/test.txt`
- **THEN** the write fails with a read-only filesystem error (defence in depth — the app code never attempts this, but the mount prevents accidents)

### Requirement: Read-write output share mount

The `streamlit` service SHALL mount the hospital output share into the container at `/out` with read-write access. All xlsx/xltx writes SHALL target paths under `/out`.

#### Scenario: Output written to share

- **WHEN** Simple mode writes the paired xlsx/xltx
- **THEN** the files appear at `/out/<MACHINE>/WL/<MACHINE>_WL_<RUNFOLDER>/` on the host's output share, visible to the MyQA import process

### Requirement: Bind-mounted config, templates, and assets

The `streamlit` service SHALL bind-mount `machines.yaml`, the `templates/` directory, and the `assets/` directory from the host into the container, all read-only. Updates to any of these on the host SHALL take effect on container restart without requiring an image rebuild. Host-side files MUST be readable by the container's non-root UID (default `1000:1000`); deployment documentation SHALL describe the required `chown`/`chmod` for bind-mount sources.

#### Scenario: Template updated without rebuild

- **WHEN** the host edits `templates/winston_lutz.xltx` (e.g. adds a new metric cell) and restarts the container
- **THEN** the next analysis run uses the updated template — no `docker compose build` required

#### Scenario: Fry meme updated without rebuild

- **WHEN** the host replaces `/mnt/hospital/RT_Assets/fry_money.png` on the network share and restarts the container
- **THEN** the new meme renders in the UI

#### Scenario: Bind-mount file ownership

- **WHEN** the host bind-mounts a root-owned `machines.yaml` (mode 0600) into the container running as UID 1000
- **THEN** the app refuses to start with a clear permission error: "Cannot read /app/machines.yaml — ensure host file is readable by UID 1000"

### Requirement: Caddy reverse proxy with IP allowlist (v1 auth mode)

Caddy SHALL listen on port 80 and reverse-proxy to `streamlit:8501`. Access SHALL be restricted by an IP allowlist (configurable CIDR ranges in the Caddyfile, default: RFC1918 private ranges `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`). Requests from non-allowlisted IPs SHALL receive a 403 response.

#### Scenario: Allowlisted IP

- **WHEN** a browser at `10.x.x.x` requests `http://<host>/`
- **THEN** Caddy proxies the request to Streamlit and the app renders

#### Scenario: Non-allowlisted IP

- **WHEN** a browser at `8.8.8.8` requests `http://<host>/`
- **THEN** Caddy returns HTTP 403 with body "Forbidden"

### Requirement: Caddyfile structured for auth escalation

The Caddyfile SHALL include commented-out escalation blocks showing how to enable: (1) real TLS with hospital-provided certificates, (2) HTTP Basic Authentication, (3) OIDC via `forward_auth` to Authelia/Keycloak. Enabling any of these SHALL require only uncommenting and editing the relevant block — no rewrite of the baseline configuration.

#### Scenario: Basic auth enabled by ops team

- **WHEN** the ops team uncomments the `basic_auth` block in the Caddyfile, sets a bcrypt-hashed password, and restarts Caddy
- **THEN** browsers prompt for credentials before reaching Streamlit — no app code change, no Streamlit restart required

#### Scenario: Hospital TLS cert added

- **WHEN** the ops team uncomments the `real_cert` block, mounts hospital `.crt` and `.key` files, and restarts Caddy
- **THEN** the app is reachable over HTTPS with a valid cert — no app code change

### Requirement: Streamlit version pinning

The project's `pyproject.toml` SHALL pin `streamlit>=1.33` (required for `st.dialog` used by the Detection overlay tab). The version SHALL be locked in `uv.lock` for reproducible deployment.

#### Scenario: st.dialog available

- **WHEN** the Detection overlay tab is rendered and an image is clicked
- **THEN** `st.dialog` opens successfully (no `AttributeError`)

### Requirement: Pylinac version pinning

The project's `pyproject.toml` SHALL pin `pylinac>=3.45` (required for the axis-data handling behaviour described in the design's D6 cache key). The wrapper module `core/wl_runner.py` SHALL isolate all pylinac API calls so that future pylinac major versions require changes in only that module.

#### Scenario: Axis data handling matches design

- **WHEN** the wrapper calls `WinstonLutz(directory).analyze(...)` without `missing_axis_value`
- **THEN** pylinac raises if axis data cannot be determined (v3.45+ behaviour), and the wrapper surfaces this as a physicist-friendly error in Simple mode

### Requirement: Container runs as non-root

The `Dockerfile` SHALL create a non-root user (UID 1000, e.g. `appuser`) and run the Streamlit process as that user. The container SHALL NOT run as root.

#### Scenario: Process user

- **WHEN** `docker exec <container> ps -o user= -p 1` is run
- **THEN** the output is `appuser` (or equivalent non-root username), not `root`

### Requirement: Output directory existence and writability validated at startup

At startup, the app SHALL verify that `output.root` exists and is writable by writing and removing a probe file. If the probe fails, the app SHALL refuse to start with a clear error indicating the path and the permission/missing-mount cause.

#### Scenario: Output root missing

- **WHEN** `output.root = /out` but `/out` is not mounted in the container
- **THEN** the app refuses to start, logging "Output root /out does not exist — check the docker-compose volume mount"

#### Scenario: Output root read-only

- **WHEN** `output.root = /out` exists but the probe write fails (mount is `:ro` or filesystem is full)
- **THEN** the app refuses to start, logging "Output root /out is not writable — check mount options and disk space"

### Requirement: Logs to stdout for `docker logs`

The Streamlit application SHALL configure the `logging` module to write to stdout (the Docker convention) so logs are retrievable via `docker logs <container>`. SHALL NOT write logs to a file inside the container.

#### Scenario: Logs captured by docker logs

- **WHEN** a Simple mode analysis fails and `logging.exception(...)` is called
- **THEN** the traceback appears in `docker logs <container>` output
