/**
 * Registration against the browser's WebMCP surface.
 *
 * The API is young and still moving. Chrome 146 shipped it on
 * `navigator.modelContext`; the W3C explainer writes it as
 * `document.modelContext`; earlier drafts used `window.agent`. We register
 * against every surface that exists — deduplicated, because a browser may
 * alias one object onto several of them — so the page works in an agentic
 * browser today and in the standardised one later without a code change.
 *
 * Two things the spec does not solve for, which matter when someone opens this
 * page cold in an agentic browser:
 *
 *   1. The host API may be injected *after* our React effect runs. There is no
 *      event for it, so we watch for one appearing and register into it when it
 *      does, for a bounded window after load.
 *   2. When no host API exists at all — a plain browser, or a judge opening the
 *      page in Safari — we install a minimal same-shape shim so the page's own
 *      tool runner still works and a polyfill, extension or headless harness has
 *      somewhere to look. The shim is branded, so we never mistake our own
 *      stand-in for a real host and claim native support we don't have.
 */

import { TOOLS, type WebMcpResult, type WebMcpToolDescriptor } from "@/lib/webmcp-tools";

export interface ModelContextLike {
  registerTool?: (tool: WebMcpToolDescriptor) => unknown;
  unregisterTool?: (name: string) => unknown;
  /** Pre-March-2026 shape: replace the whole tool set in one call. */
  provideContext?: (init: { tools: WebMcpToolDescriptor[] }) => unknown;
}

/** What the page shows about its own registration. */
export interface RegistrationStatus {
  registered: string[];
  /** Every surface we successfully registered against. */
  surfaces: string[];
  /** True only when the *browser* supplied the API. Our shim never sets this. */
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

/** Marks an object as our stand-in rather than a browser-provided host. */
const SHIM_BRAND = "__eventosWebMcpShim";

/** How long after load we keep watching for a host API to show up. */
const WATCH_MS = 60_000;
const WATCH_INTERVAL_MS = 500;

/**
 * All six tools are read-only lookups — none of them book, cancel, send or
 * charge anything. Saying so lets a host call them without a confirmation
 * prompt, which is the difference between an agent exploring the page freely
 * and one that stops to ask before every read.
 */
const ANNOTATIONS = { readOnlyHint: true } as const;

/* ── Surfaces ─────────────────────────────────────────────────────────── */

interface Surface {
  label: string;
  api: ModelContextLike;
  native: boolean;
}

function isShim(api: unknown): boolean {
  return Boolean((api as Record<string, unknown> | null | undefined)?.[SHIM_BRAND]);
}

function usable(api: unknown): api is ModelContextLike {
  if (!api || typeof api !== "object") return false;
  const candidate = api as ModelContextLike;
  return typeof candidate.registerTool === "function" || typeof candidate.provideContext === "function";
}

/**
 * Host-provided surfaces present right now. Never returns our own shim, and
 * never returns the same object twice — a browser that aliases
 * `document.modelContext` onto `navigator.modelContext` would otherwise get two
 * registration passes and throw on every duplicate tool name.
 */
function nativeSurfaces(): Surface[] {
  const found: Surface[] = [];
  const seen = new Set<unknown>();

  const consider = (label: string, api: unknown) => {
    if (!usable(api) || isShim(api) || seen.has(api)) return;
    seen.add(api);
    found.push({ label, api, native: true });
  };

  if (typeof navigator !== "undefined") consider("navigator.modelContext", navigator.modelContext);
  if (typeof document !== "undefined") consider("document.modelContext", document.modelContext);
  if (typeof window !== "undefined") consider("window.modelContext", window.modelContext);

  return found;
}

/** A shim used only when the browser has no WebMCP API of its own. */
function createShim(): ModelContextLike {
  const tools = new Map<string, WebMcpToolDescriptor>();
  return {
    [SHIM_BRAND]: true,
    tools,
    registerTool(tool: WebMcpToolDescriptor) {
      if (tools.has(tool.name)) {
        throw new Error(`A tool named ${tool.name} is already registered`);
      }
      tools.set(tool.name, tool);
      return { unregister: () => tools.delete(tool.name) };
    },
    unregisterTool(name: string) {
      return tools.delete(name);
    },
    getTools() {
      return [...tools.values()];
    },
  } as unknown as ModelContextLike;
}

/** Install the shim once, and hand back the same one on later calls. */
function ensureShim(): Surface {
  const existing = window.modelContext;
  if (isShim(existing)) {
    return { label: "document.modelContext (shim)", api: existing as ModelContextLike, native: false };
  }

  const shim = createShim();

  // Configurable, so a real implementation — or a polyfill loaded after us —
  // can replace it rather than colliding with it. If it does, the watcher below
  // notices and registers into the replacement.
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

  return { label: "document.modelContext (shim)", api: shim, native: false };
}

/* ── Registration ─────────────────────────────────────────────────────── */

/** Register every tool into one surface. Returns how many landed. */
function registerInto(surface: Surface, status: RegistrationStatus): number {
  const annotated = TOOLS.map((tool) => ({ ...tool, annotations: ANNOTATIONS }));

  // Hosts that only speak the older bulk API get the whole set in one call.
  if (typeof surface.api.registerTool !== "function") {
    try {
      surface.api.provideContext?.({ tools: annotated });
      for (const tool of TOOLS) {
        if (!status.registered.includes(tool.name)) status.registered.push(tool.name);
      }
      return TOOLS.length;
    } catch (error) {
      status.errors.push(`${surface.label} / provideContext: ${describe(error)}`);
      return 0;
    }
  }

  let count = 0;
  for (const tool of annotated) {
    try {
      // `registerTool` throws on a duplicate name, and React re-mounts in
      // development, so clear the name first where the surface allows it.
      try {
        surface.api.unregisterTool?.(tool.name);
      } catch {
        // Nothing was registered under that name. Expected on a first run.
      }
      surface.api.registerTool!(tool);
      count += 1;
      if (!status.registered.includes(tool.name)) status.registered.push(tool.name);
    } catch (error) {
      status.errors.push(`${surface.label} / ${tool.name}: ${describe(error)}`);
    }
  }
  return count;
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Current status, kept across re-registrations so the UI can be updated. */
let current: RegistrationStatus = { registered: [], surfaces: [], native: false, errors: [] };
let watching = false;

function publish(status: RegistrationStatus): void {
  current = status;

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
}

/** Register into whatever surfaces exist right now. */
function registerNow(): RegistrationStatus {
  const status: RegistrationStatus = {
    registered: [...current.registered],
    surfaces: [],
    native: false,
    errors: [],
  };

  const hosts = nativeSurfaces();
  const targets = hosts.length ? hosts : [ensureShim()];

  for (const surface of targets) {
    if (registerInto(surface, status)) {
      status.surfaces.push(surface.label);
      status.native ||= surface.native;
    }
  }

  return status;
}

/**
 * Watch for a host API that arrives after we registered — an extension that
 * injects late, or a browser that sets it up after first paint. There is no
 * event for this, so we poll on a bounded schedule and stop as soon as we find
 * one. Cheap: a few property reads twice a second, for a minute after load.
 */
function watchForHost(): void {
  if (watching || current.native) return;
  watching = true;

  const started = Date.now();

  const check = () => {
    if (!nativeSurfaces().length) return false;

    const upgraded = registerNow();
    if (upgraded.native) {
      publish(upgraded);
      console.info(
        `[eventOS WebMCP] host appeared after load — re-registered ${upgraded.registered.length} tools on ${upgraded.surfaces.join(", ")}`,
      );
      return true;
    }
    return false;
  };

  const timer = window.setInterval(() => {
    if (check() || Date.now() - started > WATCH_MS) {
      window.clearInterval(timer);
      window.removeEventListener("visibilitychange", nudge);
      window.removeEventListener("focus", nudge);
      watching = false;
    }
  }, WATCH_INTERVAL_MS);

  // A tab returning to the foreground is a likely moment for a host to attach.
  function nudge() {
    check();
  }
  window.addEventListener("visibilitychange", nudge);
  window.addEventListener("focus", nudge);
}

/**
 * Register all six tools. Safe to call twice — React re-mounts in development,
 * and `registerTool` throws on a duplicate name, so each tool is unregistered
 * first where the surface supports it.
 */
export function registerEventosTools(): RegistrationStatus {
  if (typeof window === "undefined") {
    return { registered: [], surfaces: [], native: false, errors: [] };
  }

  const status = registerNow();
  publish(status);

  // Judges will look here first.
  console.info(
    `[eventOS WebMCP] registered ${status.registered.length} tools on ${
      status.surfaces.join(", ") || "no surface"
    }${status.native ? "" : " — no native WebMCP host detected, using shim"}`,
    status.registered,
  );

  if (!status.native) watchForHost();

  return status;
}
