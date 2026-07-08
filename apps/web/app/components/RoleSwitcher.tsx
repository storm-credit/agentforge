"use client";
import { useEffect, useState } from "react";
import { type DemoRoleKey, DEMO_ROLES, getDemoRole, setDemoRole } from "../lib/demoRole";

// Demo-only identity picker (SSO not wired; header-stub auth). Switching roles
// reloads the page so every view refetches with the selected identity's headers
// and shows that role's real, server-enforced view.
export function RoleSwitcher() {
  const [role, setRole] = useState<DemoRoleKey>("admin");
  useEffect(() => {
    setRole(getDemoRole());
  }, []);

  function onChange(next: DemoRoleKey) {
    setDemoRole(next);
    setRole(next);
    window.location.reload();
  }

  return (
    <div style={{ marginTop: "auto", paddingTop: "16px", fontSize: "12px" }}>
      <label htmlFor="demo-role" style={{ display: "block", color: "#94a3b8", marginBottom: "4px" }}>
        Demo role
      </label>
      <select
        id="demo-role"
        data-testid="demo-role-switcher"
        value={role}
        onChange={(e) => onChange(e.target.value as DemoRoleKey)}
        style={{ width: "100%" }}
      >
        {(Object.keys(DEMO_ROLES) as DemoRoleKey[]).map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
    </div>
  );
}
