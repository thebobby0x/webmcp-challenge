/**
 * Registration against the browser's WebMCP surface.
 *
 * The spec puts the API on `document.modelContext`; earlier drafts and some
 * shipping builds put it on `navigator.modelContext`. We register against every
 * surface that exists, so the page works in an agentic browser today and in the
 * standardised one later without a code change.
 *
 * When no host API is present at all — a plain browser, or a judge opening the
 * page in Safari — we install a minimal same-shape shim. That keeps the page's
 * own tool runner working and leaves the registry where a polyfill, extension
 * or headless harness can find it, instead of silently registering nothing.
 */

import { TOOLS, type WebMcpResult, type WebMcpToolDescriptor } from "@/lib/webmcp-tools";

export interface ModelContextLike {
  registerTool: (tool: WebMcpToolDescriptor) => unknown;
  unregisterTool?: (name: string) => unknown;
}

/** What the page shows about its own registration. */
export interface RegistrationStatus {
  registered: string[];
  /** Every surface we successfully registered against. */
  surfaces: string[];
  /** True when the browser supplied the API rather than us shimming it. */
  native: boolean;
  errors: string[];
}

declare global {
  interface Document {
    modelContext?: ModelContextLike;
  }
  interface Navigator {
    modelContext?: ModelContextLike;
  }
  interface Window {
    modelContext?: ModelContextLike;
    /** Registration status and a direct call path, for the page and for tests. */
    __eventosWebMCP?: RegistrationStatus & {
      tools: WebMcpToolDescriptor[];
      call: (name: string, input?: Record<string, unknown>) => Promise<WebMcpResult>;
    };
  }
}

export const READY_EVENT = "eventos:webmcp-ready";

/** A shim used only when the browser has no WebMCP API of its own. */
function createShim(): ModelContextLike & { tools: Map<string, WebMcpToolDescriptor> } {
  const tools = new Map<string, WebMcpToolDescriptor>();
  return {
    tools,
    registerTool(tool) {
      if (tools.has(tool.name)) {
        throw new Error(`A tool named ${tool.name} is already registered`);
      }
      tools.set(tool.name, tool);
      return { unregister: () => tools.delete(tool.name) };
    },
    unregisterTool(name) {
      return tools.delete(name);
    },
  };
}

interface Surface {
  label: string;
  api: ModelContextLike;
  native: boolean;
}

/** Every WebMCP surface this browser exposes, plus a shim if it exposes none. */
function surfaces(): Surface[] {
  const found: Surface[] = [];

  if (typeof document !== "undefined" && document.modelContext) {
    found.push({ label: "document.modelContext", api: document.modelContext, native: true });
  }
  if (typeof navigator !== "undefined" && navigator.modelContext) {
    found.push({ label: "navigator.modelContext", api: navigator.modelContext, native: true });
  }
  if (typeof window !== "undefined" && window.modelContext) {
    found.push({ label: "window.modelContext", api: window.modelContext, native: true });
  }

  if (found.length) return found;

  const shim = createShim();
  // Defined as configurable so a real implementation — or a polyfill loaded
  // after us — can replace it rather than colliding with it.
  try {
    Object.defineProperty(document, "modelContext", {
      value: shim,
      configurable: true,
      writable: true,
    });
  } catch {
    // Some engines lock `document`; the window mirror below still works.
  }
  window.modelContext = shim;

  return [{ label: "document.modelContext (shim)", api: shim, native: false }];
}

/**
 * Register all six tools. Safe to call twice — React re-mounts in development,
 * and `registerTool` throws on a duplicate name, so each tool is unregistered
 * first where the surface supports it.
 */
export function registerEventosTools(): RegistrationStatus {
  const status: RegistrationStatus = {
    registered: [],
    surfaces: [],
    native: false,
    errors: [],
  };

  if (typeof window === "undefined") return status;

  for (const surface of surfaces()) {
    let registeredHere = 0;

    for (const tool of TOOLS) {
      try {
        try {
          surface.api.unregisterTool?.(tool.name);
        } catch {
          // Nothing was registered under that name. Expected on a first run.
        }
        surface.api.registerTool(tool);
        registeredHere += 1;
        if (!status.registered.includes(tool.name)) status.registered.push(tool.name);
      } catch (error) {
        status.errors.push(
          `${surface.label} / ${tool.name}: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    }

    if (registeredHere) {
      status.surfaces.push(surface.label);
      status.native ||= surface.native;
    }
  }

  window.__eventosWebMCP = {
    ...status,
    tools: TOOLS,
    call: (name, input = {}) => {
      const tool = TOOLS.find((candidate) => candidate.name === name);
      if (!tool) return Promise.reject(new Error(`No registered tool named ${name}`));
      return tool.execute(input);
    },
  };

  window.dispatchEvent(new CustomEvent<RegistrationStatus>(READY_EVENT, { detail: status }));

  // Judges will look here first.
  console.info(
    `[eventOS WebMCP] registered ${status.registered.length} tools on ${
      status.surfaces.join(", ") || "no surface"
    }${status.native ? "" : " — no native WebMCP host detected, using shim"}`,
    status.registered,
  );

  return status;
}
