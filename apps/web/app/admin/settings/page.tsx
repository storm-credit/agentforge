const settings = [
  { name: "부서 헤더", value: "X-Agent-Forge-Department" },
  { name: "사용자 헤더", value: "X-Agent-Forge-User" },
  { name: "역할 헤더", value: "X-Agent-Forge-Roles" },
  { name: "DB 준비 상태", value: "선택적(Opt-in)" },
];

export default function SettingsPage() {
  return (
    <section className="page">
      <div>
        <p className="eyebrow">관리</p>
        <h1>설정</h1>
        <p>SSO·정책 엔진·런타임 레지스트리가 붙기 전까지 사용하는 로컬 파일럿 기본값입니다.</p>
      </div>
      <section className="panel">
        <h2>로컬 기본값</h2>
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

