# Single-instance hackathon deployment

Deployed 2026-09-20 to Ubuntu 24.04, instance `i-0d27ac4662acdacc7` in
`ap-south-1`, public IP `13.233.117.95`.

- Site: http://13.233.117.95/
- Readiness: http://13.233.117.95/api/health/ready
- Backend: `/home/ubuntu/simple-sarkari-/backend`
- Frontend build: `/var/www/janvaani`
- Reverse proxy: `/etc/caddy/Caddyfile`
- Services: `janvaani-api`, `janvaani-worker`, `caddy` (enabled at boot)
- IAM instance role: `janvaani-ec2-role`; no static AWS credentials deployed.

The API listens on loopback port 8000. Caddy serves the frontend and proxies
`/api/*` to it. Both use the same origin; the frontend uses its default `/api`.
The production `.env` is mode 600 and contains the authorized Atlas connection
and newly generated reviewer/JWT secrets. Never commit it.

## Access and checks

```sh
ssh -i /Users/ayushanand/Downloads/janvaani.pem ubuntu@13.233.117.95
sudo systemctl status janvaani-api janvaani-worker caddy
journalctl -u janvaani-api -n 50 --no-pager
journalctl -u janvaani-worker -n 50 --no-pager
curl --fail http://127.0.0.1:8000/api/health/ready
```

Readiness returns HTTP 200 even for degraded dependencies; check that the JSON
contains `status: ok`, `database: ready`, and `storage: ready`.

Verified: public frontend and readiness, catalogue, authenticated sources,
S3 HeadBucket, SQS attributes, Bedrock Converse, and Polly neural synthesis.
Worker logs confirm polling with IAM role credentials. A full queued ingestion
has not been submitted as part of deployment verification. Existing Atlas data
includes two published circulars; no seed/reset was run.

## HTTPS and admin access

The public IP currently serves HTTP. Do not send the reviewer token over public
HTTP. Until HTTPS is configured, use an SSH tunnel for admin access:

```sh
ssh -i /Users/ayushanand/Downloads/janvaani.pem -N -L 8080:127.0.0.1:80 ubuntu@13.233.117.95
```

Open `http://localhost:8080` in your browser; the remote connection is carried
over SSH. The reviewer token remains in the backend `.env` on EC2.

For a domain: point its DNS A record to a stable instance address, replace `:80`
in Caddyfile with that domain, validate and reload Caddy. Ports 80/443 must be
reachable for automatic HTTPS. An auto-assigned public IP can change after an
EC2 stop/start; update Atlas allowlisting and DNS or allocate an Elastic IP.

## Updates

Upload backend source without `.env`, virtualenvs, or local caches. Install
requirements with the existing `.venv/bin/pip`. Restart API first, verify
readiness, then restart the worker to avoid simultaneous index initialization.
Build the frontend locally with `npm run build --prefix frontend` and upload
`frontend/dist/` contents to `/var/www/janvaani`.

If hosting the frontend separately, set `VITE_API_BASE_URL` to the HTTPS API URL
including `/api` before building, and set backend `CORS_ORIGINS` to a JSON array
of allowed frontend origins, then restart the API.

SQS visibility timeout is currently 120 seconds, with no redrive policy returned.
Long-running jobs can be delivered again if they exceed that timeout; add
visibility renewal and a dead-letter queue before relying on long crawl jobs.
SES and SageMaker are unconfigured in this deployment.
