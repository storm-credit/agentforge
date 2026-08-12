"use client";
import { DEMO_ROLES } from "../lib/demoRole";
import { useDemoRole } from "../lib/useDemoRole";

// Read-only display of the identity a run will actually be created as.
//
// Identity is chosen in ONE place (the sidebar Demo role switcher) and applied to
// every request; this note just makes the consequence visible where it matters —
// the ask forms, whose runs are attributed to this principal in the audit trail
// and scoped to it by the owner-or-admin GET /runs check. It shows exactly what
// the headers say (see lib/demoRole.ts) and claims no authority beyond them.
export function ActiveIdentityNote() {
  const { role } = useDemoRole();
  const headers = DEMO_ROLES[role];

  return (
    <p className="note" data-testid="active-identity" style={{ margin: "0 0 var(--space-3)" }}>
      사용자(부서):{" "}
      <strong data-testid="active-identity-role">{role}</strong> —{" "}
      {headers["X-Agent-Forge-User"]} / {headers["X-Agent-Forge-Department"]} · 열람등급{" "}
      {headers["X-Agent-Forge-Clearance"]} · 그룹 {headers["X-Agent-Forge-Groups"]}
      <br />
      이 질문은 위 사용자로 기록되며(감사 추적), 답변 근거도 이 사용자의 권한 범위에서만
      검색됩니다. 사용자는 왼쪽 사이드바의 &quot;Demo role&quot;에서 바꿉니다.
    </p>
  );
}
