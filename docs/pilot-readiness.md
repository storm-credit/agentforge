# Pilot Readiness

Agent Forge MVP 파일럿은 실제 부서와 문서를 확정하기 전에도 준비할 수 있다. 이 문서는 파일럿 부서 선정, 샘플 문서 구성, 문서 소유자 지정, 권한 테스트 준비를 위한 공식 체크리스트다.

## 1. Recommended Pilot Candidates

| Priority | Candidate | Why it fits | Key prerequisite |
|---|---|---|---|
| 1 | Security / privacy policy Q&A | Best for ACL, citation, audit validation | Security document owner and sensitive-document exclusion rules |
| 2 | HR / general affairs manual Q&A | Clear repetitive-question reduction value | Current manuals and non-sensitive examples |
| 3 | IT operations procedure Q&A | Strong search value for internal procedures | Current runbooks and deprecated-document cleanup |

## 2. Selection Criteria

The first pilot should meet these conditions:

- One primary document owner and one backup owner are named.
- 50 or more candidate documents can be listed.
- At least two file formats are available among PDF, DOCX, XLSX, TXT, and Markdown.
- Allowed and blocked test users can be prepared.
- The document owner can provide at least 30 evaluation questions.
- Confidential and personal-data-heavy documents can be excluded from MVP.

## 3. Sample Document Mix

| Document group | Target count | Examples | Default level |
|---|---:|---|---|
| Policies and rules | 10~30 | Security policy, privacy standard, travel expense rule | Internal / restricted |
| Work manuals | 20~80 | Request process, approval process, incident guide | Internal |
| FAQ and notices | 10~50 | Repeated questions, change notices, user guides | Public / internal |
| Forms and templates | 5~20 | Request forms, checklists, spreadsheets | Internal |
| Exceptions and appendices | 5~20 | Exception handling, contact table, escalation path | Internal / restricted |

MVP can start development with a synthetic corpus, but the pilot should lock at least 30 approved real documents before the first end-to-end evaluation.

## 4. Document Inventory Template

| ID | Title | Owner department | Owner | Format | Level | Access group | Version/effective date | Status |
|---|---|---|---|---|---|---|---|---|
| DOC-001 |  |  |  | PDF | Internal |  |  | Candidate |
| DOC-002 |  |  |  | DOCX | Internal |  |  | Candidate |
| DOC-003 |  |  |  | XLSX | Restricted |  |  | Candidate |

Allowed status values:

- Candidate
- Under review
- Approved
- Excluded
- Needs replacement

## 5. Required Test Accounts

| Account type | Purpose | Expected behavior |
|---|---|---|
| All-employee user | Public/internal document access | Can retrieve allowed public/internal documents |
| Pilot-department user | Department restricted access | Can retrieve department-specific documents |
| Other-department user | ACL blocking | Restricted documents never appear in retrieval, answer, or citation |
| Admin user | Document and ACL management | Changes create audit events |
| Audit viewer | Trace review | Can inspect run/audit data without excessive raw sensitive content |

## 6. Week-1 Decisions

| Decision | Recommended outcome |
|---|---|
| Pilot department | Choose the department that can provide documents fastest |
| Document owner | Name one owner and one backup |
| Document levels | Use public/internal/restricted/confidential, with confidential excluded from MVP |
| Evaluation set size | Start with 30 questions, expand to 50 before pilot |
| Pilot users | Admin plus 5 pilot users for the 8-week demo |

## 7. Go Criteria

The project can move into pilot execution when:

- The pilot department is named.
- The document owner approves the first 30 documents.
- ACL mapping is available for test users.
- Evaluation questions include factual, procedural, exception, and denied-access cases.
- Security agrees on audit log retention and masking rules.
