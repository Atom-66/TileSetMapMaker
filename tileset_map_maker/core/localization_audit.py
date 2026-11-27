"""
Automated localization completeness and hardcoded-string auditor for TileSet Map Maker.

Run directly before building or in CI:
    python -m tileset_map_maker.core.localization_audit
"""

import ast
import os
import re
import string
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple


_UI_FUNCS: Set[str] = {
    "QLabel", "ElidedLabel", "QPushButton", "QToolButton", "QCheckBox", "QRadioButton",
    "SwitchToggle", "QGroupBox", "QAction", "QMenu", "QDockWidget", "QProgressDialog",
    "setText", "setWindowTitle", "setToolTip", "setStatusTip", "setPlaceholderText",
    "setTitle", "setLabelText", "setCancelButtonText", "setHeaderLabels",
    "addAction", "addItem", "addItems", "addTab", "addRow", "addMenu", "addButton",
    "information", "warning", "critical", "question", "about",
    "getOpenFileName", "getOpenFileNames", "getSaveFileName", "getExistingDirectory",
    "getText", "getItem", "getInt", "showMessage", "show_notification", "notify",
    "setTabText",
}

# Intentional non-translated technical strings (blend mode IDs, format masks, examples)
_ALLOWED_TECHNICAL_STRINGS: Set[str] = {
    "normal", "multiply", "screen", "overlay", "add",
    "path", "organic", "auto", "ID", "JSON (*.json)",
    "hp=100:integer, name=Goblin:string",
    "TileSet Map Maker",
}

_FORMATTER = string.Formatter()


@dataclass
class LocalizationAuditReport:
    en_key_count: int = 0
    pl_key_count: int = 0
    duplicate_en_keys: Dict[str, int] = field(default_factory=dict)
    duplicate_pl_keys: Dict[str, int] = field(default_factory=dict)
    missing_in_en: List[str] = field(default_factory=list)
    missing_in_pl: List[str] = field(default_factory=list)
    empty_en_keys: List[str] = field(default_factory=list)
    empty_pl_keys: List[str] = field(default_factory=list)
    param_mismatches: List[Tuple[str, Set[str], Set[str]]] = field(default_factory=list)
    missing_code_keys: List[Tuple[str, int, str]] = field(default_factory=list)
    hardcoded_ui_strings: List[Tuple[str, int, str, str]] = field(default_factory=list)
    potentially_unused_keys: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any([
            self.duplicate_en_keys,
            self.duplicate_pl_keys,
            self.missing_in_en,
            self.missing_in_pl,
            self.empty_en_keys,
            self.empty_pl_keys,
            self.param_mismatches,
            self.missing_code_keys,
            self.hardcoded_ui_strings,
        ])


def _get_format_fields(text: str) -> Set[str]:
    fields: Set[str] = set()
    for _, field_name, _, _ in _FORMATTER.parse(text):
        if field_name is not None:
            fields.add(field_name.split(".")[0].split("[")[0])
    return fields


def _contains_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-zÀ-ž]{2,}", text))


def _is_technical(text: str) -> bool:
    s = text.strip()
    if not s or len(s) <= 2 or s in _ALLOWED_TECHNICAL_STRINGS:
        return True
    if s.startswith(("#", "http", "Q", "/*")) or ("{" in s and ":" in s and ";" in s):
        return True
    if re.fullmatch(r"[a-z0-9_./:-]+", s) and ("_" in s or "/" in s or "." in s):
        return True
    if re.fullmatch(r"\d+\s*[x×]\s*\d+(\s*px)?", s):
        return True
    if re.fullmatch(r"[\d\s×x.,:%()\-–+/|{}]+(px|ms|MB)?", s):
        return True
    if re.fullmatch(r"(\{\.\.\.\}|[\s×x.,:%()\[\]\-–+/|]|px|ms|MB|TileSet Map Maker|Preset)+", s):
        return True
    if re.fullmatch(r"X:\s*\{[^}]+\}.*Y:\s*\{[^}]+\}.*", s):
        return True
    return False


def _is_tr_call(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in ("tr", "tr_plural"):
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("tr", "t", "tr_plural"):
            return True
    return False


def _extract_hardcoded(node: ast.AST) -> List[str]:
    if _is_tr_call(node):
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if _contains_letters(node.value) and not _is_technical(node.value):
            return [node.value]
        return []
    if isinstance(node, ast.JoinedStr):
        parts = []
        has_raw = False
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                if _contains_letters(v.value) and not _is_technical(v.value):
                    has_raw = True
                parts.append(v.value)
            else:
                parts.append("{...}")
        joined = "".join(parts)
        if has_raw and not _is_technical(joined):
            return [joined]
        return []
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _extract_hardcoded(node.left) + _extract_hardcoded(node.right)
    if isinstance(node, (ast.List, ast.Tuple)):
        out: List[str] = []
        for elt in node.elts:
            out.extend(_extract_hardcoded(elt))
        return out
    return []


def run_localization_audit(package_root: str) -> LocalizationAuditReport:
    """Performs a full AST + dictionary localization audit on `package_root`."""
    report = LocalizationAuditReport()
    loc_path = os.path.join(package_root, "core", "localization.py")
    with open(loc_path, encoding="utf-8") as f:
        loc_tree = ast.parse(f.read(), filename=loc_path)

    trans_node = None
    for node in loc_tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "TRANSLATIONS":
            trans_node = node.value
            break
    if trans_node is None or not isinstance(trans_node, ast.Dict):
        raise RuntimeError(f"TRANSLATIONS dict not found in {loc_path}")

    dicts: Dict[str, Dict[str, str]] = {}
    dupes: Dict[str, Dict[str, int]] = {}
    for k_node, v_node in zip(trans_node.keys, trans_node.values):
        lang = k_node.value
        counts = Counter()
        d: Dict[str, str] = {}
        for dk, dv in zip(v_node.keys, v_node.values):
            key = dk.value
            val = dv.value
            counts[key] += 1
            d[key] = val
        dicts[lang] = d
        dupes[lang] = {k: c for k, c in counts.items() if c > 1}

    en = dicts.get("en", {})
    pl = dicts.get("pl", {})
    report.en_key_count = len(en)
    report.pl_key_count = len(pl)
    report.duplicate_en_keys = dupes.get("en", {})
    report.duplicate_pl_keys = dupes.get("pl", {})
    report.missing_in_pl = sorted(set(en) - set(pl))
    report.missing_in_en = sorted(set(pl) - set(en))
    report.empty_en_keys = sorted(k for k, v in en.items() if not v.strip())
    report.empty_pl_keys = sorted(k for k, v in pl.items() if not v.strip())

    for key in sorted(set(en) & set(pl)):
        fe = _get_format_fields(en[key])
        fp = _get_format_fields(pl[key])
        if fe != fp:
            report.param_mismatches.append((key, fe, fp))

    used_keys: Set[str] = set()
    used_prefixes: Set[str] = set()
    ui_dir = os.path.abspath(os.path.join(package_root, "ui"))

    for root, _, files in os.walk(package_root):
        for fn in sorted(files):
            if not fn.endswith(".py") or fn in ("localization.py", "localization_audit.py"):
                continue
            full_path = os.path.join(root, fn)
            rel_path = os.path.relpath(full_path, os.path.dirname(package_root))
            with open(full_path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=full_path)

            is_ui_file = os.path.abspath(full_path).startswith(ui_dir)

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else None)
                )

                # Skip logger.warning / logger.info / logger.error calls
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if node.func.value.id in ("logger", "logging"):
                        continue
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Attribute):
                    if node.func.value.attr == "logger":
                        continue

                if fn_name in ("tr", "tr_plural") and node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        k = arg0.value
                        if fn_name == "tr_plural":
                            for suffix in (".one", ".few", ".many"):
                                fk = f"{k}{suffix}"
                                used_keys.add(fk)
                                if fk not in en or fk not in pl:
                                    report.missing_code_keys.append((rel_path, node.lineno, fk))
                        else:
                            used_keys.add(k)
                            if k not in en or k not in pl:
                                report.missing_code_keys.append((rel_path, node.lineno, k))
                    elif isinstance(arg0, ast.JoinedStr) and arg0.values:
                        first = arg0.values[0]
                        if isinstance(first, ast.Constant) and isinstance(first.value, str):
                            used_prefixes.add(first.value)

                if is_ui_file and fn_name in _UI_FUNCS:
                    for arg in node.args:
                        for raw in _extract_hardcoded(arg):
                            report.hardcoded_ui_strings.append((rel_path, node.lineno, fn_name, raw))
                    for kw in node.keywords:
                        if kw.arg in ("text", "title", "label", "tooltip", "placeholder", "message"):
                            for raw in _extract_hardcoded(kw.value):
                                report.hardcoded_ui_strings.append((rel_path, node.lineno, fn_name, raw))

    # Also detect string-literal keys stored in dicts/tuples (e.g. ("act_new", "action.new"))
    all_keys = set(en) | set(pl)
    for root, _, files in os.walk(package_root):
        for fn in sorted(files):
            if not fn.endswith(".py") or fn in ("localization.py", "localization_audit.py"):
                continue
            full_path = os.path.join(root, fn)
            with open(full_path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=full_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in all_keys:
                        used_keys.add(node.value)

    report.potentially_unused_keys = sorted(
        k
        for k in all_keys
        if k not in used_keys and not any(k.startswith(p) for p in used_prefixes)
    )
    return report


def main() -> int:
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    report = run_localization_audit(pkg_root)
    print(f"Localization Audit: EN={report.en_key_count}, PL={report.pl_key_count}")
    print(f"  Duplicate EN keys: {len(report.duplicate_en_keys)}")
    print(f"  Duplicate PL keys: {len(report.duplicate_pl_keys)}")
    print(f"  Missing in EN: {len(report.missing_in_en)}")
    print(f"  Missing in PL: {len(report.missing_in_pl)}")
    print(f"  Empty EN/PL: {len(report.empty_en_keys)}/{len(report.empty_pl_keys)}")
    print(f"  Param mismatches: {len(report.param_mismatches)}")
    print(f"  Missing code keys: {len(report.missing_code_keys)}")
    print(f"  Hardcoded UI strings: {len(report.hardcoded_ui_strings)}")
    print(f"  Potentially unused keys (info): {len(report.potentially_unused_keys)}")

    for item in report.missing_code_keys:
        print(f"  [MISSING KEY] {item[0]}:{item[1]} -> {item[2]}")
    for item in report.hardcoded_ui_strings:
        print(f"  [HARDCODED UI] {item[0]}:{item[1]} [{item[2]}] {item[3]!r}")
    for key, fe, fp in report.param_mismatches:
        print(f"  [PARAM MISMATCH] {key}: en={fe} vs pl={fp}")

    return 1 if report.has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
