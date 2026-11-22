#!/usr/bin/env python3
"""Second brain test: does Claude Code need an Obsidian-style vault?

Arms
  none    auto memory OFF, no vault          (control: code + git only)
  native  auto memory ON,  no vault          (Claude's built-in memory)
  vault   auto memory OFF, Markdown vault    (Obsidian-style second brain)
  native_rules  auto memory ON + the same save-everything rules as the vault arm,
                pointed at Claude's own memory (separates "vault" from "instructions")

Each trial: copy a fresh fixture per arm, run the teaching sessions one by one
(every session is a new `claude -p` process, so nothing carries over except
memory files, the vault and the code itself), then ask probe questions in fresh
sessions and grade the answers.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ["none", "native", "vault", "native_rules"]


def sh(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_repo(src, dst, name=None):
    if src:
        shutil.copytree(src, dst)
    else:
        dst.mkdir(parents=True)
        (dst / "README.md").write_text(f"# {name}\nA small static website for the label.\n")
        (dst / "package.json").write_text(json.dumps({"name": name, "version": "0.1.0"}, indent=2))
    sh(["git", "init", "-q"], dst)
    sh(["git", "add", "-A"], dst)
    sh(["git", "-c", "user.email=t@t", "-c", "user.name=test", "commit", "-qm", "init"], dst)


def setup_arm(base, arm):
    base.mkdir(parents=True)
    project, other = base / "release-tracker", base / "label-site"
    make_repo(HERE / "fixture", project)
    make_repo(None, other, "label-site")
    shutil.copytree(HERE / "inputs", base / "inputs")
    vault, tpl = None, None
    if arm == "native_rules":
        tpl = (HERE / "templates" / "native-rules-CLAUDE.md").read_text()
    if arm == "vault":
        vault = base / "vault"
        (vault / "notes").mkdir(parents=True)
        (vault / "sources").mkdir()
        (vault / "index.md").write_text("# Vault index\n")
        tpl = (HERE / "templates" / "vault-CLAUDE.md").read_text().replace("{VAULT}", str(vault))
    if tpl:
        for repo in (project, other):
            (repo / "CLAUDE.md").write_text(tpl)
            sh(["git", "add", "-A"], repo)
            sh(["git", "-c", "user.email=t@t", "-c", "user.name=test", "commit", "-qm", "rules"], repo)
    return project, other, base / "inputs", vault


def arm_env(arm):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)
    if arm in ("none", "vault"):
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    return env


def call(claude, prompt, cwd, env, model, add_dirs, read_only):
    cmd = claude + ["-p", prompt, "--output-format", "json", "--model", model]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    if read_only:
        cmd += ["--allowedTools", "Read,Glob,Grep", "--disallowedTools", "Edit,Write,Bash"]
    else:
        cmd += ["--permission-mode", "acceptEdits"]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
    wall = time.time() - t0
    try:
        j = json.loads(p.stdout)
    except json.JSONDecodeError:
        j = {"is_error": True, "result": (p.stdout + p.stderr)[-500:]}
    u = j.get("usage", {}) or {}
    return {
        "result": (j.get("result") or "").strip(),
        "is_error": bool(j.get("is_error")),
        "input_tokens": (u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                         + u.get("cache_read_input_tokens", 0)),
        "output_tokens": u.get("output_tokens", 0),
        "cost_usd": j.get("total_cost_usd", 0) or 0,
        "turns": j.get("num_turns", 0),
        "denials": len(j.get("permission_denials", []) or []),
        "seconds": round(wall, 1),
    }


def grade(answer, probe):
    a = answer.strip()
    if any(re.search(r, a, re.I) for r in probe["pass"]):
        return "PASS"
    if re.fullmatch(r"\W*UNKNOWN\W*", a, re.I) or "unknown" in a.lower()[:40]:
        return "UNKNOWN"
    if any(re.search(r, a, re.I) for r in probe.get("stale", [])):
        return "STALE"
    return "FAIL"


def dir_stats(paths):
    files = [f for p in paths for f in Path(p).rglob("*.md") if f.is_file()]
    return len(files), sum(f.stat().st_size for f in files)


def native_memory_dirs(run_id):
    root = Path.home() / ".claude" / "projects"
    return [d for d in root.glob(f"*{run_id}*")] if root.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--workdir", default=str(Path.home() / "second-brain-test-runs"))
    ap.add_argument("--mock", action="store_true", help="use a fake claude to test the pipeline")
    ap.add_argument("--cleanup", action="store_true", help="(kept for compatibility, memory is now removed after every arm)")
    ap.add_argument("--purge-old", action="store_true", help="delete memory folders left by earlier test runs before starting")
    a = ap.parse_args()

    cfg = json.loads((HERE / "config.json").read_text())
    arms = a.arms.split(",")
    run_id = "sbt" + time.strftime("%Y%m%d%H%M%S")
    out = Path(a.workdir) / run_id
    claude = [sys.executable, str(HERE / "mock_claude.py")] if a.mock else ["claude"]
    rows, sanity = [], []

    stale = native_memory_dirs("sbt20[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]")
    if stale and not a.mock:
        if a.purge_old:
            for d in stale:
                shutil.rmtree(d, ignore_errors=True)
            print(f"Removed {len(stale)} memory folders left by earlier test runs.")
        else:
            sys.exit(f"Found {len(stale)} memory folders from earlier test runs in ~/.claude/projects "
                     "(they can leak answers). Rerun with --purge-old to delete them first.")

    for t in range(1, a.trials + 1):
        for arm in arms:
            base = out / f"t{t}" / arm
            project, other, inputs, vault = setup_arm(base, arm)
            env = arm_env(arm)
            if a.mock:
                env["MOCK_ARM"], env["MOCK_VAULT"] = arm, str(vault or "")
                env["MOCK_MEMDIR"] = str(Path(a.workdir) / "mock-home" / f"{run_id}-t{t}-{arm}")
            extra = [inputs] + ([vault] if vault else [])
            for s in cfg["teaching_sessions"]:
                prompt = s["prompt"].replace("{INPUTS}", str(inputs))
                r = call(claude, prompt, project, env, a.model, extra, read_only=False)
                rows.append({"trial": t, "arm": arm, "step": s["id"], "phase": "teach", **r})
                print(f"t{t} {arm:12} {s['id']:22} {'ERR' if r['is_error'] else 'ok'}  ${r['cost_usd']:.3f}", flush=True)

            # Claude Code turns every non-alphanumeric path character into "-" (native_rules -> native-rules)
            mem = [Path(env["MOCK_MEMDIR"])] if a.mock else native_memory_dirs(re.sub(r"[^A-Za-z0-9]", "-", f"{run_id}/t{t}/{arm}/"))
            mem_n, mem_b = dir_stats(mem) if arm.startswith("native") else (0, 0)
            v_n, v_b = dir_stats([vault]) if vault else (0, 0)
            sanity.append({"trial": t, "arm": arm, "memory_files": mem_n, "memory_bytes": mem_b,
                           "vault_files": v_n, "vault_bytes": v_b})

            for p in cfg["probes"]:
                cwd = project if p["where"] == "project" else other
                prompt = cfg["probe_wrapper"].replace("{QUESTION}", p["question"])
                # probes get the vault but NOT the inputs folder, so outside-doc questions test memory, not file access
                r = call(claude, prompt, cwd, env, a.model, [vault] if vault else [], read_only=True)
                g = grade(r["result"], p) if not r["is_error"] else "ERROR"
                rows.append({"trial": t, "arm": arm, "step": p["id"], "phase": "probe", "grade": g, **r})
                print(f"t{t} {arm:12} {p['id']:22} {g:7}  ${r['cost_usd']:.3f}", flush=True)

            # isolation: keep a copy of what this arm stored, then remove it so no later
            # arm or trial can find it with Glob/Read (this caused a leak in run 2)
            for i, d in enumerate(mem):
                if d.exists():
                    shutil.copytree(d, base / "_saved_memory" / f"{i}_{d.name[-40:]}")
                    if not a.mock:
                        shutil.rmtree(d, ignore_errors=True)
            shutil.make_archive(str(base), "gztar", root_dir=base)
            shutil.rmtree(base)

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps({"rows": rows, "sanity": sanity, "model": a.model,
                                                  "mock": a.mock, "trials": a.trials}, indent=2))
    write_report(out, cfg, rows, sanity, arms, a)
    if a.cleanup and not a.mock:
        for d in native_memory_dirs(run_id):
            shutil.rmtree(d, ignore_errors=True)
    print(f"\nReport: {out / 'report.md'}")


def write_report(out, cfg, rows, sanity, arms, a):
    L = []
    if a.mock:
        L += ["# MOCK RUN - pipeline test only, these numbers are fake", ""]
    else:
        L += ["# Second brain test results", ""]
    L += [f"Model: `{a.model}` - trials: {a.trials} - date: {time.strftime('%Y-%m-%d')}", ""]

    L += ["## Sanity checks (a result is only valid if its arm actually stored something)", "",
          "| trial | arm | memory files | memory KB | vault files | vault KB | valid |", "|---|---|---|---|---|---|---|"]
    for s in sanity:
        ok = {"none": True, "native": s["memory_files"] > 0, "native_rules": s["memory_files"] > 0,
              "vault": s["vault_files"] > 0}[s["arm"]]
        L.append(f"| {s['trial']} | {s['arm']} | {s['memory_files']} | {s['memory_bytes']/1024:.1f} | "
                 f"{s['vault_files']} | {s['vault_bytes']/1024:.1f} | {'yes' if ok else 'NO - check setup'} |")
    errs = [r for r in rows if r["is_error"]]
    denials = sum(r["denials"] for r in rows)
    L += ["", f"Errored calls: {len(errs)} - permission denials: {denials}", ""]

    probes = [r for r in rows if r["phase"] == "probe"]
    L += ["## Recall by probe (PASS count / trials)", "",
          "| probe | kind | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]
    for p in cfg["probes"]:
        cells = []
        for arm in arms:
            rs = [r for r in probes if r["arm"] == arm and r["step"] == p["id"]]
            n = sum(r["grade"] == "PASS" for r in rs)
            stale = sum(r["grade"] == "STALE" for r in rs)
            cells.append(f"{n}/{len(rs)}" + (f" ({stale} stale)" if stale else ""))
        L.append(f"| {p['id']} | {p['kind']} | " + " | ".join(cells) + " |")

    L += ["", "## Totals per arm", "",
          "| arm | recall | avg probe input tokens | teach cost $ | probe cost $ | avg probe seconds |",
          "|---|---|---|---|---|---|"]
    for arm in arms:
        pr = [r for r in probes if r["arm"] == arm]
        te = [r for r in rows if r["arm"] == arm and r["phase"] == "teach"]
        if not pr:
            continue
        acc = sum(r["grade"] == "PASS" for r in pr) / len(pr)
        L.append(f"| {arm} | {acc:.0%} | {sum(r['input_tokens'] for r in pr)/len(pr):,.0f} | "
                 f"{sum(r['cost_usd'] for r in te):.2f} | {sum(r['cost_usd'] for r in pr):.2f} | "
                 f"{sum(r['seconds'] for r in pr)/len(pr):.1f} |")

    L += ["", "## Every answer (review before publishing - regex grading can be wrong)", ""]
    for r in probes:
        L.append(f"- t{r['trial']} **{r['arm']}** `{r['step']}` {r['grade']}: {r['result'][:300]!r}")
    (out / "report.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
