"""Private Streamable HTTP adapter for the local Cortrix MCP package."""
import hmac
from pathlib import Path
import uvicorn
from cortrix_mcp.server import mcp
from mcp.server.transport_security import TransportSecuritySettings

TOKEN = Path('/run/secrets/mcp_token').read_text().strip()
assert len(TOKEN) >= 32
app = mcp.streamable_http_app(
    stateless_http=True, json_response=True, host='0.0.0.0',
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=['127.0.0.1:8421', 'localhost:8421', 'durieamac-mini.taile2af0f.ts.net', 'durieamac-mini.taile2af0f.ts.net:443'],
        allowed_origins=['https://durieamac-mini.taile2af0f.ts.net'],
    ),
)

class BearerGate:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            supplied = dict(scope.get('headers', [])).get(b'authorization', b'').decode('latin1')
            if not hmac.compare_digest(supplied, 'Bearer ' + TOKEN):
                await send({'type': 'http.response.start', 'status': 401,
                            'headers': [(b'www-authenticate', b'Bearer'), (b'content-type', b'application/json')]})
                await send({'type': 'http.response.body', 'body': b'{"error":"unauthorized"}'})
                return
        await self.application(scope, receive, send)

if __name__ == '__main__':
    uvicorn.run(BearerGate(app), host='0.0.0.0', port=8421, access_log=False)
