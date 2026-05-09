# Open Design 활용 검토

## 결론

활용 가능하다. 다만 MVP 런타임에 바로 넣는 것이 아니라, 우선은 Agent Studio 화면 설계와 디자인 시스템 초안 작성을 돕는 `sidecar design accelerator`로 쓰는 것이 안전하다.

## 왜 맞는가

Open Design의 구조는 Agent Forge와 닮아 있다.

- skill 기반으로 작업 유형을 고른다.
- design system을 파일로 관리한다.
- agent가 산출물을 만들고 preview한다.
- checklist와 critique로 품질을 잡는다.
- Codex 같은 coding-agent CLI를 활용할 수 있다.
- local-first/BYOK 방향이라 사내망 전략과 비교적 잘 맞는다.

## 활용 후보

| 영역 | 활용 방식 |
|---|---|
| Agent Studio | Agents, Knowledge, Eval, Audit 화면 prototype |
| 디자인 시스템 | 내부 업무용 UI token, component rule, anti-pattern 정리 |
| 데모 자료 | 제안서, pitch deck, dashboard mockup |
| Frontend QA | 시각 품질, 접근성, 정보 밀도 체크리스트 참고 |

## 금지선

- 실제 사내 문서, 개인정보, 비공개 업무 데이터를 넣지 않는다.
- 라이선스 검토 없이 코드나 디자인 시스템을 복사하지 않는다.
- MVP의 필수 runtime dependency로 두지 않는다.
- 결과물을 그대로 production UI로 자동 채택하지 않는다.

## 다음 액션

1. synthetic data만 사용해 Agent Studio prototype 1개를 만든다.
2. Agent Forge 전용 design system 초안을 만든다.
3. 보안/라이선스/네트워크 호출 검토 후 채택 범위를 다시 결정한다.

