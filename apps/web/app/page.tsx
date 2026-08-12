import Link from "next/link";

const stats = [
  { label: "접근 통제", value: "RBAC + ACL", note: "검색 시점에 서버가 강제 적용" },
  { label: "답변 근거", value: "인용 필수", note: "모든 답변에 출처 인용, 품질 평가로 추적" },
  { label: "배포 환경", value: "온프레미스", note: "폐쇄망 / 자체 호스팅" },
];

// 실제로 구현되어 CI로 검증되는 기능 목록(권한 범위 내 RAG 질의응답 전 구간).
// "구현됨"은 코드가 동작함을 뜻할 뿐 파일럿 가동을 뜻하지 않는다 — 파일럿 참여
// 여부는 별도 조직 결정(SSO 연동, 실 문서 승인 등)이다. docs/40-delivery/current-state.md 참고.
const workstreams = [
  { name: "지식 문서 & 문서별 ACL", status: "구현됨" },
  { name: "에이전트 등록 & 버전 관리", status: "구현됨" },
  { name: "실행 기록 & 검색 추적", status: "구현됨" },
  { name: "품질 평가 이력", status: "구현됨" },
  { name: "감사 로그", status: "구현됨" },
];

export default function Home() {
  return (
    <section className="page">
      <div className="header">
        <div>
          <p className="eyebrow">파일럿 안내</p>
          <h1>사내 문서로 답하는 에이전트, 부서에서 직접 만들고 운영합니다</h1>
          <p>
            질문에 답하기 전에 권한부터 확인합니다 — 권한이 없는 문서는 애초에
            검색되지 않고, 모든 답변에는 근거 문서가 인용되며, 실행 기록과 감사
            로그가 남습니다.
          </p>
          <p className="note">
            현재 로그인은 실제 SSO가 아니라 데모용 헤더로 사용자를 지정하는
            방식입니다. 서버측 권한 검사는 실제로 동작하지만, 신원 자체는
            클라이언트가 주장하는 구조입니다 — 파일럿 전 SSO 연동이 필요합니다.
          </p>
        </div>
        <div className="buttonRow">
          <Link className="button" href="/agents">
            에이전트
          </Link>
          <Link className="button secondary" href="/knowledge">
            지식
          </Link>
        </div>
      </div>

      <div className="statGrid">
        {stats.map((item) => (
          <div className="stat" key={item.label}>
            <strong>{item.value}</strong>
            <h3>{item.label}</h3>
            <p>{item.note}</p>
          </div>
        ))}
      </div>

      <section className="panel">
        <h2>제공 기능</h2>
        <ul className="statusList">
          {workstreams.map((item) => (
            <li key={item.name}>
              <span>{item.name}</span>
              <span className={item.status === "계획됨" ? "badge warn" : "badge success"}>
                {item.status}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
