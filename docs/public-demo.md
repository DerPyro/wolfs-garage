# Public demo deployment

The demo stack is a disposable showcase of the standalone application. It uses the standalone Dockerfile and the real application API, but the demo backend must be the dedicated synthetic-data factory `wolfs_garage.demo:create_demo_app()`. Do not point this stack at a normal Garage database or private service. Its application state is bounded in a temporary SQLite directory owned by the demo process; it is reset after one hour when the next request arrives, and all state is lost when the process restarts. It has no database volume, production volume, shared Docker network, or connection to the existing garage.

The example configuration uses `demo.example.org` as a documentation-only hostname. Deployment examples use reserved example hosts; keep operator-specific hostnames and origins in an untracked private env file. The README's explicitly approved product link is separate from deployment configuration.

## Local configuration

Copy `deploy/demo.env.example` to an untracked private env file if you need to change the local port or host. The example supports `http://localhost:18996` with Host `localhost:18996`:

```sh
docker compose --env-file deploy/demo.env.example -f deploy/compose.demo.yaml config --quiet
docker compose --env-file deploy/demo.env.example -f deploy/compose.demo.yaml up --build
```

Open `http://localhost:18996`. The proxy binds only to loopback. The application has no published port and is reachable only from the proxy over the dedicated internal Docker network. The proxy also has a separate ordinary egress network for a later externally managed TLS/tunnel connector; the backend is not attached to that network and has no outbound route. No Cloudflare, DNS, host firewall, tunnel, or Access configuration is changed by these files.

## Operator deployment boundary

For an externally reachable demo, configure the independently managed TLS/tunnel layer to reach the proxy, preserve the public `Host` and the browser's `Origin`, and supply `X-Forwarded-Proto`. Never overwrite `Origin` to make a rejected write succeed. Set `GARAGE_DEMO_HOST` to the exact incoming Host (including a nonstandard port, if present) and `GARAGE_PUBLIC_ORIGIN` to the matching browser origin in a private env file. Keep the TLS/tunnel layer in front of this proxy. The proxy rejects other Host values before forwarding, passes `Host` and `Origin` through unchanged, and preserves the upstream `X-Forwarded-Proto`. It replaces `X-Forwarded-For` with the actual proxy peer address; rate limits do not trust client-supplied forwarding headers.

The NGINX layer limits API traffic to 10 requests/second per peer with a burst of 40, API writes to 2/second per peer with a burst of 10, and API writes globally to 5/second with a burst of 10. Static UI assets are not subject to those API limits so the first page load can fetch its normal asset set. Oversized request bodies above 16 KiB are rejected. A throttled response includes `Retry-After: 2`. These are resource bounds, not authentication or DDoS protection; availability still depends on the upstream network/service and operator capacity.

The backend runs as UID/GID 65532 with a read-only root filesystem, a 64 MiB `/tmp` tmpfs, 256 MiB memory, 0.5 CPU, 64 processes, no added capabilities, and `no-new-privileges`. The proxy runs as UID/GID 101 with a read-only root filesystem, tmpfs for generated configuration and runtime files, no added capabilities, a digest-pinned image, and read-only source templates. Its loopback-only published port is 18996 by default. The compose project name and networks are unique to the demo. Do not add private volumes, existing external networks, host binds, credentials, or real vehicle data.

The demo has no login and no private data. Anyone who reaches it can change the shared synthetic state until an hourly reset or process restart. Do not add real personal or vehicle information. Do not claim protection against volumetric attacks or abuse beyond the configured local limits.

## Validation

The local acceptance run confirmed the demo Compose configuration, passed `nginx -t` with the pinned image under the read-only, unprivileged settings, and passed the repository's 174 unit tests, DOM checks, and real-browser Chromium run. A 70-request API burst produced the expected 429 response with `Retry-After`; killing the worker produced a fresh generation on the next request and left only one demo temp directory. These checks validate the source configuration and runtime behavior, not external service availability.
