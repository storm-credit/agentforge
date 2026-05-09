const settings = [
  { name: "Department header", value: "X-Agent-Forge-Department" },
  { name: "User header", value: "X-Agent-Forge-User" },
  { name: "Role header", value: "X-Agent-Forge-Roles" },
  { name: "Database readiness", value: "Opt-in" },
];

export default function SettingsPage() {
  return (
    <section className="page">
      <div>
        <p className="eyebrow">Admin</p>
        <h1>Settings</h1>
        <p>Manage local pilot defaults before SSO, policy engines, and runtime registries arrive.</p>
      </div>
      <section className="panel">
        <h2>Local defaults</h2>
        <ul className="statusList">
          {settings.map((setting) => (
            <li key={setting.name}>
              <span>{setting.name}</span>
              <span className="badge">{setting.value}</span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}

