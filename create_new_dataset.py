"""
Create the new experiment datasets from generated-settings/:

  replication-package/datasets/NewDataset/          <- for RQ1/RQ2/RQ3 (HyperTest)
  replication-package/datasets/NewUnsecureDataset/  <- for RQ1 (vulnerable only)
  replication-package/datasets/NewDataset-phosphor/ <- for RQ3 (Phosphor)

Naming convention enforced: sample dirs must end in -secure or -unsecure
for the ground-truth detection in the experiment scripts.

Phosphor annotation: auto-generate MultiTainter calls for H parameters
and Taint checks for the return value.
"""

import os, re, json, glob, shutil

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
IFSPEC_DIR      = os.path.join(BASE_DIR, "workspace", "ifspec", "JavaSourceCode")
GEN_SETTINGS    = os.path.join(BASE_DIR, "generated-settings")
REPLICATION_PKG = os.path.join(BASE_DIR, "replication-package")
DATASETS_DIR    = os.path.join(REPLICATION_PKG, "datasets")

NEW_DATASET         = os.path.join(DATASETS_DIR, "NewDataset")
NEW_UNSECURE        = os.path.join(DATASETS_DIR, "NewUnsecureDataset")
NEW_PHOSPHOR        = os.path.join(DATASETS_DIR, "NewDataset-phosphor")
ARTIFACTS_DIR       = os.path.join(BASE_DIR, "artifacts")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def read_ground_truth(ifspec_name):
    gt_path = os.path.join(IFSPEC_DIR, ifspec_name, "ground-truth.txt")
    content = read_file(gt_path).strip().upper()
    return "INSECURE" if "INSECURE" in content else "SECURE"


def get_sample_canonical_name(ifspec_name):
    """
    Return (canonical_name, ground_truth) where canonical_name ends in
    -secure or -unsecure, suitable for the experiment scripts.
    """
    name = ifspec_name

    # Already has a recognized suffix
    if name.endswith("-secure"):
        return name, "SECURE"
    if name.lower().endswith("-unsecure"):
        # normalize case
        return re.sub(r'-[Uu]nsecure$', '-unsecure', name), "INSECURE"
    if name.lower().endswith("-insecure"):
        base = re.sub(r'-[Ii]nsecure$', '', name)
        return base + "-unsecure", "INSECURE"

    # No suffix: use ground-truth.txt
    gt = read_ground_truth(ifspec_name)
    suffix = "-unsecure" if gt == "INSECURE" else "-secure"
    return name + suffix, gt


PHOSPHOR_IMPORTS = """\
import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
"""

PRIMITIVE_TAINT = {
    "int":     "taintedInt",
    "byte":    "taintedByte",
    "short":   "taintedShort",
    "long":    "taintedLong",
    "float":   "taintedFloat",
    "double":  "taintedDouble",
    "boolean": "taintedBoolean",
    "char":    "taintedChar",
}


def get_param_type(java_source, method_name, param_name):
    """
    Extract the declared type of param_name in method_name's signature.
    Returns None if not found.
    """
    pattern = rf'(?:public|protected|private|static|final|synchronized)[\s\w<>\[\]]*\b{re.escape(method_name)}\s*\(([^)]*)\)'
    m = re.search(pattern, java_source)
    if not m:
        return None
    params_str = m.group(1)
    for part in params_str.split(","):
        parts = part.strip().split()
        if len(parts) >= 2 and parts[-1].strip("[]") == param_name:
            return parts[-2].strip("[]")
    return None


def generate_phosphor_java(java_source, method_name, settings_conf):
    """
    Transform java_source by adding Phosphor taint calls.
    - H parameters of the test method get tainted at method entry
    - Return value gets a Taint check before every return statement
    Returns (modified_source, success).
    """
    # Parse H/L from settings.conf
    policy = {}
    for line in settings_conf.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            policy[k.strip()] = v.strip()

    h_params = [k for k, v in policy.items() if v == "H" and k != "ret"]
    ret_hl   = policy.get("ret", "L")

    # Add phosphor imports at the top (after any existing imports)
    lines = java_source.splitlines()
    insert_pos = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("import ") or line.strip().startswith("package "):
            insert_pos = i + 1
    lines = lines[:insert_pos] + PHOSPHOR_IMPORTS.splitlines() + lines[insert_pos:]
    source = "\n".join(lines)

    # Find the method body and insert taint calls for H params
    method_pat = (
        rf'((?:public|protected|private|static|final|synchronized|native|abstract|\s)*'
        rf'\w[\w<>\[\]]*\s+{re.escape(method_name)}\s*\([^)]*\)'
        rf'(?:\s*throws\s+[\w,\s]+)?)'
        rf'\s*\{{'
    )
    m = re.search(method_pat, source)
    if not m:
        return source, False

    method_header_end = m.end()  # position just after the opening {

    taint_lines = []
    for param in h_params:
        ptype = get_param_type(source, method_name, param)
        if ptype and ptype.lower() in PRIMITIVE_TAINT:
            fn = PRIMITIVE_TAINT[ptype.lower()]
            taint_lines.append(
                f'\n        {param} = MultiTainter.{fn}({param}, "{param}_"); // @Phosphor'
            )
        # For object types, skip automatic taint (complex) — just note it

    if taint_lines:
        source = (
            source[:method_header_end]
            + "".join(taint_lines)
            + source[method_header_end:]
        )

    # Add taint check before return statements inside the method body
    if ret_hl == "L":
        # Find the method body extent and replace "return X;" with check + return
        def add_taint_check(m2):
            ret_expr = m2.group(1).strip()
            if ret_expr == "":  # void return
                return m2.group(0)
            check = (
                f'\n        Taint taint__ret = MultiTainter.getTaint({ret_expr}); // @Phosphor'
                f'\n        if (taint__ret != null && taint__ret.getLabels().length > 0) {{'  # @Phosphor
                f'\n            System.out.println("Phosphor: \'ret\' is tainted"); // @Phosphor'
                f'\n            System.out.println("Phosphor: taint labels " + Arrays.toString(taint__ret.getLabels())); // @Phosphor'
                f'\n        }} else System.out.println("Phosphor: \'ret\' is not tainted"); // @Phosphor'
                f'\n        return {ret_expr};'
            )
            return check
        source = re.sub(r'return\s+([^;]+);', add_taint_check, source)

    return source, True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load selected samples
    with open(os.path.join(ARTIFACTS_DIR, "selected_50_samples.json")) as f:
        selected = json.load(f)["samples"]

    # Clean and recreate dataset dirs
    for d in (NEW_DATASET, NEW_UNSECURE, NEW_PHOSPHOR):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)

    mapping = []  # (ifspec_name, canonical_name, ground_truth)
    skipped = []

    for ifspec_name in selected:
        gen_dir = os.path.join(GEN_SETTINGS, ifspec_name)
        if not os.path.isdir(gen_dir):
            print(f"SKIP {ifspec_name}: no generated-settings dir")
            skipped.append(ifspec_name)
            continue

        method_txt = os.path.join(gen_dir, "method.txt")
        settings_conf_path = os.path.join(gen_dir, "settings.conf")
        java_files = glob.glob(os.path.join(gen_dir, "*.java"))

        if not java_files or not os.path.isfile(method_txt) or not os.path.isfile(settings_conf_path):
            print(f"SKIP {ifspec_name}: missing files")
            skipped.append(ifspec_name)
            continue

        canon_name, ground_truth = get_sample_canonical_name(ifspec_name)
        mapping.append((ifspec_name, canon_name, ground_truth))

        java_path = java_files[0]
        java_source = read_file(java_path)
        settings_conf = read_file(settings_conf_path)
        method_lines = read_file(method_txt).splitlines()
        method_name = method_lines[0].strip() if method_lines else "main"
        modifier = method_lines[1].strip() if len(method_lines) > 1 else "static"

        # ----- NewDataset -----
        sample_dir = os.path.join(NEW_DATASET, canon_name)
        program_dir = os.path.join(sample_dir, "program")
        os.makedirs(program_dir)
        shutil.copy(java_path, os.path.join(program_dir, os.path.basename(java_path)))
        with open(os.path.join(sample_dir, "method.txt"), "w") as f:
            f.write(f"{method_name}\n{modifier}\n")
        with open(os.path.join(sample_dir, "settings.conf"), "w") as f:
            f.write(settings_conf)

        # ----- NewUnsecureDataset (vulnerable only) -----
        if ground_truth == "INSECURE":
            u_dir = os.path.join(NEW_UNSECURE, canon_name)
            u_prog = os.path.join(u_dir, "program")
            os.makedirs(u_prog)
            shutil.copy(java_path, os.path.join(u_prog, os.path.basename(java_path)))
            with open(os.path.join(u_dir, "method.txt"), "w") as f:
                f.write(f"{method_name}\n{modifier}\n")
            with open(os.path.join(u_dir, "settings.conf"), "w") as f:
                f.write(settings_conf)

        # ----- NewDataset-phosphor -----
        phosphor_java, ok = generate_phosphor_java(java_source, method_name, settings_conf)
        p_dir = os.path.join(NEW_PHOSPHOR, canon_name)
        os.makedirs(p_dir)
        with open(os.path.join(p_dir, os.path.basename(java_path)), "w") as f:
            f.write(phosphor_java)
        with open(os.path.join(p_dir, "settings.conf"), "w") as f:
            f.write(settings_conf)
        if not ok:
            print(f"  WARNING: Phosphor annotation may be incomplete for {ifspec_name}")

        print(f"  {ifspec_name} -> {canon_name} ({ground_truth})")

    # Save mapping to artifact
    secure_count   = sum(1 for _, _, g in mapping if g == "SECURE")
    insecure_count = sum(1 for _, _, g in mapping if g == "INSECURE")
    artifact = {
        "total": len(mapping),
        "secure_count": secure_count,
        "insecure_count": insecure_count,
        "skipped": skipped,
        "mapping": [{"ifspec": i, "canonical": c, "ground_truth": g} for i, c, g in mapping],
    }
    with open(os.path.join(ARTIFACTS_DIR, "dataset_mapping.json"), "w") as f:
        json.dump(artifact, f, indent=2)

    print(f"\nNewDataset:         {len(mapping)} samples ({secure_count} secure, {insecure_count} insecure)")
    print(f"NewUnsecureDataset: {insecure_count} samples")
    print(f"NewDataset-phosphor:{len(mapping)} samples (with phosphor annotations)")
    print(f"Skipped: {len(skipped)}")


if __name__ == "__main__":
    main()
