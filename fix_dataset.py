"""
fix_dataset.py: Fix Java programs in generated-settings for hypercoveragetester
compatibility, then run a Docker compatibility test.

Fixes applied per program:
  1. Add 'public' to class declarations
  2. Add 'public' to the test method declaration
  3. Add explicit 'ret' local variable and rewrite return statements
     (settings.conf uses 'ret : L'; bytecode must have a variable named 'ret')

Programs skipped:
  - void return type  (tool tracks return value only)
  - try-catch in body (getBranchDistance returns null)
  - missing test method
"""

import os, re, json, shutil, glob

BASE          = os.path.dirname(os.path.abspath(__file__))
GEN_SETTINGS  = os.path.join(BASE, "generated-settings")
ARTIFACTS     = os.path.join(BASE, "artifacts")
REPLICATION   = os.path.join(BASE, "replication-package")
DATASETS_DIR  = os.path.join(REPLICATION, "datasets")
NEW_DATASET   = os.path.join(DATASETS_DIR, "NewDataset")
NEW_UNSECURE  = os.path.join(DATASETS_DIR, "NewUnsecureDataset")
NEW_PHOSPHOR  = os.path.join(DATASETS_DIR, "NewDataset-phosphor")
IFSPEC_DIR    = os.path.join(BASE, "workspace", "ifspec", "JavaSourceCode")

JAVA_MODIFIERS = {
    "public", "protected", "private", "static", "final",
    "synchronized", "native", "abstract", "strictfp",
}

# Programs with try-catch that cause getBranchDistance() NullPointerException
TRY_CATCH_SKIP = {
    "ConditionalLekage", "ExceptionHandling",
    "ExceptionalControlFlow1-Insecure", "ExceptionalControlFlow1-secure",
    "ExceptionalControlFlow2-secure",
    "ExceptionDivZero",
    "ArrayIndexException-Insecure", "ArrayIndexException-secure",
    "simpleTypesCastingError",
}

# Programs where method.txt names a method absent from the class file
METHOD_MISMATCH_SKIP = {"ObjectSensLeak"}

# Programs definitively incompatible with the tool's fuzzer
FUZZER_SKIP = {
    "Polynomial",       # BigInteger params — FuzzerNotPresentException
    "Webstore2",        # Object (Video) return type — FuzzerNotPresentException
    "PasswordChecker",  # String param + no H method params — InvocationTargetException
}


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def read_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def write_file(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Java source analysis
# ---------------------------------------------------------------------------

def get_method_info(source, method_name):
    """
    Scan source line-by-line for the method declaration.
    Returns (return_type:str, has_try_in_body:bool, is_public:bool).
    return_type is None if not found.
    """
    lines  = source.splitlines()
    n      = len(lines)
    decl_i = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        # Must contain method name followed by '('
        if not re.search(rf'(?<!\w){re.escape(method_name)}\s*\(', stripped):
            continue
        # Must look like a declaration: optional modifiers, return type, name, '('
        m = re.match(
            r'^((?:(?:public|protected|private|static|final|synchronized|native|abstract)\s+)*)'
            r'([\w][\w<>\[\],]*(?:\[\s*\])*)\s+'
            rf'{re.escape(method_name)}\s*\(',
            stripped,
        )
        if not m:
            continue
        modifiers = m.group(1)
        ret_type  = m.group(2).strip()
        # Safety: strip accidental leading modifiers absorbed into ret_type
        parts = ret_type.split()
        while parts and parts[0] in JAVA_MODIFIERS:
            parts.pop(0)
        ret_type  = parts[0] if parts else ret_type
        is_public = "public" in modifiers
        decl_i    = i
        break

    if decl_i is None:
        return None, False, False

    # Find opening brace (might be on same or next lines)
    brace_pos = source.find("{", source.index(lines[decl_i]))
    if brace_pos == -1:
        return ret_type, False, is_public

    # Extract body (balanced braces)
    depth, pos = 1, brace_pos + 1
    src        = source
    while pos < len(src) and depth > 0:
        c = src[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        pos += 1
    body = src[brace_pos + 1: pos - 1]
    has_try = bool(re.search(r"\btry\s*\{", body))

    return ret_type, has_try, is_public


def _find_method_bounds(source, method_name):
    """Return (open_brace_pos, close_brace_pos) for method body, or (None, None)."""
    lines = source.splitlines()
    decl_i = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if not re.search(rf'(?<!\w){re.escape(method_name)}\s*\(', stripped):
            continue
        m = re.match(
            r'^((?:(?:public|protected|private|static|final|synchronized|native|abstract)\s+)*)'
            r'[\w][\w<>\[\],]*(?:\[\s*\])*\s+'
            rf'{re.escape(method_name)}\s*\(',
            stripped,
        )
        if m:
            decl_i = i
            break

    if decl_i is None:
        return None, None

    open_pos = source.find("{", source.index(lines[decl_i]))
    if open_pos == -1:
        return None, None

    depth, pos = 1, open_pos + 1
    while pos < len(source) and depth > 0:
        c = source[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        pos += 1
    return open_pos, pos - 1


# ---------------------------------------------------------------------------
# Source fixes
# ---------------------------------------------------------------------------

def fix_class_visibility(source, java_filename=""):
    """Add public to the class declaration matching the filename."""
    class_name = os.path.splitext(java_filename)[0] if java_filename else ""
    if not class_name:
        # Fallback: make the single top-level class public
        return re.sub(
            r"(?m)^(?![ \t]*(?:public|protected|private|abstract|final)\b)([ \t]*)(class\b)",
            r"\1public \2",
            source,
        )
    # Only add public to the class whose name matches the filename
    return re.sub(
        rf"(?m)^(?![ \t]*(?:public|protected|private|abstract|final)\s+class\s+{re.escape(class_name)})"
        rf"([ \t]*)(class\s+{re.escape(class_name)}\b)",
        r"\1public \2",
        source,
    )


def fix_method_visibility(source, method_name):
    """Ensure the test method has the public modifier."""
    # Already public?
    if re.search(
        rf"public\s+(?:(?:static|final|synchronized|abstract|native)\s+)*"
        rf"[\w<>\[\]]+\s+{re.escape(method_name)}\s*\(",
        source,
    ):
        return source

    # Insert 'public' before the first occurrence of the declaration
    def inserter(m2):
        indent = m2.group(1)
        rest   = m2.group(2)
        return f"{indent}public {rest}"

    return re.sub(
        rf"(?m)^([ \t]*)((?:(?:protected|private|static|final|synchronized|abstract|native)\s+)*"
        rf"[\w<>\[\]]+\s+{re.escape(method_name)}\s*\()",
        inserter,
        source,
        count=1,
    )


def add_ret_variable(source, method_name, ret_type):
    """
    In the method body:
      1. Prepend 'TYPE ret;'
      2. Rewrite 'return EXPR;' → 'ret = EXPR; return ret;'
    Returns (new_source, success).
    """
    open_pos, close_pos = _find_method_bounds(source, method_name)
    if open_pos is None:
        return source, False

    body = source[open_pos + 1: close_pos]

    # Already done
    if re.search(r"\bret\b", body):
        return source, True

    body = f"\n        {ret_type} ret;" + body

    def rewrite_return(m2):
        expr = m2.group(1).strip()
        if not expr:
            return m2.group(0)  # bare return; in void (shouldn't reach here)
        return f"ret = {expr};\n        return ret;"

    body = re.sub(r"\breturn\s+([^;{}\n]+);", rewrite_return, body)

    new_source = source[: open_pos + 1] + body + source[close_pos:]
    return new_source, True


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def read_ground_truth(ifspec_name):
    gt = read_file(os.path.join(IFSPEC_DIR, ifspec_name, "ground-truth.txt")).strip().upper()
    return "INSECURE" if "INSECURE" in gt else "SECURE"


def canonical_name(ifspec_name):
    n = ifspec_name
    if n.endswith("-secure"):
        return n, "SECURE"
    if n.lower().endswith("-unsecure"):
        return re.sub(r"-[Uu]nsecure$", "-unsecure", n), "INSECURE"
    if n.lower().endswith("-insecure"):
        return re.sub(r"-[Ii]nsecure$", "", n) + "-unsecure", "INSECURE"
    gt = read_ground_truth(ifspec_name)
    return n + ("-unsecure" if gt == "INSECURE" else "-secure"), gt


# ---------------------------------------------------------------------------
# Phosphor annotation
# ---------------------------------------------------------------------------

PHOSPHOR_IMPORTS = (
    "import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor\n"
    "import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor\n"
    "import java.util.Arrays; // @Phosphor\n"
)

PRIMITIVE_TAINT = {
    "int":     "taintedInt",   "byte":    "taintedByte",
    "short":   "taintedShort", "long":    "taintedLong",
    "float":   "taintedFloat", "double":  "taintedDouble",
    "boolean": "taintedBoolean","char":   "taintedChar",
}


def generate_phosphor_java(source, method_name, settings_conf):
    policy = {}
    for line in settings_conf.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            policy[k.strip()] = v.strip()
    h_params = [k for k, v in policy.items() if v == "H" and k != "ret"]

    lines  = source.splitlines()
    insert = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith(("import ", "package ")):
            insert = i + 1
    lines  = lines[:insert] + PHOSPHOR_IMPORTS.splitlines() + lines[insert:]
    source = "\n".join(lines)

    method_pat = (
        rf"((?:public|protected|private|static|final|synchronized|native|abstract|\s)*"
        rf"\w[\w<>\[\]]*\s+{re.escape(method_name)}\s*\([^)]*\)"
        rf"(?:\s*throws\s+[\w,\s]+)?)"
        rf"\s*\{{"
    )
    m = re.search(method_pat, source)
    if not m:
        return source, False

    taint_lines = []
    sig_m = re.search(
        rf"(?:public|protected|private|static|final|synchronized)\s+"
        rf"(?:[\w<>\[\]]+\s+)+{re.escape(method_name)}\s*\(([^)]*)\)",
        source,
    )
    if sig_m:
        for param in h_params:
            for part in sig_m.group(1).split(","):
                parts = part.strip().split()
                if len(parts) >= 2 and parts[-1] == param:
                    ptype = parts[-2].rstrip("[]")
                    if ptype.lower() in PRIMITIVE_TAINT:
                        fn = PRIMITIVE_TAINT[ptype.lower()]
                        taint_lines.append(
                            f'\n        {param} = MultiTainter.{fn}({param}, "{param}_"); // @Phosphor'
                        )

    if taint_lines:
        ins    = m.end()
        source = source[:ins] + "".join(taint_lines) + source[ins:]

    return source, True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(os.path.join(ARTIFACTS, "selected_50_samples.json")) as f:
        orig_selected = json.load(f)

    # Use ifspec_names if present, else canonical sample names mapped back
    if "ifspec_names" in orig_selected:
        selected = orig_selected["ifspec_names"]
    else:
        selected = orig_selected["samples"]

    fixed_samples  = []
    incompatible   = []

    print("=== Fixing Java sources in generated-settings/ ===\n")

    for ifspec_name in selected:
        gen_dir = os.path.join(GEN_SETTINGS, ifspec_name)
        if not os.path.isdir(gen_dir):
            print(f"  SKIP {ifspec_name}: no generated-settings dir")
            incompatible.append({"name": ifspec_name, "reason": "no-generated-settings"})
            continue

        if ifspec_name in TRY_CATCH_SKIP:
            print(f"  SKIP {ifspec_name}: try-catch incompatibility")
            incompatible.append({"name": ifspec_name, "reason": "try-catch"})
            continue

        if ifspec_name in METHOD_MISMATCH_SKIP:
            print(f"  SKIP {ifspec_name}: method not in class")
            incompatible.append({"name": ifspec_name, "reason": "method-mismatch"})
            continue

        if ifspec_name in FUZZER_SKIP:
            print(f"  SKIP {ifspec_name}: unsupported parameter/return type")
            incompatible.append({"name": ifspec_name, "reason": "fuzzer-incompatible"})
            continue

        java_files = glob.glob(os.path.join(gen_dir, "*.java"))
        if not java_files:
            print(f"  SKIP {ifspec_name}: no .java file")
            incompatible.append({"name": ifspec_name, "reason": "no-java-file"})
            continue

        java_path   = java_files[0]
        method_txt  = read_file(os.path.join(gen_dir, "method.txt")).splitlines()
        settings_cf = read_file(os.path.join(gen_dir, "settings.conf"))
        method_name = method_txt[0].strip() if method_txt else None
        modifier    = method_txt[1].strip() if len(method_txt) > 1 else "static"
        source      = read_file(java_path)

        if not method_name:
            print(f"  SKIP {ifspec_name}: empty method.txt")
            incompatible.append({"name": ifspec_name, "reason": "no-method"})
            continue

        ret_type, has_try, is_public = get_method_info(source, method_name)

        if ret_type is None:
            print(f"  SKIP {ifspec_name}: method '{method_name}' not found in class")
            incompatible.append({"name": ifspec_name, "reason": "method-not-found"})
            continue

        if ret_type == "void":
            print(f"  SKIP {ifspec_name}: void method")
            incompatible.append({"name": ifspec_name, "reason": "void-method"})
            continue

        if has_try:
            print(f"  SKIP {ifspec_name}: try-catch in method body")
            incompatible.append({"name": ifspec_name, "reason": "try-catch"})
            continue

        # Apply fixes
        source = fix_class_visibility(source, os.path.basename(java_path))
        source = fix_method_visibility(source, method_name)
        source, ok = add_ret_variable(source, method_name, ret_type)

        if not ok:
            print(f"  FAIL {ifspec_name}: couldn't rewrite returns")
            incompatible.append({"name": ifspec_name, "reason": "rewrite-failed"})
            continue

        write_file(java_path, source)
        print(f"  FIXED {ifspec_name}: {method_name}() -> {ret_type}")

        canon, gt = canonical_name(ifspec_name)
        fixed_samples.append((
            ifspec_name, canon, gt,
            os.path.basename(java_path), method_name, modifier, source, settings_cf,
        ))

    print(f"\n{len(fixed_samples)} fixed, {len(incompatible)} skipped\n")

    # ---------------------------------------------------------------------------
    # Rebuild datasets
    # ---------------------------------------------------------------------------
    print("=== Rebuilding datasets ===\n")

    for d in (NEW_DATASET, NEW_UNSECURE, NEW_PHOSPHOR):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)

    mapping              = []
    phosphor_incompatible = []

    for (ifspec_name, canon, gt, java_file, method_name, modifier, source, settings_cf) in fixed_samples:
        # NewDataset
        sample_dir  = os.path.join(NEW_DATASET, canon)
        program_dir = os.path.join(sample_dir, "program")
        os.makedirs(program_dir, exist_ok=True)
        write_file(os.path.join(program_dir, java_file), source)
        write_file(os.path.join(sample_dir, "method.txt"), f"{method_name}\n{modifier}\n")
        write_file(os.path.join(sample_dir, "settings.conf"), settings_cf)

        # NewUnsecureDataset
        if gt == "INSECURE":
            u_dir  = os.path.join(NEW_UNSECURE, canon)
            u_prog = os.path.join(u_dir, "program")
            os.makedirs(u_prog, exist_ok=True)
            write_file(os.path.join(u_prog, java_file), source)
            write_file(os.path.join(u_dir, "method.txt"), f"{method_name}\n{modifier}\n")
            write_file(os.path.join(u_dir, "settings.conf"), settings_cf)

        # NewDataset-phosphor
        p_dir    = os.path.join(NEW_PHOSPHOR, canon)
        os.makedirs(p_dir, exist_ok=True)
        p_src, p_ok = generate_phosphor_java(source, method_name, settings_cf)
        write_file(os.path.join(p_dir, java_file), p_src if p_ok else source)
        write_file(os.path.join(p_dir, "settings.conf"), settings_cf)
        if not p_ok:
            phosphor_incompatible.append(ifspec_name)

        mapping.append({"ifspec": ifspec_name, "canonical": canon, "ground_truth": gt})
        print(f"  {canon} ({gt})")

    # ---------------------------------------------------------------------------
    # Persist artifacts
    # ---------------------------------------------------------------------------
    s_ct = sum(1 for m in mapping if m["ground_truth"] == "SECURE")
    i_ct = sum(1 for m in mapping if m["ground_truth"] == "INSECURE")

    with open(os.path.join(ARTIFACTS, "fixed_dataset_mapping.json"), "w") as f:
        json.dump({
            "total": len(mapping), "secure_count": s_ct, "insecure_count": i_ct,
            "mapping": mapping, "incompatible": incompatible,
        }, f, indent=2)

    with open(os.path.join(ARTIFACTS, "phosphor_incompatible.json"), "w") as f:
        json.dump({"count": len(phosphor_incompatible), "samples": phosphor_incompatible}, f, indent=2)

    with open(os.path.join(ARTIFACTS, "selected_50_samples.json"), "w") as f:
        json.dump({
            "seed": 42, "requested": 50, "available": len(mapping),
            "samples": [m["canonical"] for m in mapping],
            "ifspec_names": [m["ifspec"] for m in mapping],
        }, f, indent=2)

    print(f"\nNewDataset:          {len(mapping)} ({s_ct} secure, {i_ct} insecure)")
    print(f"NewUnsecureDataset:  {i_ct} insecure")
    print(f"NewDataset-phosphor: {len(mapping)} ({len(phosphor_incompatible)} without annotation)")


if __name__ == "__main__":
    main()
