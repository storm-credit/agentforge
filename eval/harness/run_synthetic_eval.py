from __future__ import annotations

import json
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_ROOT.parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.corpus import load_corpus  # noqa: E402
from agentforge_eval.scorer import score_corpus  # noqa: E402


def main() -> int:
    corpus_path = REPO_ROOT / "eval" / "synthetic-corpus" / "cases-v0.1.json"
    corpus = load_corpus(corpus_path)
    report = score_corpus(corpus)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

