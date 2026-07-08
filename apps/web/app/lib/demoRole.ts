// Demo role switcher (UX only — the backend enforces RBAC/ACL server-side regardless
// of what the frontend sends; this merely picks which stub identity headers to send
// so a reviewer can see each role's real, server-enforced view).
//
// SSO is not wired yet (header-stub auth, known limitation). When SSO lands, this
// module and the header bundles disappear in favor of real session identity.

export const DEMO_ROLE_STORAGE_KEY = "af-demo-role";

export const DEMO_ROLES = {
  // "admin" is the historical OPERATOR bundle, unchanged — the default experience.
  admin: {
    "X-Agent-Forge-User": "operator",
    "X-Agent-Forge-Department": "Operations",
    "X-Agent-Forge-Roles": "admin",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
  },
  // Non-privileged, authenticated identity. Clearance "internal" (not "public") so
  // knowledge sources (whose default confidentiality is typically "internal") stay
  // visible, while "restricted"+ documents are filtered out of list views by the
  // server-side ACL/clearance scoping — making that scoping visibly demonstrable.
  developer: {
    "X-Agent-Forge-User": "dev1",
    "X-Agent-Forge-Department": "Engineering",
    "X-Agent-Forge-Roles": "developer",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
  },
} as const;

export type DemoRoleKey = keyof typeof DEMO_ROLES;

// Roles the backend treats as privileged for mutations (PRIVILEGED_ROLES in
// apps/api/app/infra/authz.py). Used only to hide/disable controls the server
// would 403 anyway — pure UX, not an enforcement point.
const PRIVILEGED_DEMO_ROLES: ReadonlySet<DemoRoleKey> = new Set(["admin"]);

export function getDemoRole(): DemoRoleKey {
  if (typeof window === "undefined") return "admin";
  const stored = window.localStorage.getItem(DEMO_ROLE_STORAGE_KEY);
  return stored && stored in DEMO_ROLES ? (stored as DemoRoleKey) : "admin";
}

export function setDemoRole(role: DemoRoleKey): void {
  window.localStorage.setItem(DEMO_ROLE_STORAGE_KEY, role);
}

export function isPrivilegedDemoRole(role: DemoRoleKey): boolean {
  return PRIVILEGED_DEMO_ROLES.has(role);
}

// Synchronous header builder read at call time by every api.ts fetch.
export function roleHeaders(): Record<string, string> {
  return { ...DEMO_ROLES[getDemoRole()] };
}
