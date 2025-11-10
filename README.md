# integrated-mods-patcher — Docker setup

This repository contains a Flask-based scraper served by Waitress. The included `Dockerfile` is a multi-stage build that:

- Builds Python wheels in a `builder` stage (reduces runtime image size and isolates build tools).
- Uses a slim runtime image and installs only the runtime extraction tools needed by the app (unzip, p7zip-full, unrar-free).

Files added:
- `Dockerfile` — Multi-stage build (builder -> runtime).
- `.dockerignore` — Excludes venv, temp directories, and other unnecessary files from the build context.

Quick build & run

Build the image:

```pwsh
# from repository root
docker build -t integrated-mods-patcher:latest .
```

Run the container (map port 5000):

```pwsh
docker run -p 5000:5000 \
  -e NOCO_BASE_URL="https://..." \
  -e NOCO_WW="<noco-table-id>" \
  -e NOCO_BEARER="<token>" \
  integrated-mods-patcher:latest
```

Notes and environment variables

- The Flask app expects certain env vars (you can set them via `-e` or an env file):
  - `NOCO_BASE_URL` (optional override, by default in `app.py`) 
  - `NOCO_WW`, `NOCO_ZZ`, `NOCO_INI`, `NOCO_BEARER`
  - `GAME` (default `WW`)
  - `DEBUG_MODE` (set `True`/`False`)
  - `SAMPLE_LIMIT`

- Extraction tools included: `unzip`, `p7zip-full`, `unrar-free`.
  - `unrar-free` may not support all RAR formats; your code contains logic to attempt building a more capable unrar if needed, but building from source inside the container is not performed by the Dockerfile (keeps image smaller and build deterministic).

Security

- Avoid baking secrets into Docker images. Use runtime env vars or Docker secrets for production.

If you'd like, I can:
- Add a `docker-compose.yml` with env-file support.
- Add a healthcheck to the Dockerfile.
- Attempt to install the official `unrar` binary from RARLab during build (larger, may require non-free sources).
