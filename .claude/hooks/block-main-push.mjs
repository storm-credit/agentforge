#!/usr/bin/env node
/**
 * PreToolUse hook — blocks a direct `git push` that would land on a protected
 * branch (main/master) without going through a PR.
 *
 * Contract (Claude Code PreToolUse hooks):
 *   exit 0  -> allow the tool call.
 *   exit 2  -> block the tool call; stderr is fed back as the reason.
 *   other   -> non-blocking error, tool call proceeds, stderr shown to user.
 *
 * FAIL-OPEN IS THE PRIMARY REQUIREMENT: any error while reading input,
 * parsing the command, or inspecting the repo must fall through to exit 0
 * (allow). This hook must never be able to wedge a session. Only an
 * affirmatively-detected direct push to a protected branch blocks.
 */
import { execFileSync } from "node:child_process";

const PROTECTED_BRANCHES = new Set(["main", "master"]);

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", () => resolve(data));
    // If there's no piped stdin at all, don't hang.
    setTimeout(() => resolve(data), 2000);
  });
}

// Split a git-push argument string into tokens, honoring simple quoting.
function tokenize(argsStr) {
  const tokens = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let m;
  while ((m = re.exec(argsStr)) !== null) {
    tokens.push(m[1] ?? m[2] ?? m[3]);
  }
  return tokens;
}

// Given the token list after `git push`, find (remote, refspec).
function parsePushArgs(tokens) {
  const positional = [];
  for (const tok of tokens) {
    if (tok.startsWith("-")) continue; // skip flags like --force, -u, --dry-run
    positional.push(tok);
  }
  const remote = positional[0];
  const refspec = positional[1];
  return { remote, refspec };
}

// Resolve the destination branch name a refspec would land on.
// "main" -> "main"; "HEAD:main" -> "main"; "+feat:main" -> "main"; ":main" -> "main".
function destBranchFromRefspec(refspec) {
  if (!refspec) return undefined;
  let r = refspec.replace(/^\+/, "");
  if (r.includes(":")) {
    r = r.split(":").slice(1).join(":");
  }
  r = r.replace(/^refs\/heads\//, "");
  return r || undefined;
}

function findGitPushInvocations(command) {
  // A command line may chain multiple commands; check each segment
  // independently so we don't miss `cmd1 && git push origin main`.
  const segments = command.split(/&&|\|\||[|;]/);
  const hits = [];
  const pushRe = /\bgit\s+push\b(.*)$/i;
  for (const seg of segments) {
    const m = seg.match(pushRe);
    if (m) hits.push(m[1] || "");
  }
  return hits;
}

async function main() {
  const raw = await readStdin();
  if (!raw || !raw.trim()) return exitAllow();

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return exitAllow();
  }

  const toolName = payload.tool_name || payload.toolName;
  if (typeof toolName !== "string") return exitAllow();
  if (!/^(bash|powershell)$/i.test(toolName)) return exitAllow();

  const toolInput = payload.tool_input || payload.toolArgs || {};
  const command = typeof toolInput.command === "string" ? toolInput.command : undefined;
  if (!command) return exitAllow();

  const pushArgStrings = findGitPushInvocations(command);
  if (pushArgStrings.length === 0) return exitAllow();

  const cwd = typeof payload.cwd === "string" ? payload.cwd : process.cwd();

  for (const argsStr of pushArgStrings) {
    const tokens = tokenize(argsStr);
    const { remote, refspec } = parsePushArgs(tokens);
    let destBranch = destBranchFromRefspec(refspec);

    if (!destBranch) {
      // Bare `git push` or `git push <remote>` with no refspec pushes the
      // current branch. Resolve it; if that fails for any reason, fail open.
      destBranch = safeCurrentBranch(cwd);
    }

    if (destBranch && PROTECTED_BRANCHES.has(destBranch)) {
      return exitBlock(
        `Direct 'git push' to protected branch '${destBranch}' is not allowed.\n` +
          `Matched command: git push${argsStr}\n` +
          `Remote: ${remote ?? "(default)"}\n` +
          `Use a feature branch + PR instead (CLAUDE.md workflow rule: docs-only changes also go through branch+PR).`
      );
    }
  }

  return exitAllow();
}

function safeCurrentBranch(cwd) {
  try {
    const out = execFileSync("git", ["rev-parse", "--abbrev-ref", "HEAD"], {
      cwd,
      encoding: "utf8",
      timeout: 3000,
      windowsHide: true,
    });
    return out.trim();
  } catch {
    return undefined; // fail open: unknown branch -> do not block
  }
}

function exitAllow() {
  process.exit(0);
}

function exitBlock(reason) {
  process.stderr.write(reason + "\n");
  process.exit(2);
}

main().catch(() => {
  // Absolute last-resort fail-open: any unexpected error must not block work.
  exitAllow();
});
