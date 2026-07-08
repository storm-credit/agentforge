"use client";
import { useEffect, useState } from "react";
import { type DemoRoleKey, getDemoRole, isPrivilegedDemoRole } from "./demoRole";

// Reads the persisted demo role after mount (localStorage is browser-only, so the
// first render assumes the default "admin" to keep SSR/CSR markup consistent).
// Role changes go through the RoleSwitcher, which reloads the page, so no
// cross-component subscription is needed.
export function useDemoRole(): { role: DemoRoleKey; isPrivileged: boolean } {
  const [role, setRole] = useState<DemoRoleKey>("admin");
  useEffect(() => {
    setRole(getDemoRole());
  }, []);
  return { role, isPrivileged: isPrivilegedDemoRole(role) };
}
