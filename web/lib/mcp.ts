/**
 * A Model Context Protocol client speaking JSON-RPC 2.0 over Streamable HTTP.
 *
 * Runs in the browser against /api/mcp, which proxies to the eventOS Agent
 * Fleet on Cloud Run. The proxy exists so the client stays same-origin and the
 * upstream URL stays in server-side config — the fleet's /mcp endpoint sets
 * permissive CORS, so a direct browser connection also works if you point
 * `endpoint` at it.
 */

export const PROTOCOL_VERSION = "2025-11-25";

export interface JsonSchema {
  type?: string;
  description?: string;
  enum?: string[];
  items?: JsonSchema;
  properties?: Record<string, JsonSchema>;
  required?: string[];
}

export interface McpTool {
  name: string;
  title?: string;
  description: string;
  inputSchema: JsonSchema;
  _meta?: { "eventos/agent"?: string };
}

export interface ContentBlock {
  type: string;
  text?: string;
}

export interface ToolResult {
  content: ContentBlock[];
  structuredContent?: unknown;
  isError?: boolean;
}

export interface ServerInfo {
  name: string;
  title?: string;
  version: string;
}

export interface InitializeResult {
  protocolVersion: string;
  capabilities: Record<string, unknown>;
  serverInfo: ServerInfo;
  instructions?: string;
}

interface JsonRpcResponse<T> {
  jsonrpc: "2.0";
  id: number | string;
  result?: T;
  error?: { code: number; message: string; data?: unknown };
}

/** One request/response pair on the wire, for protocol inspection. */
export interface WireExchange {
  seq: number;
  method: string;
  request: unknown;
  response: unknown;
  ms: number;
  at: string;
  status: "ok" | "error" | "notification";
}

/** A JSON-RPC error returned by the server, carrying the spec error code. */
export class McpError extends Error {
  constructor(
    readonly code: number,
    message: string,
    readonly data?: unknown,
  ) {
    super(message);
    this.name = "McpError";
  }
}

export class McpClient {
  private nextId = 1;
  private sessionId: string | null = null;
  private negotiatedVersion: string = PROTOCOL_VERSION;

  private wireSeq = 0;

  constructor(
    private readonly endpoint: string = "/api/mcp",
    /** Called with every exchange, so a UI can show the raw protocol traffic. */
    private readonly onExchange?: (exchange: WireExchange) => void,
  ) {}

  private record(
    method: string,
    request: unknown,
    response: unknown,
    ms: number,
    status: WireExchange["status"],
  ): void {
    this.onExchange?.({
      seq: ++this.wireSeq,
      method,
      request,
      response,
      ms: Math.round(ms),
      at: new Date().toISOString().slice(11, 23),
      status,
    });
  }

  get session(): string | null {
    return this.sessionId;
  }

  get protocolVersion(): string {
    return this.negotiatedVersion;
  }

  /** Open the session. Must be called before tools/list or tools/call. */
  async initialize(): Promise<InitializeResult> {
    const { body, headers } = await this.send<InitializeResult>("initialize", {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: "eventos-webmcp-client", version: "1.0.0" },
    });

    this.sessionId = headers.get("Mcp-Session-Id") ?? this.sessionId;
    this.negotiatedVersion = body.protocolVersion ?? PROTOCOL_VERSION;

    // Per the lifecycle spec the client confirms it is ready. Fire-and-forget:
    // it is a notification, so the server returns 202 with no body.
    void this.notify("notifications/initialized");

    return body;
  }

  async listTools(): Promise<McpTool[]> {
    const { body } = await this.send<{ tools: McpTool[] }>("tools/list", {});
    return body.tools ?? [];
  }

  async callTool(name: string, args: Record<string, unknown>): Promise<ToolResult> {
    const { body } = await this.send<ToolResult>("tools/call", {
      name,
      arguments: args,
    });
    return body;
  }

  async ping(): Promise<void> {
    await this.send("ping", {});
  }

  /** Terminate the session server-side. Best-effort. */
  async close(): Promise<void> {
    if (!this.sessionId) return;
    try {
      await fetch(this.endpoint, { method: "DELETE", headers: this.headers() });
    } catch {
      // The session expires on its own; a failed teardown is not worth surfacing.
    }
    this.sessionId = null;
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "MCP-Protocol-Version": this.negotiatedVersion,
    };
    if (this.sessionId) headers["Mcp-Session-Id"] = this.sessionId;
    return headers;
  }

  private async notify(method: string, params: Record<string, unknown> = {}): Promise<void> {
    const message = { jsonrpc: "2.0", method, params };
    const started = performance.now();
    try {
      const response = await fetch(this.endpoint, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(message),
      });
      this.record(
        method,
        message,
        `HTTP ${response.status} — no body, as the spec requires for a notification`,
        performance.now() - started,
        "notification",
      );
    } catch {
      // Notifications carry no response, so a transport hiccup here is not fatal.
    }
  }

  private async send<T>(
    method: string,
    params: Record<string, unknown>,
  ): Promise<{ body: T; headers: Headers }> {
    const id = this.nextId++;
    const message = { jsonrpc: "2.0", id, method, params };
    const started = performance.now();

    let response: Response;
    try {
      response = await fetch(this.endpoint, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(message),
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      this.record(method, message, { transportError: detail }, performance.now() - started, "error");
      throw new McpError(-32603, `Transport failure on ${method}: ${detail}`);
    }

    const text = await response.text();
    const elapsed = performance.now() - started;

    if (!text.trim()) {
      const detail = `Empty response from ${method} (HTTP ${response.status})`;
      this.record(method, message, { httpStatus: response.status }, elapsed, "error");
      throw new McpError(response.status, detail);
    }

    let payload: JsonRpcResponse<T>;
    try {
      payload = parseResponse<T>(text, response.headers.get("Content-Type"));
    } catch (error) {
      this.record(method, message, text.slice(0, 500), elapsed, "error");
      throw error;
    }

    this.record(method, message, payload, elapsed, payload.error ? "error" : "ok");

    if (payload.error) {
      throw new McpError(payload.error.code, payload.error.message, payload.error.data);
    }
    if (payload.result === undefined) {
      throw new McpError(-32603, `Response to ${method} carried neither result nor error`);
    }

    return { body: payload.result, headers: response.headers };
  }
}

/**
 * Streamable HTTP lets the server answer with either JSON or an SSE stream, so
 * accept both. For SSE we take the first `data:` payload, which is the response
 * to the request we just sent.
 */
function parseResponse<T>(text: string, contentType: string | null): JsonRpcResponse<T> {
  if (contentType?.includes("text/event-stream")) {
    for (const line of text.split("\n")) {
      if (line.startsWith("data:")) {
        return JSON.parse(line.slice(5).trim()) as JsonRpcResponse<T>;
      }
    }
    throw new McpError(-32700, "SSE response contained no data frame");
  }

  try {
    return JSON.parse(text) as JsonRpcResponse<T>;
  } catch {
    throw new McpError(-32700, `Could not parse response as JSON: ${text.slice(0, 200)}`);
  }
}

/** Flatten a tool result's content blocks into displayable text. */
export function resultText(result: ToolResult): string {
  return result.content
    .filter((block) => block.type === "text" && block.text)
    .map((block) => block.text as string)
    .join("\n\n");
}

/** The fleet agent that owns a tool, for grouping in the UI. */
export function toolAgent(tool: McpTool): string {
  return tool._meta?.["eventos/agent"] ?? "Fleet";
}
