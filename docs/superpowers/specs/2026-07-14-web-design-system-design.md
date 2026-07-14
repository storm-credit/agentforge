# apps/web 경량 디자인 시스템 — 설계 (2026-07-14)

## 목적
기능·보안·RBAC가 완료된 내부 관리도구의 프론트(apps/web)가 시각적으로 밋밋함(인라인 하드코딩 hex 산재, 디자인 시스템 부재, 다크모드 없음). **가독성·가시성·심미성**을 올리되, 기능/동작/테스트는 100% 보존한다. 사용자 확정 방향: **경량 디자인 시스템(전체 적용) · 클린 미니멀 엔터프라이즈 · 라이트+다크**.

## 비목표 (YAGNI)
- JS 컴포넌트 라이브러리(shadcn/Radix) 도입 안 함.
- CSS 프레임워크(Tailwind 등) 도입 안 함 — 빌드/의존성 변경 최소.
- 새 페이지·새 기능·과한 애니메이션 없음.
- 백엔드/API 변경 없음 (순수 프론트 프레젠테이션 레이어).

## 아키텍처

### 1. 디자인 토큰 (CSS 커스텀 프로퍼티, `apps/web/app/globals.css`)
색상은 **의미 기반 토큰**으로 정의하고 라이트/다크 두 세트를 둔다. 기본은 `prefers-color-scheme` 추종, `<html data-theme="light|dark">`가 있으면 그것이 우선.

```
:root {                      /* light (default) */
  --bg, --surface, --surface-2, --border,
  --text, --text-muted,
  --accent, --accent-hover, --accent-contrast,
  --success, --warn, --danger, --info,
  --space-1..6 (4/8/12/16/24/32),
  --radius-sm/md, --shadow-sm/md, --focus-ring,
  --font-sans, --text-xs/sm/base/lg/xl, --weight-normal/medium/semibold, --leading
}
@media (prefers-color-scheme: dark) { :root { /* dark overrides for color tokens only */ } }
:root[data-theme="light"] { /* force light */ }
:root[data-theme="dark"]  { /* force dark  */ }
```
- 팔레트: 중립 그레이 스케일 + **단일 액센트색**(차분한 블루 계열, 절제). 시맨틱색은 배지/상태용.
- 다크는 색 토큰만 재정의 — 간격/타이포/컴포넌트 규칙은 공유.
- 대비: 본문 텍스트/배경은 WCAG AA(4.5:1) 목표, 라이트·다크 둘 다 확인.

### 2. 공용 컴포넌트 클래스 (globals.css, 손수 작성 CSS)
기존 className 관례(`.panel/.card/.button/.badge/.field/.eyebrow/.statusList/.buttonRow`)를 **토큰 기반으로 재작성 + 정제**하고, 부족한 것 추가:
- `.button` (+ `.secondary`, 크기 변형), 명확한 hover/active/disabled/focus-visible.
- `.badge` (+ `.success/.warn/.danger/.info` 시맨틱 변형) — 기존 `.badge.warn` 유지.
- 인풋/셀렉트/textarea(`.field`) 일관 스타일 + focus-ring + 다크 대응.
- `.table` (헤더/행/구분선 — Runs·Eval·Audit·Knowledge의 인라인 테이블 스타일 대체).
- 사이드바/네비 활성 상태, 헤딩/`.eyebrow`, 에러 텍스트/`.role-restricted-note` 등.

### 3. 인라인 스타일 치환
`style={{ color: "#b91c1c" }}`, `style={{ padding: "6px 8px" }}` 등 산재한 인라인 하드코딩을 토큰 클래스/토큰 var로 치환. 레이아웃용 일회성 인라인(flex gap 등)은 남겨도 되나 색/여백 하드코딩은 토큰화.
- 대상 파일(현재까지 파악): `app/globals.css`, `app/layout.tsx`, `app/knowledge/page.tsx`, `app/runs/page.tsx`, `app/audit/page.tsx`, `app/eval/page.tsx`, `app/agents/page.tsx`, `app/agents/[id]/page.tsx`, `app/agents/new/page.tsx`, `app/chat/page.tsx`, `app/components/RoleSwitcher.tsx` — 착수 시 전체 재확인.

### 4. 다크모드 토글
사이드바(layout.tsx)에 기존 `RoleSwitcher`와 동일 패턴의 `ThemeSwitcher` 추가:
- `<html>`의 `data-theme`를 `light|dark|system`으로 설정, localStorage 저장.
- SSR/hydration 안전: 초기 렌더는 `system`(토큰 기본값=prefers-color-scheme)로 시작하고, 마운트 후 저장값 반영(기존 useDemoRole/RoleSwitcher가 쓰는 것과 동일한 mount-후-반영 패턴).
- FOUC 최소화: 필요 시 layout에 인라인 스크립트로 초기 data-theme 선반영(작게, 선택).

### 5. 폰트
**Pretendard**를 self-host(next/font local 또는 정적 파일)로 번들 — 한글 클린 엔터프라이즈 표준, "이쁨" 체감↑. `--font-sans`에 Pretendard → 시스템 스택 폴백. 웹폰트 라이선스(OFL) 확인.

## 데이터 흐름 / 상호작용
순수 프레젠테이션. 상태·페치·라우팅 로직 무변경. 테마 토글만 새 클라이언트 상태(localStorage).

## 에러/엣지
- 기존 에러 상태(`ask-error`, `role-restricted-note`, 각 페이지 error 텍스트)는 `--danger` 토큰으로 테마 대응해 보존.
- 다크에서 배지/에러 대비 확인.

## 테스트 & 회귀 안전장치 (핵심)
- **모든 `data-testid`·표시 텍스트·DOM 구조·동작을 보존** — CI의 21개 Playwright e2e가 testid/텍스트로 검증하므로, 순수 토큰/클래스 치환이면 그린 유지(스타일 정확값은 검증 안 함). **이게 이 슬라이스의 가장 중요한 불변식.**
- `tsc --noEmit` 클린 유지.
- CI e2e(PR #97) 그린으로 회귀 자동 확인. 로컬 Docker 다운 시 route-mock 스펙 + tsc로 보완하고 실 CI 결과를 최종 근거로 삼음(정직 명시).
- 라이트/다크 각각 주요 페이지 시각 확인(스크린샷 1회) — Docker 복구 후.

## 범위/분할
단일 슬라이스로 진행하되, 파일 수가 많아 리스크가 크면 (a) globals.css 토큰+공용클래스 먼저, (b) 페이지별 치환 순차의 2단계로 나눌 수 있음. 각 단계 후 tsc/e2e 확인.

## 구현 배정
CLAUDE.md 2-d 대전제에 따라 **프론트 전문가 서브에이전트에 딥 브리핑으로 배정**(모델: Fable). PR 오픈까지만, 오케스트레이터가 리뷰(testid 보존·대비·다크 확인)+머지. 세션 사용량 한도 리셋(06:00 KST) 후 디스패치.
