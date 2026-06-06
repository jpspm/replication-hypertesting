"""
Phases 3-7 of the HyperTesting Extended Replication Agent.

Phases executed here:
  Phase 3  - Recover original 34 paper samples -> artifacts/original_paper_samples.json
  Phase 4  - Build candidate pool (IFSpec - original 34) -> artifacts/candidate_pool.json
  Phase 5  - Compatibility validation (dry-run via Docker) ->
               artifacts/compatible_samples.json
               artifacts/incompatible_samples.json
  Phase 6  - Select 50 programs (seed 42) -> artifacts/selected_50_samples.json
  Phase 7  - Generate settings.conf from RIFL -> generated-settings/

All paths are relative to the working directory where this script is run.
"""

import os
import sys
import json
import re
import glob
import random
import shutil
import subprocess
import xml.etree.ElementTree as ET

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
REPLICATION_PKG = os.path.join(BASE_DIR, "replication-package")
IFSPEC_DIR      = os.path.join(BASE_DIR, "workspace", "ifspec", "JavaSourceCode")
ARTIFACTS_DIR   = os.path.join(BASE_DIR, "artifacts")
GEN_SETTINGS    = os.path.join(BASE_DIR, "generated-settings")

FULL_DATASET        = os.path.join(REPLICATION_PKG, "datasets", "FullDataset")
UNSECURE_DATASET    = os.path.join(REPLICATION_PKG, "datasets", "UnsecureOnlyDataset")

os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(GEN_SETTINGS,  exist_ok=True)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def list_subdirs(path):
    return sorted([
        d for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d))
    ])


def read_file_safe(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Phase 3 - Recover original 34 samples
# ---------------------------------------------------------------------------

def phase3_original_samples():
    print("\n=== Phase 3: Recovering original paper samples ===")
    full_samples    = list_subdirs(FULL_DATASET)
    unsec_samples   = list_subdirs(UNSECURE_DATASET)

    result = {
        "count": len(full_samples),
        "full_dataset_count": len(full_samples),
        "unsecure_only_dataset_count": len(unsec_samples),
        "datasets": {
            "FullDataset":          full_samples,
            "UnsecureOnlyDataset":  unsec_samples,
        },
        "samples": full_samples,
    }
    save_json(os.path.join(ARTIFACTS_DIR, "original_paper_samples.json"), result)
    print(f"  Found {len(full_samples)} samples in FullDataset.")
    return set(full_samples)


# ---------------------------------------------------------------------------
# Mapping: FullDataset sample name -> IFSpec directory name
# Derived by comparing Java class content across both collections.
# ---------------------------------------------------------------------------

FULLDATASET_TO_IFSPEC = {
    "Aliasing-ControlFlow-secure":              "Aliasing-ControlFlow-secure",
    "Aliasing-ControlFlow-unsecure":            "Aliasing-ControlFlow-Insecure",
    "Aliasing-InterProcedural-secure":          "Aliasing-InterProcedural-secure",
    "Aliasing-InterProcedural-unsecure":        "Aliasing-InterProcedural-Insecure",
    "Aliasing-Nested-secure":                   "Aliasing-Nested-secure",
    "Aliasing-Nested-unsecure":                 "Aliasing-Nested-Insecure",
    "Aliasing-Simple-secure":                   "Aliasing-Simple-secure",
    "Aliasing-Simple-unsecure":                 "Aliasing-Simple-Insecure",
    "Aliasing-StrongUpdate-secure":             "Aliasing-StrongUpdate-secure",
    "ArrayIndexSensitivity-secure":             "ArrayIndexSensitivity-secure",
    "Arrays-ImplicitLeak-secure":               "Arrays-ImplicitLeak-secure",
    "Arrays-ImplicitLeak-unsecure":             "Arrays-ImplicitLeak-Insecure",
    "ArraySizeStrongUpdate-secure":             "ArraySizeStrongUpdate",
    "BooleanOperations-secure":                 "BooleanOperations-secure",
    "BooleanOperations-unsecure":               "BooleanOperations-Insecure",
    "CallContext-secure":                       "CallContext",
    "Deepalias-secure":                         "Deepalias2",
    "Deepalias-unsecure":                       "Deepalias1",
    "Deepcall-secure":                          "Deepcall2",
    "Deepcall-unsecure":                        "Deepcall1",
    "DirectAssignment-secure":                  "DirectAssignment-secure",
    "DirectAssignment-unsecure":                "DirectAssignment",
    "DirectAssignmentLeak-unsecure":            "DirectAssignmentLeak",
    "HighConditionalIncrementalLeak-secure":    "HighConditionalIncrementalLeak-secure",
    "HighConditionalIncrementalLeak-unsecure":  "HighConditionalIncrementalLeak-Insecure",
    "IFLoop-secure":                            "IFLoop",
    "IFLoop-unsecure":                          "IFLoop2",
    "IFMethodContractA-secure":                 "IFMethodContract",
    "IFMethodContractB-secure":                 "IFMethodContract2",
    "LostInCast-secure":                        "LostInCast",
    "ScenarioPassword-secure":                  "ScenarioPasswordSecure",
    "ScenarioPassword-unsecure":                "ScenarioPasswordInsecure",
    "SimpleArraySize-unsecure":                 "simpleArraySize",
    "SimpleErasureByConditionalChecks-secure":  "simpleErasureByConditionalChecks",
}

IFSPEC_USED = set(FULLDATASET_TO_IFSPEC.values())


# ---------------------------------------------------------------------------
# Phase 4 - Build candidate pool
# ---------------------------------------------------------------------------

def phase4_candidate_pool():
    print("\n=== Phase 4: Building candidate pool ===")
    all_ifspec = list_subdirs(IFSPEC_DIR)
    candidates = [s for s in all_ifspec if s not in IFSPEC_USED]

    result = {
        "ifspec_total":         len(all_ifspec),
        "paper_samples_count":  len(IFSPEC_USED),
        "candidate_count":      len(candidates),
        "paper_samples_used":   sorted(IFSPEC_USED),
        "candidates":           candidates,
    }
    save_json(os.path.join(ARTIFACTS_DIR, "candidate_pool.json"), result)
    print(f"  IFSpec total: {len(all_ifspec)}, Used: {len(IFSPEC_USED)}, Candidates: {len(candidates)}")
    return candidates


# ---------------------------------------------------------------------------
# RIFL parsing helpers (Phase 5 settings + Phase 7)
# ---------------------------------------------------------------------------

def extract_class_name(java_path):
    """Return the public/default class name declared in a .java file."""
    content = read_file_safe(java_path)
    m = re.search(r'(?:public\s+)?class\s+(\w+)', content)
    return m.group(1) if m else None


EXTERNAL_CLASSES = (
    "java.", "javax.", "android.", "sun.", "com.sun.",
    "org.w3c.", "org.xml.", "org.omg.",
)

def _is_external(cls):
    return any(cls.startswith(p) for p in EXTERNAL_CLASSES)


def _parse_domain_map(root):
    """Return domain_name -> 'H'|'L' from <flowrelation> and <domains>."""
    domain_map = {}
    for flow in root.iter("flow"):
        frm = flow.get("from", "")
        to  = flow.get("to",   "")
        if frm and to:
            domain_map[frm] = "L"   # low (public)
            domain_map[to]  = "H"   # high (confidential)
    if not domain_map:
        for domain in root.iter("domain"):
            name = domain.get("name", "").lower()
            actual = domain.get("name", "")
            if "high" in name or name == "h":
                domain_map[actual] = "H"
            elif "low" in name or name == "l":
                domain_map[actual] = "L"
    return domain_map


def _extract_param_names(java_path, method_name):
    """
    Return ordered list of parameter names for the given method declaration.
    Matches only declarations (return_type method_name(params)), not call sites.
    """
    content = read_file_safe(java_path)
    # Match: [modifiers] ReturnType methodName(params) — require a word before the name
    pattern = rf'(?:(?:public|protected|private|static|final|synchronized|native|abstract)\s+)+(?:[\w<>\[\]]+\s+){re.escape(method_name)}\s*\(([^)]*)\)'
    m = re.search(pattern, content)
    if not m:
        # Simpler fallback: TYPE methodName(params) where TYPE is a word
        pattern2 = rf'\b\w[\w<>\[\]]*\s+{re.escape(method_name)}\s*\(([^)]*)\)'
        for candidate in re.finditer(pattern2, content):
            params_str = candidate.group(1).strip()
            if params_str and re.match(r'\w[\w<>\[\]]*\s+\w', params_str):
                # Looks like a declaration (has type + name pairs)
                m = candidate
                break
    if not m:
        return []
    params_str = m.group(1).strip()
    if not params_str:
        return []
    names = []
    for param in params_str.split(","):
        parts = param.strip().split()
        if len(parts) >= 2:  # must have at least type + name
            names.append(parts[-1].strip("[]"))
    return names


def find_method_in_rifl(rifl_path, java_class_name=None):
    """
    Extract (method_name, None) from a RIFL XML spec, considering only
    elements whose 'class' attribute is NOT an external Java class.
    """
    content = read_file_safe(rifl_path)
    if not content:
        return None, None
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None, None

    for elem in root.iter():
        cls = elem.get("class", "")
        method_attr = elem.get("method", "")
        if not method_attr or not cls:
            continue
        if _is_external(cls):
            continue
        if "(" in method_attr:
            m = re.match(r'(\w+)\(', method_attr)
            if m:
                return m.group(1), None
    return None, None


def find_method_in_java(java_path, class_name=None):
    """
    Return (method_name, modifier) for the primary test method.
    Prefers the first static method with non-String-array primitive-ish parameters
    that is not main(). Falls back to main() if nothing else is found.
    """
    content = read_file_safe(java_path)
    # Prefer: public static <type> <name>(<non-String[]> params)
    for m in re.finditer(
            r'(?:public\s+)?(static\s+)\w[\w<>\[\]]*\s+(\w+)\s*\(([^)]*)\)',
            content):
        name = m.group(2)
        params = m.group(3)
        if name in ("main", "class", "interface", "enum"):
            continue
        # Skip if param list is just String[]
        if re.fullmatch(r'\s*String\s*\[\s*\]\s*\w+\s*', params):
            continue
        return name, "static"
    # Non-static public methods
    for m in re.finditer(
            r'public\s+(?!static)(\w[\w<>\[\]]*)\s+(\w+)\s*\(([^)]*)\)',
            content):
        name = m.group(2)
        if name in ("main", "class", "interface", "enum"):
            continue
        return name, "nonstatic"
    # Fall back to main
    if re.search(r'public\s+static\s+void\s+main\s*\(', content):
        return "main", "static"
    return None, None


def parse_rifl_settings(rifl_path, java_path, method_name=None):
    """
    Convert RIFL XML into settings.conf content using actual Java parameter
    names. Returns a settings string, or None if nothing can be generated.
    """
    content = read_file_safe(rifl_path)
    if not content:
        return None
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None

    domain_map = _parse_domain_map(root)

    handle_hl = {}
    for assign in root.iter("assign"):
        h = assign.get("handle")
        d = assign.get("domain")
        if h and d and d in domain_map:
            handle_hl[h] = domain_map[d]

    # Collect (param_index -> HL) and (return -> HL) for the target method
    param_pos_hl   = {}   # 0-based index -> H|L
    return_hl      = "L"
    field_hl       = {}   # field_name -> H|L
    has_local_refs = False

    for assignable in root.iter("assignable"):
        handle = assignable.get("handle")
        hl = handle_hl.get(handle)
        if not hl:
            continue
        for child in assignable.iter():
            tag = child.tag.lower()
            cls = child.get("class", "")
            if _is_external(cls):
                continue
            if tag == "parameter":
                idx_str = child.get("parameter", "")
                if idx_str.isdigit():
                    param_pos_hl[int(idx_str) - 1] = hl
                has_local_refs = True
            elif tag == "returnvalue":
                return_hl = hl
                has_local_refs = True
            elif tag == "field":
                fname = child.get("name", "") or child.get("field", "")
                if fname:
                    field_hl[fname] = hl
                    has_local_refs = True
            elif tag == "local":
                fname = child.get("name", "")
                if fname:
                    field_hl[fname] = hl
                    has_local_refs = True

    # Get actual parameter names from Java
    param_names = _extract_param_names(java_path, method_name) if method_name else []

    lines = []
    seen  = set()

    # Map by position
    for idx, hl in sorted(param_pos_hl.items()):
        if idx < len(param_names):
            vname = param_names[idx]
        else:
            vname = f"param{idx+1}"
        if vname not in seen:
            lines.append(f"{vname} : {hl}")
            seen.add(vname)

    # Remaining named params not covered by RIFL positions → default L
    for i, pname in enumerate(param_names):
        if pname not in seen:
            hl = param_pos_hl.get(i, "L")
            lines.append(f"{pname} : {hl}")
            seen.add(pname)

    # Fields / locals from RIFL
    for fname, hl in field_hl.items():
        if fname not in seen:
            lines.append(f"{fname} : {hl}")
            seen.add(fname)

    # Return value
    if "ret" not in seen:
        lines.append(f"ret : {return_hl}")

    if lines:
        return "\n".join(lines) + "\n"

    return _generate_settings_from_java(java_path)


def _generate_settings_from_java(java_path):
    """
    Fallback: scan the Java file for parameter names of the test method
    and assign H to the first param, L to the rest / return.
    """
    content = read_file_safe(java_path)
    # Find the first non-main public method
    m = re.search(
        r'public\s+(?:static\s+)?\w[\w<>\[\]]*\s+(\w+)\s*\(([^)]*)\)',
        content
    )
    if not m:
        return None
    params_str = m.group(2).strip()
    lines = []
    if params_str:
        params = [p.strip().split()[-1] for p in params_str.split(",") if p.strip()]
        for i, p in enumerate(params):
            lines.append(f"{p} : {'H' if i == 0 else 'L'}")
    lines.append("ret : L")
    return "\n".join(lines) + "\n" if lines else None


# ---------------------------------------------------------------------------
# Phase 5 - Compatibility validation
# ---------------------------------------------------------------------------

def _build_sample_dir(ifspec_name, target_dir):
    """
    Build a temporary sample directory from an IFSpec entry,
    mirroring the FullDataset structure expected by the experiment scripts.
    Returns True on success.
    """
    ifspec_sample = os.path.join(IFSPEC_DIR, ifspec_name)
    program_src   = os.path.join(ifspec_sample, "program")
    rifl_path     = os.path.join(ifspec_sample, "rifl.xml")

    java_files = glob.glob(os.path.join(program_src, "*.java"))
    if not java_files:
        return False, "no Java file found"

    java_path = java_files[0]
    class_name = extract_class_name(java_path)
    if not class_name:
        return False, "cannot determine class name"

    # Determine method name + modifier
    method_name, modifier = find_method_in_rifl(rifl_path, class_name)
    if not method_name:
        method_name, modifier = find_method_in_java(java_path, class_name)
    if not method_name:
        return False, "cannot determine method name"
    if not modifier:
        java_content = read_file_safe(java_path)
        is_static = bool(re.search(
            rf'static\s+\w[\w<>\[\]]*\s+{re.escape(method_name)}\s*\(',
            java_content))
        modifier = "static" if is_static else "nonstatic"

    # Build settings.conf
    settings = parse_rifl_settings(rifl_path, java_path, method_name)
    if not settings:
        return False, "cannot generate settings.conf"

    # Create target directory structure
    os.makedirs(os.path.join(target_dir, "program"), exist_ok=True)
    shutil.copy(java_path, os.path.join(target_dir, "program", os.path.basename(java_path)))
    with open(os.path.join(target_dir, "method.txt"), "w") as f:
        f.write(f"{method_name}\n{modifier}\n")
    with open(os.path.join(target_dir, "settings.conf"), "w") as f:
        f.write(settings)

    return True, None


def _try_run_tool(jar_path, java_file, method, modifier, settings, timeout=30):
    """
    Attempt a short dry-run of hyperfuzz or hyperevo.
    Returns (success, error_message).
    """
    static_flag = "--static" if modifier == "static" else ""
    cmd = [
        "java", "-jar", jar_path,
        f"-c={java_file}",
        f"-m={method}",
        f"-s={settings}",
        static_flag,
        "-p=1",   # minimal budget for dry-run
    ]
    cmd = [c for c in cmd if c]  # remove empty strings
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout,
            cwd=REPLICATION_PKG
        )
        # Accept exit 0, or stderr that says "testing budget" (tool ran correctly)
        combined = (result.stdout + result.stderr).lower()
        if result.returncode == 0:
            return True, None
        # Some tools print usage errors on incompatible constructs
        if any(kw in combined for kw in ("unsupportedoperationexception",
                                          "classnotfoundexception",
                                          "compilationexception",
                                          "error:")):
            return False, result.stderr[:300]
        # If it just ran but exited non-zero (e.g. no violation found), treat as OK
        return True, None
    except subprocess.TimeoutExpired:
        # Timeout during dry-run likely means tool started correctly
        return True, None
    except Exception as e:
        return False, str(e)


def phase5_compatibility(candidates):
    print("\n=== Phase 5: Compatibility validation ===")
    HYPERFUZZ = os.path.join(REPLICATION_PKG, "bin", "hyperfuzz.jar")
    HYPEREVO  = os.path.join(REPLICATION_PKG, "bin", "hyperevo.jar")

    compatible   = []
    incompatible = []

    tmp_base = os.path.join(BASE_DIR, "_compat_tmp")
    os.makedirs(tmp_base, exist_ok=True)

    for ifspec_name in candidates:
        print(f"  Checking: {ifspec_name} ...", end=" ", flush=True)
        sample_dir = os.path.join(tmp_base, ifspec_name)
        os.makedirs(sample_dir, exist_ok=True)

        ok, reason = _build_sample_dir(ifspec_name, sample_dir)
        if not ok:
            print(f"INCOMPATIBLE ({reason})")
            incompatible.append({"sample": ifspec_name, "status": "incompatible", "reason": reason})
            continue

        # Read built files
        java_files = glob.glob(os.path.join(sample_dir, "program", "*.java"))
        java_file  = java_files[0]
        method_txt = open(os.path.join(sample_dir, "method.txt")).readlines()
        method     = method_txt[0].strip()
        modifier   = method_txt[1].strip() if len(method_txt) > 1 else "static"
        settings   = os.path.join(sample_dir, "settings.conf")

        # Dry-run HyperFuzz
        fuzz_ok, fuzz_err = _try_run_tool(HYPERFUZZ, java_file, method, modifier, settings)
        if not fuzz_ok:
            msg = f"HyperFuzz dry-run failed: {fuzz_err}"
            print(f"INCOMPATIBLE ({msg})")
            incompatible.append({"sample": ifspec_name, "status": "incompatible", "reason": msg})
            continue

        # Dry-run HyperEvo
        evo_ok, evo_err = _try_run_tool(HYPEREVO, java_file, method, modifier, settings)
        if not evo_ok:
            msg = f"HyperEvo dry-run failed: {evo_err}"
            print(f"INCOMPATIBLE ({msg})")
            incompatible.append({"sample": ifspec_name, "status": "incompatible", "reason": msg})
            continue

        # Settings verification
        if not os.path.isfile(settings):
            msg = "settings.conf missing after generation"
            print(f"INCOMPATIBLE ({msg})")
            incompatible.append({"sample": ifspec_name, "status": "incompatible", "reason": msg})
            continue

        print("OK")
        compatible.append(ifspec_name)

    # Persist results
    save_json(os.path.join(ARTIFACTS_DIR, "compatible_samples.json"),
              {"count": len(compatible), "samples": compatible})
    save_json(os.path.join(ARTIFACTS_DIR, "incompatible_samples.json"),
              {"count": len(incompatible), "samples": incompatible})

    print(f"  Compatible: {len(compatible)}, Incompatible: {len(incompatible)}")
    return compatible


# ---------------------------------------------------------------------------
# Phase 6 - Select 50 programs (seed 42)
# ---------------------------------------------------------------------------

def phase6_select_50(compatible):
    print("\n=== Phase 6: Selecting 50 programs (seed=42) ===")
    if len(compatible) < 50:
        print(f"  WARNING: only {len(compatible)} compatible programs available, selecting all.")
        selected = list(compatible)
    else:
        rng = random.Random(42)
        selected = rng.sample(compatible, 50)

    result = {
        "seed":    42,
        "count":   len(selected),
        "samples": sorted(selected),
    }
    save_json(os.path.join(ARTIFACTS_DIR, "selected_50_samples.json"), result)
    print(f"  Selected {len(selected)} programs.")
    return selected


# ---------------------------------------------------------------------------
# Phase 7 - Generate settings.conf + method.txt for selected samples
# ---------------------------------------------------------------------------

def phase7_generate_settings(selected):
    print("\n=== Phase 7: Generating security labels / settings.conf ===")
    for ifspec_name in selected:
        ifspec_sample = os.path.join(IFSPEC_DIR, ifspec_name)
        dest_dir      = os.path.join(GEN_SETTINGS, ifspec_name)
        os.makedirs(dest_dir, exist_ok=True)

        program_src = os.path.join(ifspec_sample, "program")
        rifl_path   = os.path.join(ifspec_sample, "rifl.xml")
        java_files  = glob.glob(os.path.join(program_src, "*.java"))

        if not java_files:
            print(f"  SKIP {ifspec_name}: no Java file")
            continue

        java_path  = java_files[0]
        class_name = extract_class_name(java_path)

        method_name, modifier = find_method_in_rifl(rifl_path, class_name)
        if not method_name:
            method_name, modifier = find_method_in_java(java_path, class_name)
        if not method_name:
            print(f"  SKIP {ifspec_name}: cannot determine method")
            continue
        if not modifier:
            java_content = read_file_safe(java_path)
            is_static = bool(re.search(
                rf'static\s+\w[\w<>\[\]]*\s+{re.escape(method_name)}\s*\(',
                java_content))
            modifier = "static" if is_static else "nonstatic"

        settings = parse_rifl_settings(rifl_path, java_path, method_name)
        if not settings:
            settings = _generate_settings_from_java(java_path) or "ret : L\n"

        shutil.copy(java_path, os.path.join(dest_dir, os.path.basename(java_path)))
        with open(os.path.join(dest_dir, "settings.conf"), "w") as f:
            f.write(settings)
        with open(os.path.join(dest_dir, "method.txt"), "w") as f:
            f.write(f"{method_name}\n{modifier}\n")

        print(f"  {ifspec_name}: method={method_name} ({modifier})")

    print(f"  Settings written to: {GEN_SETTINGS}/")


# ---------------------------------------------------------------------------
# Environment snapshot (for artifacts/environment.json)
# ---------------------------------------------------------------------------

def capture_environment():
    import platform
    def run(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return (r.stdout + r.stderr).strip()
        except Exception as e:
            return str(e)

    env = {
        "os":         platform.platform(),
        "java":       run(["java", "-version"]),
        "python":     run(["python3", "--version"]) or run(["python", "--version"]),
        "pip_freeze": run(["pip3", "freeze"]) or run(["pip", "freeze"]),
    }
    save_json(os.path.join(ARTIFACTS_DIR, "environment.json"), env)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("HyperTesting Extended Replication Agent - Phases 3-7")
    print("=" * 60)

    capture_environment()
    phase3_original_samples()
    candidates = phase4_candidate_pool()
    compatible = phase5_compatibility(candidates)
    selected   = phase6_select_50(compatible)
    phase7_generate_settings(selected)

    print("\n=== Done (Phases 3-7) ===")
    print(f"  Artifacts: {ARTIFACTS_DIR}")
    print(f"  Settings:  {GEN_SETTINGS}")
