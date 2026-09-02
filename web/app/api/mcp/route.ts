/**
 * Transparent proxy to the eventOS Agent Fleet MCP server.
 *
 * Keeps the browser client same-origin and the upstream URL in server-side
 * config. Every MCP header the transport cares about — session id, protocol
 * version — is forwarded in both directions, so the client sees the fleet's
 * responses unmodified.
 */

const UPSTREAM =
  process.env.CLOUD_RUN_URL ??
  "https://eventos-agent-fleet-502476192372.us-central1.run.app";

// Tool calls hit a live LLM (fleet_architect_design), so allow a long window.
export const maxDuration = 120;
export const dynamic = "force-dynamic";

const FORWARD_TO_UPSTREAM = [
  "content-type",
  "accept",
  "mcp-session-id",
  "mcp-protocol-version",
];

const FORWARD_TO_CLIENT = [
  "content-type",
  "mcp-session-id",
  "mcp-protocol-version",
];

function upstreamHeaders(request: Request): Headers {
  const headers = new Headers();
  for (const name of FORWARD_TO_UPSTREAM) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (!headers.has("content-type")) headers.set("content-type", "application/json");
  if (!headers.has("accept")) headers.set("accept", "application/json");
  return headers;
}

function clientHeaders(response: Response): Headers {
  const headers = new Headers();
  for (const name of FORWARD_TO_CLIENT) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("cache-control", "no-store");
  return headers;
}

async function forward(request: Request, method: "POST" | "DELETE"): Promise<Response> {
  const body = method === "POST" ? await request.text() : undefined;

  try {
    const upstream = await fetch(`${UPSTREAM}/mcp`, {
      method,
      headers: upstreamHeaders(request),
      body,
      cache: "no-store",
    });

    // 202 (notification) and 204 (session terminated) carry no body, and
    // constructing a Response with one would throw.
    if (upstream.status === 202 || upstream.status === 204) {
      return new Response(null, {
        status: upstream.status,
        headers: clientHeaders(upstream),
      });
    }

    return new Response(upstream.body, {
      status: upstream.status,
      headers: clientHeaders(upstream),
    });
  } catch (error) {
    // Surface transport failures as a JSON-RPC internal error so the client's
    // normal error path handles them instead of a raw network exception.
    const message = error instanceof Error ? error.message : String(error);
    return Response.json(
      {
        jsonrpc: "2.0",
        id: null,
        error: { code: -32603, message: `Could not reach the fleet: ${message}` },
      },
      { status: 502, headers: { "cache-control": "no-store" } },
    );
  }
}

export async function POST(request: Request) {
  return forward(request, "POST");
}

export async function DELETE(request: Request) {
  return forward(request, "DELETE");
}

/** Where the proxy points, so the UI can show the live upstream. */
export async function GET() {
  return Response.json(
    { upstream: `${UPSTREAM}/mcp`, manifest: `${UPSTREAM}/mcp/manifest` },
    { headers: { "cache-control": "no-store" } },
  );
}
