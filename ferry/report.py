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
            short = sha[:7]
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

    # Bobcoins
    bc = metrics.get("bobcoins_by_task", {})
    total_bc = sum(bc.values()) if isinstance(bc, dict) else 0

    baseline_min = metrics.get("manual_baseline_minutes", None)

    return {
        "fixes_audited": fixes_audited,
        "missing_security": missing_sec,
        "ports_proven": proven,
        "clean": clean_ct,
        "adapted": adapted_ct,
        "escalated": escalated_ct,
        "pending": pending_ct,
        "total_bobcoins": round(total_bc, 2),
        "manual_baseline_minutes": baseline_min,
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
    }

    data_json = _escape_json_for_html(ferry_data)

    # Build HTML by concatenation to avoid f-string conflicts with JS braces.
    # Only the data-injection line uses f-string interpolation.
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
        '    }\n'
        '  }\n'
        '  * { box-sizing: border-box; margin: 0; padding: 0; }\n'
        '  body { font-family: var(--font); font-size: 14px; line-height: 1.6;\n'
        '          background: var(--bg); color: var(--text); }\n'
        '  a { color: var(--accent); }\n'
        '  .container { max-width: 960px; margin: 0 auto; padding: 24px 16px; }\n'
        '  h1 { font-size: 1.4em; font-weight: 700; margin-bottom: 8px; }\n'
        '  h2 { font-size: 1.1em; font-weight: 600; margin: 24px 0 10px; }\n'
        '  h3 { font-size: 1em; font-weight: 600; margin: 12px 0 6px; }\n'
        '  .metrics-bar { display: flex; flex-wrap: wrap; gap: 12px;\n'
        '    background: var(--surface); border: 1px solid var(--border);\n'
        '    border-radius: 6px; padding: 14px 16px; margin: 16px 0; }\n'
        '  .metric { display: flex; flex-direction: column; align-items: center;\n'
        '    min-width: 90px; text-align: center; }\n'
        '  .metric-value { font-size: 1.5em; font-weight: 700; color: var(--accent); }\n'
        '  .metric-label { font-size: 0.78em; color: var(--muted); margin-top: 2px; }\n'
        '  .matrix-wrap { overflow-x: auto; }\n'
        '  table { border-collapse: collapse; width: 100%; min-width: 500px; }\n'
        '  th, td { border: 1px solid var(--border); padding: 6px 10px;\n'
        '    text-align: left; vertical-align: top; }\n'
        '  th { background: var(--surface); font-weight: 600; font-size: 0.85em; }\n'
        '  .cell { cursor: pointer; border-radius: 4px; padding: 4px 8px;\n'
        '    font-size: 0.82em; white-space: nowrap; transition: opacity 0.1s; }\n'
        '  .cell:hover { opacity: 0.8; }\n'
        '  .cell-proven { background: var(--green-bg); color: var(--green); }\n'
        '  .cell-clean  { background: var(--blue-bg);  color: var(--blue);  }\n'
        '  .cell-escalated { background: var(--amber-bg); color: var(--amber); }\n'
        '  .cell-skip   { background: var(--grey-bg);  color: var(--grey);  }\n'
        '  .cell-pending { background: var(--red-bg);  color: var(--red);   }\n'
        '  #details-panel { display: none; position: fixed; right: 0; top: 0; bottom: 0;\n'
        '    width: min(480px, 100vw); overflow-y: auto;\n'
        '    background: var(--bg); border-left: 2px solid var(--border);\n'
        '    padding: 20px 18px; z-index: 100; font-size: 0.88em; }\n'
        '  #details-panel.open { display: block; }\n'
        '  #details-close { float: right; cursor: pointer; font-size: 1.3em;\n'
        '    color: var(--muted); background: none; border: none;\n'
        '    padding: 0; line-height: 1; }\n'
        '  .kv-table { width: 100%; border-collapse: collapse; margin: 8px 0; }\n'
        '  .kv-table td { padding: 3px 6px; border-bottom: 1px solid var(--border); }\n'
        '  .kv-table td:first-child { font-weight: 600; color: var(--muted);\n'
        '    white-space: nowrap; width: 40%; }\n'
        '  .badge { display: inline-block; border-radius: 3px; padding: 1px 6px;\n'
        '    font-size: 0.85em; font-weight: 600; }\n'
        '  .badge-pass { background: var(--green-bg); color: var(--green); }\n'
        '  .badge-fail { background: var(--red-bg);   color: var(--red);   }\n'
        '  .badge-na   { background: var(--grey-bg);  color: var(--grey);  }\n'
        '  pre { background: var(--surface); border: 1px solid var(--border);\n'
        '    border-radius: 4px; padding: 10px; overflow-x: auto;\n'
        '    font-size: 0.78em; line-height: 1.4; white-space: pre;\n'
        '    max-height: 320px; overflow-y: auto; }\n'
        '  .diff-add { color: var(--green); }\n'
        '  .diff-del { color: var(--red); }\n'
        '  .legend { display: flex; flex-wrap: wrap; gap: 10px;\n'
        '    margin: 10px 0; font-size: 0.82em; }\n'
        '  .legend-item { display: flex; align-items: center; gap: 5px; }\n'
        '  .legend-dot { width: 12px; height: 12px; border-radius: 2px; flex-shrink: 0; }\n'
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
        '  <p style="color:var(--muted);font-size:0.9em">Automated backporting with proof:'
        ' fail&#8209;before &#8594; pass&#8209;after &#8594; full suite</p>\n'
        '  <div class="metrics-bar" id="metrics-bar"></div>\n'
        '  <h2>Matrix</h2>\n'
        '  <div class="legend" id="legend"></div>\n'
        '  <div class="matrix-wrap"><table id="matrix-table"></table></div>\n'
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

  /* Metrics bar */
  var metricsBar = document.getElementById("metrics-bar");
  function addMetric(value, label) {
    var div = document.createElement("div");
    div.className = "metric";
    var val = document.createElement("span");
    val.className = "metric-value";
    val.textContent = value;
    var lbl = document.createElement("span");
    lbl.className = "metric-label";
    lbl.textContent = label;
    div.appendChild(val);
    div.appendChild(lbl);
    metricsBar.appendChild(div);
  }
  addMetric(metrics.fixes_audited, "fixes audited");
  addMetric(metrics.missing_security, "missing security");
  addMetric(metrics.ports_proven, "ports proven");
  addMetric(metrics.clean, "clean");
  addMetric(metrics.adapted, "adapted");
  addMetric(metrics.escalated, "escalated");
  addMetric(metrics.pending, "pending");
  addMetric(
    metrics.total_bobcoins !== null ? metrics.total_bobcoins.toFixed(2) : "\u2014",
    "Bobcoins"
  );
  addMetric(
    metrics.manual_baseline_minutes !== null
      ? metrics.manual_baseline_minutes + " min"
      : "\u2014",
    "baseline"
  );

  /* Legend */
  var legendItems = [
    { cls: "cell-proven",    dot: "#dcffe4", label: "adapted + proven (f2p+p2p)" },
    { cls: "cell-clean",     dot: "#ddf4ff", label: "clean cherry-pick proven" },
    { cls: "cell-escalated", dot: "#fff8c5", label: "escalated" },
    { cls: "cell-skip",      dot: "#f6f8fa", label: "skip / not applicable" },
    { cls: "cell-pending",   dot: "#ffeef0", label: "pending / conflict" }
  ];
  var legendEl = document.getElementById("legend");
  legendItems.forEach(function (item) {
    var wrap = document.createElement("span");
    wrap.className = "legend-item";
    var dot = document.createElement("span");
    dot.className = "legend-dot";
    dot.style.background = item.dot;
    dot.style.border = "1px solid #ccc";
    var txt = document.createTextNode(item.label);
    wrap.appendChild(dot);
    wrap.appendChild(txt);
    legendEl.appendChild(wrap);
  });

  /* Matrix */
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

  function cellClass(target) {
    var r = target.result || {};
    var method = r.method || target.decision || "";
    if (method === "skip" || method === "not_applicable" || method === "skipped") {
      return "cell-skip";
    }
    if (method === "escalated") { return "cell-escalated"; }
    if (method === "pending") { return "cell-pending"; }
    if (method === "clean" && r.f2p && r.p2p) { return "cell-clean"; }
    if ((method === "adapted" || method === "clean") && (r.f2p || r.p2p)) {
      return "cell-proven";
    }
    if (method === "clean" || method === "adapted") {
      return (r.f2p && r.p2p) ? "cell-clean" : "cell-pending";
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
    if (method === "clean" && r.f2p && r.p2p) { return "proven (clean)"; }
    if (method === "adapted" && r.f2p && r.p2p) { return "proven (adapted)"; }
    if (method === "clean" || method === "adapted") {
      return "fail (f2p=" + (r.f2p ? "T" : "F") + " p2p=" + (r.p2p ? "T" : "F") + ")";
    }
    return method || "?";
  }

  fixes.forEach(function (fix) {
    var tr = document.createElement("tr");
    var tdFix = document.createElement("td");
    var shortEl = document.createElement("code");
    shortEl.textContent = fix.sha.slice(0, 7);
    tdFix.appendChild(shortEl);
    tdFix.appendChild(document.createTextNode(" "));
    var subj = document.createElement("span");
    subj.style.color = "var(--muted)";
    subj.textContent = fix.subject.length > 50
      ? fix.subject.slice(0, 50) + "..."
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

  /* Details panel */
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
    h2.textContent = fix.sha.slice(0, 7) + " on " + target.branch;
    content.appendChild(h2);

    var subjEl = document.createElement("p");
    subjEl.style.color = "var(--muted)";
    subjEl.style.marginBottom = "12px";
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
    }

    /* Adaptations */
    if (port.adaptations && port.adaptations.length) {
      var h3a = document.createElement("h3");
      h3a.textContent = "Adaptations";
      content.appendChild(h3a);
      var ul = document.createElement("ul");
      ul.style.paddingLeft = "18px";
      port.adaptations.forEach(function (a) {
        var li = document.createElement("li");
        li.textContent = a;
        ul.appendChild(li);
      });
      content.appendChild(ul);
    }

    /* Changed files */
    if (port.files_changed && port.files_changed.length) {
      var h3f = document.createElement("h3");
      h3f.textContent = "Changed files";
      content.appendChild(h3f);
      var ul2 = document.createElement("ul");
      ul2.style.paddingLeft = "18px";
      port.files_changed.forEach(function (f) {
        var li2 = document.createElement("li");
        var code = document.createElement("code");
        code.textContent = f;
        li2.appendChild(code);
        ul2.appendChild(li2);
      });
      content.appendChild(ul2);
    }

    /* Diffs */
    if (r.fix_diff) {
      var h3fd = document.createElement("h3");
      h3fd.textContent = "Fix diff (main)";
      content.appendChild(h3fd);
      content.appendChild(renderDiff(r.fix_diff));
    }
    if (r.backport_diff) {
      var h3bd = document.createElement("h3");
      h3bd.textContent = "Backport diff";
      content.appendChild(h3bd);
      content.appendChild(renderDiff(r.backport_diff));
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
    print("==> Building report …")
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
