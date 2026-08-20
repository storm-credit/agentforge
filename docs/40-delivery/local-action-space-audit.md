# Local Action Space 감사 — 2026-08-20

Status: 감사 기록 (CLAUDE.md 7-d의 근거)
기준: 하나의 reasoning node가 **한 번에 직접 고를 수 있는** Agent·Tool·Skill·MCP·기타 callable의 합 ≤ 5
방법: `.claude/agents/*.md`의 `tools:` 선언을 실측 + 이 저장소에서의 **실제 사용 이력**으로 필요성 판정

> **라우터는 하나로 센다.** `Agent`·`Skill`·`ToolSearch`처럼 다수를 뒤에 두고 **하나로 노출되는**
> 호출은 선택지를 늘리지 않고 줄인다. 라우터를 없애 뒤의 것들을 직접 노출하는 방향의 "정리"는
> 이 기준을 위반한다.

## 1. 감사 결과

| 노드 | 이전 | 이후 | 판정 |
|---|---|---|---|
| `backend-specialist` | 7 — Read, Grep, Glob, Bash, Edit, Write, WebSearch | **5** — Read, Grep, Bash, Edit, Write | **PASS** |
| `frontend-specialist` | 6 — Read, Grep, Glob, Bash, Edit, Write | **5** — Read, Grep, Bash, Edit, Write | **PASS** |
| `infra-ci-specialist` | 6 — Read, Grep, Glob, Bash, Edit, Write | **5** — Read, Grep, Bash, Edit, Write | **PASS** |
| `security-reviewer` | 9 — Read, Grep, Glob, Bash, Edit, Write, WebSearch, WebFetch, Skill | **6** — Read, Grep, Bash, Edit, Write, Skill | **REVIEW** |
| 오케스트레이터(main loop) | 내장 도구 16 + 라우터 4 | 변경 불가 | **REVIEW (프로젝트 측 레버 없음)** |

**`Read + Grep + Bash + Edit + Write = 5`가 "코드를 고치고 검증하는" 노드의 기약 최소 집합**이고,
정확히 기준선에 닿는다. 구현 노드 3개는 이 집합으로 수렴했다.

## 2. 제거 근거 (실제 사용 이력 기반, 추측 아님)

- **`Glob` 제거 (4개 노드)** — `Grep`(`pattern: "."` + `glob:`)이 대체한다. `.gitignore`를 존중하므로
  라이브 파일만 반환한다. 역할 계약(`specialists.yaml`) 4개 어디에도 `Glob` 요구가 없다(각 0건).

  > **독립 Critic이 잡은 정정 (2026-08-20).** 최초 근거는 *"`Bash find`도 있다"* 였고 **그것은
  > 틀렸다.** 이 저장소는 `.claude/worktrees/`에 `apps/web`·`apps/api`의 스테일 사본을 쌓는데,
  > `find`는 그 사본을 **라이브 파일보다 먼저** 반환한다. 즉 에이전트가 첫 결과를 편집하면
  > 버려진 사본에 쓰고도 오류 없이 성공한다 — 조용한 오대상 쓰기다. 측정 당시
  > `find . -name page.tsx -path "*audit*"`가 4건을 반환했고 라이브 파일은 **마지막**이었다.
  >
  > 두 가지로 조치했다: (1) 고아 워크트리 디렉토리 3개를 삭제해 원인을 제거했고(삭제 후 같은
  > `find`가 1건만 반환), (2) 워크트리는 계속 새로 생기므로 4개 에이전트 정의와 CLAUDE.md 7-d에
  > **이름으로 찾을 때는 `Grep`을 쓰고, `find`를 쓸 경우 `worktrees`·`node_modules`·`.venv`를
  > 제외하라**는 지침을 넣었다.
- **`WebSearch` 제거 (`backend-specialist`)** — 백엔드 구현 슬라이스에서 사용된 이력이 없다.
  OSS 선례 조사·라이브러리 서베이는 실제로 전용 리서치 노드에 배정되어 왔다.
- **`WebSearch`·`WebFetch` 제거 (`security-reviewer`)** — CVE 조회 1회가 유일한 사용례였고,
  `Bash`(curl)로 대체 가능하다. 외부 증거 수집은 리서치 노드로 분리하는 것이 경계상 맞다.

**제거하지 않은 것과 이유**: `Edit`·`Write`를 `security-reviewer`에서 빼지 않았다. 이 저장소에서
보안 노드는 리뷰뿐 아니라 **인가 수정을 직접 구현**해 왔고(#141·#150·#155·#157), 그 이력이
효과적이었다. 도구를 빼면 그 능력이 사라진다.

## 3. `security-reviewer`가 6인 이유와 권고

6개 중 `Skill`은 **라우터**다 — `threat-modeling` 절차를 하나의 호출 뒤에 둔다. 즉 실효 분기는
도구 5 + 라우터 1이다.

그럼에도 **REVIEW로 남긴다**: 이 노드는 *리뷰*와 *구현*이라는 서로 다른 책임을 겸하고 있고,
그것이 6이 된 근본 원인이다. OS §3의 "unrelated responsibilities mixed"에 해당한다.

**권고(이번 패스에서 실행하지 않음)**: 역할을 분리해 read-only 리뷰 노드(Read, Grep, Bash, Skill = 4)와
인가 구현 노드(Read, Grep, Bash, Edit, Write = 5)로 나누면 둘 다 PASS가 된다. 실행하지 않은 이유는
모든 보안 슬라이스의 배정 방식이 바뀌는 변경이고, 이번 채택의 원칙이 **최소 수정**이기 때문이다.
사용자 결정 사항으로 남긴다.

## 4. 오케스트레이터 노드

main loop의 직접 도구는 16개이지만 그중 `Agent`·`Skill`·`ToolSearch`·`Workflow`가 **라우터**로,
각각 에이전트 타입·스킬·지연 도구·오케스트레이션을 하나의 호출 뒤에 둔다. 이 목록은 하네스가
정하며 프로젝트 설정으로 줄일 수 없다. **프로젝트 측 레버가 없으므로 REVIEW로 기록하고 넘어간다.**

실효적 완화는 이미 작동하고 있다: 라우터가 다수를 하나로 접고, 지연 도구는 기본 미노출이며,
서브에이전트 브리핑이 각 노드의 허용 행동을 명시적으로 좁힌다.

## 5. 건드리지 않은 것

- `harness/agents/specialists.yaml`의 역할 계약 10개 — 정본이고, `.claude/agents/*.md`가 **복사하지
  않고 참조**하는 구조가 드리프트를 막고 있다. 유지.
- `harness/skills/` 7개, `harness/policies|registries|schemas` — 선언 상태와 배선 격차는
  `harness/tools/project_status.py`가 매번 계산해 보고한다. 이 감사의 범위가 아니다.
- 훅 2개(`block-main-push`·`secret-scan-warn`), CI 3잡, 브랜치 보호 — 실행 가능한 게이트. 유지.
- 제품 코드·마이그레이션·Work Order·SSOT — 일절 변경 없음.

## 6. 프리즈 근거 (§7-11)

이 변경은 SSOT §7의 11번 항목 *"bounded harness enforcement ... **when separately accepted** and not
used to disguise product feature work"*에 해당한다. 제품 코드 변경이 0이고, 사용자가 이 채택을
직접 지시했다(2026-08-20). 별도 Work Order 산출물은 만들지 않았다 — 프리즈 기간 중 같은 성격의
변경이 Work Order 없이 머지된 선례가 일관된다(`23394a4`·`d6bbb08`·`c8e195a`·`af7590d`·`5d66d77`).

> **최초 근거를 정정한다.** 처음에는 *"§8은 Product Runtime 범위 목록이므로 하네스 편집은
> 해당 없음"*이라고 적었다. **텍스트상 틀렸다** — §8에는 프로세스 범위 항목이 실제로 있다
> (*"repeated expert-panel/nit work…"*, *"broad rewrite…"*, *"general platform breadth…"*).
> 카테고리로 배제할 수 없으므로 그 논거는 폐기하고, 위의 §7-11 + §1(CLAUDE.md를 하위 실행규칙으로
> 분류) + 선례로 근거를 교체한다.

## 7. 재확인 방법

```
for f in .claude/agents/*.md; do
  grep -m1 '^tools:' "$f" | sed 's/tools: //' | tr ',' '\n' | grep -c .
done
```

관련: [CLAUDE.md](../../CLAUDE.md) 7-c·7-d · [current-state.md](current-state.md)
