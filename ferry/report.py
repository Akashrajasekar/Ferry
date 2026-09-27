"""ferry/report.py – the `report` command.

Reads .ferry/plan.json, .ferry/results.json, .ferry/ports/*.json,
.ferry/audit.json, metrics.json and produces:
  - docs/index.html  (self-contained, no external requests)
  - results/CHANGELOG-<sanitized-branch>.md per branch
  - results/ferry-state/ (copy of .ferry/)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .gitops import sanitize_branch

REPO_ROOT = Path(__file__).resolve().parent.parent
FERRY_DIR = REPO_ROOT / ".ferry"
DOCS_DIR = REPO_ROOT / "docs"
RESULTS_DIR = REPO_ROOT / "results"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _load_all() -> dict:
    plan = _load_json(FERRY_DIR / "plan.json", {})
    results = _load_json(FERRY_DIR / "results.json", [])
    audit = _load_json(FERRY_DIR / "audit.json", [])
    metrics = _load_json(REPO_ROOT / "metrics.json", {})

    ports: list[dict] = []
    ports_dir = FERRY_DIR / "ports"
    if ports_dir.exists():
        for pf in sorted(ports_dir.glob("*.json")):
            try:
                ports.append(json.loads(pf.read_text(encoding="utf-8")))
            except Exception:
                pass

    return {
        "plan": plan,
        "results": results,
        "audit": audit,
        "metrics": metrics,
        "ports": ports,
    }


# ---------------------------------------------------------------------------
# Changelog generation
# ---------------------------------------------------------------------------

def _write_changelogs(results: list[dict], audit: list[dict]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build subject map from audit
    subject_map = {e["sha"]: e["subject"] for e in audit}

    # Group ported results by branch
    by_branch: dict[str, list[dict]] = {}
    for r in results:
        if r.get("method") in ("clean", "adapted"):
            branch = r["branch"]
            by_branch.setdefault(branch, []).append(r)

    for branch, entries in sorted(by_branch.items()):
        san = sanitize_branch(branch)
        path = RESULTS_DIR / f"CHANGELOG-{san}.md"
        lines = [f"# Changelog for {branch}\n\n"]
        for e in entries:
            sha = e["sha"]
            subject = subject_map.get(sha, "")
            lines.append(f"- {subject} — Backport of {sha}\n")
        path.write_text("".join(lines), encoding="utf-8")
        print(f"    Written {path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# ferry-state copy
# ---------------------------------------------------------------------------

def _copy_ferry_state() -> None:
    dest = RESULTS_DIR / "ferry-state"
    if dest.exists():
        shutil.rmtree(str(dest))
    if FERRY_DIR.exists():
        shutil.copytree(str(FERRY_DIR), str(dest))
        print(f"    Copied .ferry/ to {dest.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def _compute_metrics(data: dict) -> dict:
    results = data["results"]
    audit = data["audit"]
    metrics = data["metrics"]

    fixes_audited = len(audit)
    missing_sec = sum(
        1
        for e in audit
        if e.get("kind") == "security"
        and any(v == "missing" for v in e.get("branches", {}).values())
    )

    proven = sum(1 for r in results if r.get("f2p") and r.get("p2p"))
    clean_ct = sum(1 for r in results if r.get("method") == "clean")
    adapted_ct = sum(1 for r in results if r.get("method") == "adapted")
    escalated_ct = sum(1 for r in results if r.get("method") == "escalated")
    pending_ct = sum(1 for r in results if r.get("method") == "pending")
    review_ct = sum(1 for r in results if r.get("review_required"))

    # Bobcoins
    bc = metrics.get("bobcoins_by_task", {})
    total_bc = sum(bc.values()) if isinstance(bc, dict) else 0
    # T06 coins / number of adapted ports
    t06_bc = bc.get("T06", 0) if isinstance(bc, dict) else 0
    bc_per_adapted = round(t06_bc / adapted_ct, 2) if adapted_ct > 0 else None

    baseline_min = metrics.get("manual_baseline_minutes", None)
    ferry_run_min = metrics.get("ferry_run_minutes", None)

    return {
        "fixes_audited": fixes_audited,
        "missing_security": missing_sec,
        "ports_proven": proven,
        "clean": clean_ct,
        "adapted": adapted_ct,
        "escalated": escalated_ct,
        "pending": pending_ct,
        "review_flags": review_ct,
        "total_bobcoins": round(total_bc, 2),
        "bc_per_adapted": bc_per_adapted,
        "manual_baseline_minutes": baseline_min,
        "ferry_run_minutes": ferry_run_min,
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _escape_json_for_html(obj) -> str:
    """Serialize obj to JSON and escape '</' to prevent script injection."""
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("</", "<\\/")


def _build_html(data: dict) -> str:
    m = _compute_metrics(data)
    results = data["results"]
    plan = data["plan"]
    audit = data["audit"]
    ports = data["ports"]

    # Build port adaptations lookup
    port_lookup: dict[tuple, dict] = {}
    for pf in ports:
        port_lookup[(pf.get("sha", ""), pf.get("branch", ""))] = pf

    # Build result lookup
    result_lookup: dict[tuple, dict] = {}
    for r in results:
        result_lookup[(r["sha"], r["branch"])] = r

    # Collect fixes and branches for matrix
    fix_rows = []
    if plan.get("fixes"):
        for fix in plan["fixes"]:
            sha = fix["sha"]
            subject = fix.get("subject", sha[:7])
            targets = []
            for t in fix.get("targets", []):
                branch = t["branch"]
                key = (sha, branch)
                r = result_lookup.get(key, {})
                targets.append({
                    "branch": branch,
                    "decision": t.get("decision", ""),
                    "reason": t.get("reason", ""),
                    "citation": t.get("citation", {}),
                    "result": r,
                    "port": port_lookup.get(key, {}),
                })
            fix_rows.append({
                "sha": sha,
                "subject": subject,
                "targets": targets,
            })
    else:
        # Fall back to results
        sha_set: dict[str, str] = {}
        for e in audit:
            sha_set[e["sha"]] = e.get("subject", e["sha"][:7])
        for sha, subject in sha_set.items():
            branch_set = [r["branch"] for r in results if r["sha"] == sha]
            targets = []
            for branch in sorted(set(branch_set)):
                key = (sha, branch)
                r = result_lookup.get(key, {})
                targets.append({
                    "branch": branch,
                    "decision": r.get("method", ""),
                    "reason": "",
                    "citation": {},
                    "result": r,
                    "port": port_lookup.get(key, {}),
                })
            fix_rows.append({"sha": sha, "subject": subject, "targets": targets})

    # Collect all branches
    all_branches: list[str] = []
    seen_b: set[str] = set()
    for fix in fix_rows:
        for t in fix["targets"]:
            if t["branch"] not in seen_b:
                all_branches.append(t["branch"])
                seen_b.add(t["branch"])

    ferry_data = {
        "metrics": m,
        "fixes": fix_rows,
        "branches": all_branches,
        "results": results,
        "audit": audit,
    }

    data_json = _escape_json_for_html(ferry_data)

    # Build HTML
    head_and_css = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>Ferry \u2014 every fix, every supported release, proven</title>\n'
        '<style>\n'
        '  :root {\n'
        '    --bg: #ffffff; --surface: #f7f8fa; --border: #e5e7eb;\n'
        '    --text: #1f2328; --muted: #57606a; --accent: #3b82d4;\n'
        '    --green: #22863a; --green-bg: #dcffe4;\n'
        '    --blue: #0366d6; --blue-bg: #ddf4ff;\n'
        '    --amber: #b08800; --amber-bg: #fff8c5;\n'
        '    --grey: #57606a; --grey-bg: #f6f8fa;\n'
        '    --red: #cb2431; --red-bg: #ffeef0;\n'
        '    --purple: #6f42c1; --purple-bg: #f5f0ff;\n'
        '    --font: -apple-system, "Segoe UI", system-ui, sans-serif;\n'
        '  }\n'
        '  @media (prefers-color-scheme: dark) {\n'
        '    :root {\n'
        '      --bg: #0d1117; --surface: #161b22; --border: #30363d;\n'
        '      --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;\n'
        '      --green: #3fb950; --green-bg: #0d2a17;\n'
        '      --blue: #58a6ff; --blue-bg: #051d4d;\n'
        '      --amber: #d29922; --amber-bg: #2d2800;\n'
        '      --grey: #8b949e; --grey-bg: #161b22;\n'
        '      --red: #f85149; --red-bg: #2d0f0f;\n'
        '      --purple: #bc8cff; --purple-bg: #1d1040;\n'
        '    }\n'
        '  }\n'
        '  * { box-sizing: border-box; margin: 0; padding: 0; }\n'
        '  body { font-family: var(--font); font-size: 14px; line-height: 1.6;\n'
        '         background: var(--bg); color: var(--text); overflow-x: hidden; }\n'
        '  a { color: var(--accent); }\n'
        '  .container { max-width: 960px; margin: 0 auto; padding: 24px 16px; }\n'
        '  h1 { font-size: 1.4em; font-weight: 700; margin-bottom: 4px; }\n'
        '  h2 { font-size: 1.05em; font-weight: 600; margin: 24px 0 10px; }\n'
        '  h3 { font-size: 0.95em; font-weight: 600; margin: 14px 0 6px; }\n'
        '  .how-strip { display: flex; flex-wrap: wrap; gap: 0;\n'
        '    background: var(--surface); border: 1px solid var(--border);\n'
        '    border-radius: 6px; padding: 10px 14px; margin: 14px 0;\n'
        '    align-items: center; font-size: 0.82em; color: var(--muted); }\n'
        '  .how-step { white-space: nowrap; }\n'
        '  .how-arrow { padding: 0 6px; color: var(--border); }\n'
        '  .how-step b { color: var(--text); }\n'
        '  .metrics-bar { display: flex; flex-wrap: wrap; gap: 10px;\n'
        '    background: var(--surface); border: 1px solid var(--border);\n'
        '    border-radius: 6px; padding: 14px 16px; margin: 16px 0; }\n'
        '  .metric { display: flex; flex-direction: column; align-items: center;\n'
        '    min-width: 80px; text-align: center; }\n'
        '  .metric-value { font-size: 1.4em; font-weight: 700; color: var(--accent); }\n'
        '  .metric-label { font-size: 0.75em; color: var(--muted); margin-top: 2px; }\n'
        '  .metric-value.red { color: var(--red); }\n'
        '  .metric-value.amber { color: var(--amber); }\n'
        '  .metric-value.green { color: var(--green); }\n'
        '  .matrix-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch;\n'
        '    max-width: 100%; }\n'
        '  table { border-collapse: collapse; white-space: nowrap; }\n'
        '  th, td { border: 1px solid var(--border); padding: 6px 10px;\n'
        '    text-align: left; vertical-align: middle; }\n'
        '  th { background: var(--surface); font-weight: 600; font-size: 0.82em; }\n'
        '  td.fix-cell { max-width: 260px; white-space: normal; }\n'
        '  .cell { cursor: pointer; border-radius: 4px; padding: 3px 8px;\n'
        '    font-size: 0.8em; font-weight: 600; white-space: nowrap;\n'
        '    display: inline-block; transition: opacity 0.1s; position: relative; }\n'
        '  .cell:hover { opacity: 0.8; }\n'
        '  .cell-adapted-proven { background: var(--green-bg); color: var(--green); }\n'
        '  .cell-clean-proven   { background: var(--blue-bg);  color: var(--blue);  }\n'
        '  .cell-escalated { background: var(--amber-bg); color: var(--amber); }\n'
        '  .cell-pending { background: var(--red-bg); color: var(--red); }\n'
        '  .cell-skip { background: var(--grey-bg); color: var(--grey); }\n'
        '  .review-dot { display: inline-block; width: 7px; height: 7px;\n'
        '    border-radius: 50%; background: var(--amber);\n'
        '    margin-left: 4px; vertical-align: middle; }\n'
        '  #details-panel { display: none; position: fixed; right: 0; top: 0; bottom: 0;\n'
        '    width: min(500px, 100vw); overflow-y: auto;\n'
        '    background: var(--bg); border-left: 2px solid var(--border);\n'
        '    padding: 20px 18px; z-index: 100; font-size: 0.88em; }\n'
        '  #details-panel.open { display: block; }\n'
        '  #details-close { float: right; cursor: pointer; font-size: 1.4em;\n'
        '    color: var(--muted); background: none; border: none;\n'
        '    padding: 0; line-height: 1; }\n'
        '  .kv-table { width: 100%; border-collapse: collapse; margin: 6px 0; }\n'
        '  .kv-table td { padding: 3px 6px; border-bottom: 1px solid var(--border); }\n'
        '  .kv-table td:first-child { font-weight: 600; color: var(--muted);\n'
        '    white-space: nowrap; width: 38%; }\n'
        '  .badge { display: inline-block; border-radius: 3px; padding: 1px 6px;\n'
        '    font-size: 0.82em; font-weight: 600; }\n'
        '  .badge-pass { background: var(--green-bg); color: var(--green); }\n'
        '  .badge-fail { background: var(--red-bg);   color: var(--red);   }\n'
        '  .badge-na   { background: var(--grey-bg);  color: var(--grey);  }\n'
        '  .badge-amber { background: var(--amber-bg); color: var(--amber); }\n'
        '  .test-table { width: 100%; border-collapse: collapse; font-size: 0.82em; margin: 6px 0; }\n'
        '  .test-table th { background: var(--surface); font-weight: 600;\n'
        '    border: 1px solid var(--border); padding: 3px 8px; text-align: left; }\n'
        '  .test-table td { border: 1px solid var(--border); padding: 3px 8px; }\n'
        '  pre { background: var(--surface); border: 1px solid var(--border);\n'
        '    border-radius: 4px; padding: 10px; overflow-x: auto;\n'
        '    font-size: 0.76em; line-height: 1.4; white-space: pre;\n'
        '    max-height: 340px; overflow-y: auto; }\n'
        '  .diff-add { color: var(--green); }\n'
        '  .diff-del { color: var(--red); }\n'
        '  .diff-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }\n'
        '  @media (max-width: 640px) { .diff-cols { grid-template-columns: 1fr; } }\n'
        '  .legend { display: flex; flex-wrap: wrap; gap: 10px;\n'
        '    margin: 8px 0 14px; font-size: 0.81em; }\n'
        '  .legend-item { display: flex; align-items: center; gap: 5px; }\n'
        '  .legend-swatch { border-radius: 4px; padding: 2px 7px;\n'
        '    font-size: 0.8em; font-weight: 600; }\n'
        '  .flags-box { background: var(--amber-bg); border: 1px solid var(--amber);\n'
        '    border-radius: 5px; padding: 10px 12px; margin: 10px 0; }\n'
        '  .flags-box-title { font-weight: 700; color: var(--amber); margin-bottom: 6px; }\n'
        '  .flag-item { margin-bottom: 6px; }\n'
        '  .flag-item:last-child { margin-bottom: 0; }\n'
        '  .audit-table { width: 100%; border-collapse: collapse; font-size: 0.84em; }\n'
        '  .audit-table th { background: var(--surface); border: 1px solid var(--border);\n'
        '    padding: 4px 8px; font-weight: 600; }\n'
        '  .audit-table td { border: 1px solid var(--border); padding: 4px 8px; }\n'
        '  footer { margin-top: 40px; padding-top: 14px;\n'
        '    border-top: 1px solid var(--border);\n'
        '    text-align: center; font-size: 11px; color: var(--muted); }\n'
        '</style>\n'
        '</head>\n'
        '<body>\n'
    )

    data_tag = f'<script type="application/json" id="ferry-data">{data_json}</script>\n'

    body_html = (
        '<div class="container">\n'
        '  <h1>Ferry &#8212; every fix, every supported release, proven</h1>\n'
        '  <p style="color:var(--muted);font-size:0.88em;margin-bottom:6px">'
        'Automated backporting with proof: fail&#8209;before &#8594; pass&#8209;after &#8594; full suite</p>\n'
        # How Ferry works strip
        '  <div class="how-strip" id="how-strip">\n'
        '    <span class="how-step"><b>audit</b> reads main for missing fixes</span>\n'
        '    <span class="how-arrow">&#8594;</span>\n'
        '    <span class="how-step"><b>scope</b> reads policy PDF + advisory DOCX</span>\n'
        '    <span class="how-arrow">&#8594;</span>\n'
        '    <span class="how-step"><b>try</b> plain cherry-pick</span>\n'
        '    <span class="how-arrow">&#8594;</span>\n'
        '    <span class="how-step"><b>adapt</b> parallel Bob subagents</span>\n'
        '    <span class="how-arrow">&#8594;</span>\n'
        '    <span class="how-step"><b>verify</b> per-test fail-before / pass-after + full suite</span>\n'
        '    <span class="how-arrow">&#8594;</span>\n'
        '    <span class="how-step"><b>report</b></span>\n'
        '  </div>\n'
        '  <div class="metrics-bar" id="metrics-bar"></div>\n'
        '  <h2>Matrix</h2>\n'
        '  <div class="legend" id="legend"></div>\n'
        '  <div class="matrix-wrap"><table id="matrix-table"></table></div>\n'
        '  <h2 id="missing-fixes-title">Missing fixes found by audit</h2>\n'
        '  <div id="missing-fixes-wrap"></div>\n'
        '  <div id="details-panel">\n'
        '    <button id="details-close" title="Close">&#215;</button>\n'
        '    <div id="details-content"></div>\n'
        '  </div>\n'
        '</div>\n'
        '<footer>Made with IBM Bob</footer>\n'
    )

    js = r"""<script>
(function () {
  "use strict";

  var raw = document.getElementById("ferry-data").textContent;
  var fd = JSON.parse(raw);
  var metrics = fd.metrics;
  var fixes = fd.fixes;
  var branches = fd.branches;
  var auditData = fd.audit || [];

  /* ---- Metrics bar ---- */
  var metricsBar = document.getElementById("metrics-bar");
  function addMetric(value, label, colorClass) {
    var div = document.createElement("div");
    div.className = "metric";
    var val = document.createElement("span");
    val.className = "metric-value" + (colorClass ? " " + colorClass : "");
    val.textContent = value;
    var lbl = document.createElement("span");
    lbl.className = "metric-label";
    lbl.textContent = label;
    div.appendChild(val);
    div.appendChild(lbl);
    metricsBar.appendChild(div);
  }

  addMetric(metrics.fixes_audited, "fixes audited");
  addMetric(
    metrics.missing_security,
    "missing security",
    metrics.missing_security > 0 ? "red" : "green"
  );
  addMetric(metrics.ports_proven, "ports proven", "green");
  addMetric(metrics.clean, "clean");
  addMetric(metrics.adapted, "adapted");
  if (metrics.escalated > 0) {
    addMetric(metrics.escalated, "escalated", "amber");
  }
  if (metrics.review_flags > 0) {
    addMetric(metrics.review_flags, "review flags", "amber");
  }
  addMetric(
    metrics.total_bobcoins !== null && metrics.total_bobcoins !== undefined
      ? metrics.total_bobcoins.toFixed(2)
      : "\u2014",
    "Bobcoins total"
  );
  if (metrics.bc_per_adapted !== null && metrics.bc_per_adapted !== undefined) {
    addMetric(metrics.bc_per_adapted.toFixed(2), "coins/adapted port");
  }
  addMetric(
    metrics.manual_baseline_minutes !== null && metrics.manual_baseline_minutes !== undefined
      ? metrics.manual_baseline_minutes + " min"
      : "\u2014",
    "manual baseline (1 port)"
  );
  if (metrics.ferry_run_minutes !== null && metrics.ferry_run_minutes !== undefined) {
    addMetric(metrics.ferry_run_minutes + " min", "ferry run (all adapted)");
  }

  /* ---- Legend — swatches use same CSS classes as cells ---- */
  var legendDefs = [
    { cls: "cell-adapted-proven", label: "adapted + proven" },
    { cls: "cell-clean-proven",   label: "clean + proven" },
    { cls: "cell-escalated",      label: "escalated" },
    { cls: "cell-pending",        label: "pending" },
    { cls: "cell-skip",           label: "skip / n/a" },
  ];
  var legendEl = document.getElementById("legend");
  legendDefs.forEach(function (item) {
    var wrap = document.createElement("span");
    wrap.className = "legend-item";
    var swatch = document.createElement("span");
    // Use the same class as the cell badge so colors always match
    swatch.className = "legend-swatch " + item.cls;
    swatch.textContent = item.label;
    wrap.appendChild(swatch);
    legendEl.appendChild(wrap);
  });
  // Review marker legend
  var reviewWrap = document.createElement("span");
  reviewWrap.className = "legend-item";
  var reviewDot = document.createElement("span");
  reviewDot.className = "review-dot";
  reviewWrap.appendChild(reviewDot);
  reviewWrap.appendChild(document.createTextNode(" review required"));
  legendEl.appendChild(reviewWrap);

  /* ---- Cell class ---- */
  function cellClass(target) {
    var r = target.result || {};
    var method = r.method || target.decision || "";
    if (method === "skip" || method === "not_applicable" || method === "skipped") {
      return "cell-skip";
    }
    if (method === "escalated") { return "cell-escalated"; }
    if (method === "pending")   { return "cell-pending"; }
    if (method === "clean" && r.f2p && r.p2p) { return "cell-clean-proven"; }
    if (method === "adapted" && r.f2p && r.p2p) { return "cell-adapted-proven"; }
    if (method === "clean" || method === "adapted") {
      return "cell-pending";
    }
    return "cell-skip";
  }

  function cellLabel(target) {
    var r = target.result || {};
    var method = r.method || target.decision || "";
    if (method === "skip" || method === "skipped") { return "skip"; }
    if (method === "not_applicable") { return "n/a"; }
    if (method === "escalated") { return "escalated"; }
    if (method === "pending") { return "pending"; }
    if (method === "clean" && r.f2p && r.p2p) { return "clean + proven"; }
    if (method === "adapted" && r.f2p && r.p2p) { return "adapted + proven"; }
    if (method === "clean" || method === "adapted") {
      return "fail (f2p=" + (r.f2p ? "T" : "F") + " p2p=" + (r.p2p ? "T" : "F") + ")";
    }
    return method || "?";
  }

  /* ---- Matrix ---- */
  var table = document.getElementById("matrix-table");
  var thead = document.createElement("thead");
  var hrow = document.createElement("tr");
  var thFix = document.createElement("th");
  thFix.textContent = "Fix";
  hrow.appendChild(thFix);
  branches.forEach(function (b) {
    var th = document.createElement("th");
    th.textContent = b;
    hrow.appendChild(th);
  });
  thead.appendChild(hrow);
  table.appendChild(thead);

  var tbody = document.createElement("tbody");

  fixes.forEach(function (fix) {
    var tr = document.createElement("tr");
    var tdFix = document.createElement("td");
    tdFix.className = "fix-cell";
    var shortEl = document.createElement("code");
    shortEl.textContent = fix.sha.slice(0, 7);
    tdFix.appendChild(shortEl);
    tdFix.appendChild(document.createTextNode(" "));
    var subj = document.createElement("span");
    subj.style.color = "var(--muted)";
    subj.style.fontSize = "0.88em";
    subj.textContent = fix.subject.length > 52
      ? fix.subject.slice(0, 52) + "\u2026"
      : fix.subject;
    tdFix.appendChild(subj);
    tr.appendChild(tdFix);

    var targetsByBranch = {};
    (fix.targets || []).forEach(function (t) { targetsByBranch[t.branch] = t; });

    branches.forEach(function (b) {
      var td = document.createElement("td");
      var target = targetsByBranch[b];
      if (target) {
        var cell = document.createElement("span");
        cell.className = "cell " + cellClass(target);
        cell.textContent = cellLabel(target);
        cell.setAttribute("tabindex", "0");
        cell.setAttribute("role", "button");
        // Review marker dot
        var r = target.result || {};
        if (r.review_required) {
          var dot = document.createElement("span");
          dot.className = "review-dot";
          dot.title = "Review required";
          cell.appendChild(dot);
        }
        cell.addEventListener("click", function () { showDetails(fix, target); });
        cell.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { showDetails(fix, target); }
        });
        td.appendChild(cell);
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  /* ---- Missing fixes audit section ---- */
  var mfWrap = document.getElementById("missing-fixes-wrap");
  var missingFixes = auditData.filter(function (e) {
    return Object.values(e.branches || {}).some(function (v) { return v === "missing"; });
  });
  if (missingFixes.length === 0) {
    document.getElementById("missing-fixes-title").style.display = "none";
    mfWrap.style.display = "none";
  } else {
    var mfTable = document.createElement("table");
    mfTable.className = "audit-table";
    var mfHead = document.createElement("thead");
    var mfHRow = document.createElement("tr");
    ["SHA", "Subject", "Kind", "Missing from"].forEach(function (h) {
      var th = document.createElement("th");
      th.textContent = h;
      mfHRow.appendChild(th);
    });
    mfHead.appendChild(mfHRow);
    mfTable.appendChild(mfHead);
    var mfBody = document.createElement("tbody");
    missingFixes.forEach(function (e) {
      var tr = document.createElement("tr");
      var tdSha = document.createElement("td");
      var code = document.createElement("code");
      code.textContent = e.sha.slice(0, 7);
      tdSha.appendChild(code);
      var tdSubj = document.createElement("td");
      tdSubj.textContent = e.subject;
      var tdKind = document.createElement("td");
      var kb = document.createElement("span");
      kb.className = e.kind === "security" ? "badge badge-fail" : "badge badge-na";
      kb.textContent = e.kind;
      tdKind.appendChild(kb);
      var tdBranches = document.createElement("td");
      var missingBranches = Object.entries(e.branches || {})
        .filter(function (kv) { return kv[1] === "missing"; })
        .map(function (kv) { return kv[0]; });
      tdBranches.textContent = missingBranches.join(", ");
      tr.appendChild(tdSha);
      tr.appendChild(tdSubj);
      tr.appendChild(tdKind);
      tr.appendChild(tdBranches);
      mfBody.appendChild(tr);
    });
    mfTable.appendChild(mfBody);
    mfWrap.appendChild(mfTable);
  }

  /* ---- Details panel ---- */
  var panel = document.getElementById("details-panel");
  var content = document.getElementById("details-content");
  document.getElementById("details-close").addEventListener("click", function () {
    panel.classList.remove("open");
  });

  function badge(val) {
    var s = document.createElement("span");
    s.className = val ? "badge badge-pass" : "badge badge-fail";
    s.textContent = val ? "true" : "false";
    return s;
  }

  function renderDiff(text) {
    var pre = document.createElement("pre");
    var lines = (text || "").split("\n");
    lines.forEach(function (line, i) {
      var span = document.createElement("span");
      span.className = (line.startsWith("+") && !line.startsWith("+++"))
        ? "diff-add"
        : (line.startsWith("-") && !line.startsWith("---"))
        ? "diff-del"
        : "";
      span.textContent = line + (i < lines.length - 1 ? "\n" : "");
      pre.appendChild(span);
    });
    return pre;
  }

  function showDetails(fix, target) {
    var r = target.result || {};
    var port = target.port || {};
    content.innerHTML = "";

    var h2 = document.createElement("h2");
    h2.textContent = fix.sha.slice(0, 7) + " \u2192 " + target.branch;
    content.appendChild(h2);

    var subjEl = document.createElement("p");
    subjEl.style.color = "var(--muted)";
    subjEl.style.marginBottom = "12px";
    subjEl.style.fontSize = "0.9em";
    subjEl.textContent = fix.subject;
    content.appendChild(subjEl);

    /* Decision */
    var h3d = document.createElement("h3");
    h3d.textContent = "Decision";
    content.appendChild(h3d);

    var kvt = document.createElement("table");
    kvt.className = "kv-table";

    function kvRow(k, vEl) {
      var tr2 = document.createElement("tr");
      var td1 = document.createElement("td");
      td1.textContent = k;
      var td2 = document.createElement("td");
      if (typeof vEl === "string") { td2.textContent = vEl; }
      else { td2.appendChild(vEl); }
      tr2.appendChild(td1);
      tr2.appendChild(td2);
      kvt.appendChild(tr2);
    }

    var method = r.method || target.decision || "\u2014";
    kvRow("method", method);
    kvRow("reason", target.reason || r.reason || "\u2014");
    var cit = target.citation || {};
    if (cit.doc) { kvRow("citation", cit.doc + (cit.section ? " " + cit.section : "")); }
    content.appendChild(kvt);

    /* Adaptations */
    if (port.adaptations && port.adaptations.length) {
      var h3a = document.createElement("h3");
      h3a.textContent = "Adaptations";
      content.appendChild(h3a);
      var ulA = document.createElement("ul");
      ulA.style.paddingLeft = "16px";
      port.adaptations.forEach(function (a) {
        var li = document.createElement("li");
        li.textContent = a;
        ulA.appendChild(li);
      });
      content.appendChild(ulA);
    }

    /* Verification */
    if (method === "clean" || method === "adapted") {
      var h3v = document.createElement("h3");
      h3v.textContent = "Verification";
      content.appendChild(h3v);

      var kvt2 = document.createElement("table");
      kvt2.className = "kv-table";
      function kvRow2(k, vEl) {
        var tr3 = document.createElement("tr");
        var td3 = document.createElement("td");
        td3.textContent = k;
        var td4 = document.createElement("td");
        if (typeof vEl === "string") { td4.textContent = vEl; }
        else { td4.appendChild(vEl); }
        tr3.appendChild(td3);
        tr3.appendChild(td4);
        kvt2.appendChild(tr3);
      }
      kvRow2("fail_before", badge(r.fail_before));
      if (r.fail_before_reason) { kvRow2("fb_reason", r.fail_before_reason); }
      kvRow2("pass_after", badge(r.pass_after));
      kvRow2("f2p", badge(r.f2p));
      kvRow2("p2p (full suite)", badge(r.p2p));
      if (r.suite) {
        kvRow2("suite",
          (r.suite.passed || 0) + " passed, " + (r.suite.failed || 0) + " failed");
      }
      kvRow2("seconds", (r.seconds || 0).toFixed(2) + "s");
      content.appendChild(kvt2);

      /* Per-test table */
      var tests = r.tests || [];
      if (tests.length > 0) {
        var h3t = document.createElement("h3");
        h3t.textContent = "Per-test proof";
        content.appendChild(h3t);
        var tbl = document.createElement("table");
        tbl.className = "test-table";
        var thead2 = document.createElement("thead");
        var hrow2 = document.createElement("tr");
        ["Test ID", "Failed before", "Passed after", "Proves fix"].forEach(function (h) {
          var th = document.createElement("th");
          th.textContent = h;
          hrow2.appendChild(th);
        });
        thead2.appendChild(hrow2);
        tbl.appendChild(thead2);
        var tbody2 = document.createElement("tbody");
        tests.forEach(function (t) {
          var tr2 = document.createElement("tr");
          var tdId = document.createElement("td");
          var code = document.createElement("code");
          code.style.fontSize = "0.85em";
          code.style.wordBreak = "break-all";
          code.textContent = t.id;
          tdId.appendChild(code);
          var tdFB = document.createElement("td");
          tdFB.appendChild(badge(t.failed_before));
          var tdPA = document.createElement("td");
          tdPA.appendChild(badge(t.passed_after));
          var tdPF = document.createElement("td");
          var pfBadge = document.createElement("span");
          pfBadge.className = t.proves_fix ? "badge badge-pass" : "badge badge-na";
          pfBadge.textContent = t.proves_fix ? "yes" : "no";
          tdPF.appendChild(pfBadge);
          tr2.appendChild(tdId);
          tr2.appendChild(tdFB);
          tr2.appendChild(tdPA);
          tr2.appendChild(tdPF);
          tbody2.appendChild(tr2);
        });
        tbl.appendChild(tbody2);
        content.appendChild(tbl);
      }
    }

    /* Review flags */
    var flags = r.flags || [];
    if (flags.length > 0) {
      var flagBox = document.createElement("div");
      flagBox.className = "flags-box";
      var flagTitle = document.createElement("div");
      flagTitle.className = "flags-box-title";
      flagTitle.textContent = "\u26a0\ufe0f Review required (" + flags.length + " flag" + (flags.length > 1 ? "s" : "") + ")";
      flagBox.appendChild(flagTitle);
      flags.forEach(function (f) {
        var item = document.createElement("div");
        item.className = "flag-item";
        var strong = document.createElement("strong");
        if (f.kind === "existing_test_modified") {
          strong.textContent = "Existing test modified";
          item.appendChild(strong);
          item.appendChild(document.createTextNode(
            ": this port changes " + f.file + " which already exists on this branch. " +
            "A release manager should verify the changed behaviour is intentional."
          ));
          if (f.functions && f.functions.length) {
            var fnEl = document.createElement("div");
            fnEl.style.marginTop = "3px";
            fnEl.style.fontSize = "0.9em";
            fnEl.style.color = "var(--muted)";
            fnEl.textContent = "Changed functions: " + f.functions.join(", ");
            item.appendChild(fnEl);
          }
        } else if (f.kind === "test_case_removed") {
          strong.textContent = "Test case removed";
          item.appendChild(strong);
          item.appendChild(document.createTextNode(
            ": " + f.file + " — the following test(s) from the original fix are absent in this port: " +
            (f.functions || []).join(", ") + ". Verify that each removal is intentional."
          ));
        } else if (f.kind === "test_passes_without_fix") {
          strong.textContent = "Test passes without fix";
          item.appendChild(strong);
          item.appendChild(document.createTextNode(
            ": one or more regression tests already pass on this branch without the fix applied. " +
            "This may mean the bug was already fixed, or the test is not a reliable proof. " +
            "Tests: " + (f.tests || []).join(", ")
          ));
        } else {
          strong.textContent = f.kind;
          item.appendChild(strong);
          item.appendChild(document.createTextNode(": " + JSON.stringify(f)));
        }
        flagBox.appendChild(item);
      });
      content.appendChild(flagBox);
    }

    /* Changed files */
    if (port.files_changed && port.files_changed.length) {
      var h3f = document.createElement("h3");
      h3f.textContent = "Changed files";
      content.appendChild(h3f);
      var ulF = document.createElement("ul");
      ulF.style.paddingLeft = "16px";
      port.files_changed.forEach(function (f) {
        var li2 = document.createElement("li");
        var code2 = document.createElement("code");
        code2.textContent = f;
        li2.appendChild(code2);
        ulF.appendChild(li2);
      });
      content.appendChild(ulF);
    }

    /* Side-by-side diffs */
    if (r.fix_diff || r.backport_diff) {
      var h3diffs = document.createElement("h3");
      h3diffs.textContent = "Diffs";
      content.appendChild(h3diffs);
      var diffCols = document.createElement("div");
      diffCols.className = "diff-cols";
      if (r.fix_diff) {
        var colL = document.createElement("div");
        var lblL = document.createElement("p");
        lblL.style.fontSize = "0.8em";
        lblL.style.color = "var(--muted)";
        lblL.style.marginBottom = "4px";
        lblL.textContent = "Original fix (main)";
        colL.appendChild(lblL);
        colL.appendChild(renderDiff(r.fix_diff));
        diffCols.appendChild(colL);
      }
      if (r.backport_diff) {
        var colR = document.createElement("div");
        var lblR = document.createElement("p");
        lblR.style.fontSize = "0.8em";
        lblR.style.color = "var(--muted)";
        lblR.style.marginBottom = "4px";
        lblR.textContent = "Backport";
        colR.appendChild(lblR);
        colR.appendChild(renderDiff(r.backport_diff));
        diffCols.appendChild(colR);
      }
      content.appendChild(diffCols);
    }

    panel.classList.add("open");
  }
})();
</script>
</body>
</html>"""

    return head_and_css + data_tag + body_html + js


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def cmd_report(_args) -> int:
    """Entry point for `ferry report`."""
    print("==> Building report \u2026")
    data = _load_all()

    # docs/index.html
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    html = _build_html(data)
    index_path = DOCS_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"    Written {index_path.relative_to(REPO_ROOT)}")

    # Changelogs
    _write_changelogs(data["results"], data["audit"])

    # ferry-state copy
    _copy_ferry_state()

    print("==> Report complete.")
    return 0
