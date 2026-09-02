"use client";

import { useEffect } from "react";
import { registerEventosTools } from "@/lib/webmcp";

/**
 * Mounted once in the root layout. Registering here rather than on the landing
 * page means the tools are live on every route the agent might land on.
 */
export default function WebMcpProvider() {
  useEffect(() => {
    registerEventosTools();
  }, []);

  return null;
}
