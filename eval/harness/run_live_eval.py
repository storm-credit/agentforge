from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_ROOT.parents[1]
sys.path.insert(0, str(HARNESS_ROOT))

from agentforge_eval.live_runner import run_live_eval  # noqa: E402


def main() -> int:
    corpus_name = os.environ.get("AGENT_FORGE_EVAL_CORPUS", "cases-live-v0.1.json")
    corpus = REPO_ROOT / "eval" / "synthetic-corpus" / corpus_name
    base_url = os.environ.get("AGENT_FORGE_EVAL_BASE_URL", "http://127.0.0.1:8000/api/v1")
    prefix = os.environ.get("AGENT_FORGE_EVAL_PREFIX", "evalrun")
    report = run_live_eval(corpus, base_url=base_url, prefix=prefix)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
