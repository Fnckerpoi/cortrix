# Cortrix private MCP access

Endpoint: `https://durieamac-mini.taile2af0f.ts.net/mcp`

Transport: MCP Streamable HTTP with Bearer authentication. Clients must be connected to the same Tailscale tailnet and permitted by its ACLs. Tailscale Serve provides HTTPS on port 443; Funnel is not enabled. The core API remains on host loopback port 8420. The MCP gateway is published only on host loopback port 8421.

## Client configuration

On the host, ready-to-use configurations containing the credential are stored outside the repository with mode 0600:

- `~/.config/cortrix/remote-client.json`: HTTP client configuration.
- `~/.config/cortrix/stdio-client.json`: stdio bridge template using Node.js `npx mcp-remote` (bridge not independently tested).
- `~/.config/cortrix/mcp-token`: Bearer token, also mounted read-only into the gateway.

Transfer the chosen configuration privately to the Mac or Windows client. Merge the `cortrix` entry into the Agent's MCP configuration; field conventions vary by Agent. Never commit these credential-bearing files. A remote HTTP client should use:

```json
{
  "mcpServers": {
    "cortrix": {
      "type": "http",
      "url": "https://durieamac-mini.taile2af0f.ts.net/mcp",
      "headers": {"Authorization": "Bearer <value from mcp-token>"}
    }
  }
}
```

An Agent supporting only stdio requires the bridge template, Node.js/npm and initial network access to obtain mcp-remote. OAuth-only clients that cannot supply a custom Authorization header need an adapter; arbitrary MCP clients are not universally compatible.

## Usage

Call `cortrix_query` with an explicit `namespaces` argument:

- `obsidian-knowledge`: 196 knowledge Markdown documents.
- `obsidian-experience`: 39 experience Markdown documents.
- Both: `["obsidian-knowledge", "obsidian-experience"]`.

The default is knowledge. The package lists 31 tools, including tools that write/delete data and admin tools subject to backend checks. This is not a read-only service; keep the token limited to trusted personal Agents and use write tools only when requested.

## Operation

Gateway container: `cortrix-mcp-http`, image `cortrix/mcp:local` built from this checkout. Runtime adapter: `deploy/mcp_http.py`, SDK mcp 2.3.0, stateless Streamable HTTP with DNS rebinding checks and an ASGI Bearer gate. Docker restart policy: unless-stopped. It uses network `deploy_default` and backend `http://cortrix:8420`.

The existing container was created with `docker run`. `deploy/docker-compose.mcp.yml` records an equivalent configuration for recreation; before first adopting Compose, remove only the stopped gateway container with that name. Do not remove core volumes.

Inspect:

```bash
docker logs cortrix-mcp-http
docker inspect cortrix-mcp-http
/Applications/Tailscale.app/Contents/MacOS/Tailscale serve status
```

Stop private HTTPS sharing:

```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale serve --https=443 off
```

To rotate the token, replace mcp-token with a fresh random value (retain mode 0600), restart the gateway, and regenerate/update both client configurations. The token is loaded at gateway startup.

## Verification (2026-10-31)

From the deployment Mac, through its Tailscale HTTPS hostname:

- No credential and incorrect credential: HTTP 401.
- Correct credential: initialize protocol 2025-11-25 returns HTTP 200.
- tools/list returns 31 tools.
- tools/call cortrix_query finds the Spring circular dependency document in knowledge and the electronic batch record document in experience.

This proves the hostname/TLS/auth/MCP/backend path on the host. Actual Mac/Windows client access from another device remains to be verified there. The deployment Mac must remain awake, Docker and Tailscale running.
