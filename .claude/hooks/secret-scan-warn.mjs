#!/usr/bin/env node
/**
 * PostToolUse hook — crude secret scan. WARNS ONLY, never blocks.
 *
 * Contract (Claude Code PostToolUse hooks):
 *   exit 0  -> silent, nothing shown.
 *   exit 1  -> non-blocking: stderr is shown to the user, work continues.
 *   exit 2  -> blocking (NOT used here on purpose — this hook must never
 *              block; it exists only to surface a human-visible warning).
 *
 * FAIL-OPEN: any error anywhere in this script must fall through to exit 0.
 * The tool call has already executed by the time PostToolUse fires, so this
 * hook cannot undo it anyway — its only job is to make a likely credential
 * leak visible, not to gate anything.
 */

const PATTERNS = [
  { name: "AWS Access Key ID", re: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: "GitHub token", re: /\bgh[pousr]_[A-Za-z0-9]{36,}\b/ },
  { name: "Slack token", re: /\bxox[baprs]-[0-9A-Za-z-]{10,}\b/ },
  { name: "Private key block", re: /-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----/ },
  { name: "Bearer token", re: /\bBearer\s+[A-Za-z0-9\-_.]{20,}\b/ },
  {
    name: "Generic secret assignment",
    re: /\b(api[_-]?key|secret|password|passwd|access[_-]?token)\b\s*[=:]\s*['"]?[A-Za-z0-9_\-/+]{8,}['"]?/i,
  },
];

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", () => resolve(data));
    setTimeout(() => resolve(data), 2000);
  });
}

function redactedPreview(match) {
  const s = String(match);
  return s.length <= 6 ? "***" : `${s.slice(0, 4)}***(redacted, ${s.length} chars)`;
}

async function main() {
  const raw = await readStdin();
  if (!raw || !raw.trim()) return exitClean();

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return exitClean();
  }

  const toolName = payload.tool_name || payload.toolName;
  if (typeof toolName !== "string") return exitClean();
  if (!/^(bash|powershell)$/i.test(toolName)) return exitClean();

  const toolInput = payload.tool_input || payload.toolArgs || {};
  const toolResponse = payload.tool_response ?? payload.toolResponse ?? "";

  const haystacks = [];
  if (typeof toolInput.command === "string") haystacks.push(toolInput.command);
  try {
    haystacks.push(typeof toolResponse === "string" ? toolResponse : JSON.stringify(toolResponse));
  } catch {
    // ignore, not fatal
  }
  const text = haystacks.join("\n");
  if (!text) return exitClean();

  const findings = [];
  for (const { name, re } of PATTERNS) {
    const m = text.match(re);
    if (m) findings.push(`${name}: ${redactedPreview(m[0])}`);
  }

  if (findings.length === 0) return exitClean();

  process.stderr.write(
    "WARNING: this command's input/output looks like it may contain a credential " +
      "(crude pattern match, may be a false positive):\n" +
      findings.map((f) => `  - ${f}`).join("\n") +
      "\nIf real, rotate it and avoid printing secrets in commands, logs, or files.\n"
  );
  process.exit(1);
}

function exitClean() {
  process.exit(0);
}

main().catch(() => {
  exitClean();
});
