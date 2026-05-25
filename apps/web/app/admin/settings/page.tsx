const runtimeSettings = [
  { name: "User header", value: "X-Agent-Forge-User", locked: true },
  { name: "Department header", value: "X-Agent-Forge-Department", locked: true },
  { name: "Role header", value: "X-Agent-Forge-Roles", locked: true },
  { name: "Clearance header", value: "X-Agent-Forge-Clearance", locked: true },
];

const policyToggles = [
  { name: "Citation required", state: "Enabled" },
  { name: "ACL filter required", state: "Enabled" },
  { name: "Audit write required", state: "Enabled" },
  { name: "Deep-review escalation", state: "Enabled" },
];

export default function SettingsPage() {
  return (
    <section className="page settingsPage">
      <div className="header">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Settings</h1>
          <p>
            Review local pilot defaults for principal headers, model routing, and release-gate
            policy.
          </p>
        </div>
        <button className="button secondary" disabled type="button">
          Save pending API
        </button>
      </div>

      <section className="nextAction">
        <div>
          <span className="badge neutral">Policy profile</span>
          <strong>model-routing-policy/v0.1 is the active budget and escalation baseline.</strong>
        </div>
        <span className="badge">Standard budget</span>
      </section>

      <div className="settingsGrid">
        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Principal mapping</h2>
              <p>Local headers used until SSO and policy engine integration lands.</p>
            </div>
          </div>
          <div className="configList">
            {runtimeSettings.map((setting) => (
              <label key={setting.name}>
                <span>{setting.name}</span>
                <input disabled={setting.locked} readOnly value={setting.value} />
              </label>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panelHeader">
            <div>
              <h2>Release policy</h2>
              <p>Controls that cannot be disabled for the MVP RAG assistant.</p>
            </div>
          </div>
          <div className="toggleList">
            {policyToggles.map((toggle) => (
              <label className="toggleRow" key={toggle.name}>
                <span>{toggle.name}</span>
                <input
                  aria-label={`${toggle.name} locked on`}
                  checked
                  className="toggleInput"
                  disabled
                  readOnly
                  role="switch"
                  type="checkbox"
                />
                <span className="badge">{toggle.state}</span>
              </label>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
