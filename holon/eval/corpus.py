"""Historical defect evaluation corpus materialization, verification, and git provenance."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIDECAR = ROOT / "spec" / "M4" / "lib" / "corpus_controls.json"
DEFAULT_MANIFEST = ROOT / "spec" / "eval" / "corpus_manifest.json"
DEFAULT_CACHE_DIR = Path("/tmp/holon-corpus-cache")

_COMPARE_KEYS = (
    "corpus_id",
    "system",
    "repo_url",
    "language",
    "file_path",
    "target_files",
    "pre_fix_commit",
    "fix_commit",
    "commit_subject",
    "pre_fix_blob_sha",
    "fix_blob_sha",
    "patch_sha256",
    "rule",
    "subform",
    "label_1",
    "label_2",
    "labeller_1",
    "labeller_2",
    "agreement",
    "defect_summary",
    "excerpt_identifiers",
)


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_dir_for(entry: dict, cache_dir: Path) -> Path:
    slug = str(entry["repo_url"]).rstrip("/").rsplit("/", 1)[-1] + ".git"
    return Path(cache_dir) / slug


def _ext_for(language: str) -> str:
    return ".sol" if language == "solidity" else ".go"


def load_corpus_manifest(path: Path | str | None = None) -> dict:
    manifest_path = Path(path or DEFAULT_MANIFEST)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def materialize_corpus(
    sidecar_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    cache_dir: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    """Materialize `spec/eval/corpus_manifest.json` and `spec/eval/excerpts/<id>/*` from git cache."""
    base_root = Path(root or ROOT)
    s_path = Path(sidecar_path or (base_root / "spec" / "M4" / "lib" / "corpus_controls.json"))
    m_path = Path(manifest_path or (base_root / "spec" / "eval" / "corpus_manifest.json"))
    c_dir = Path(cache_dir or DEFAULT_CACHE_DIR)

    sidecar = json.loads(s_path.read_text(encoding="utf-8"))
    entries_out: list[dict] = []

    for raw_entry in sidecar["corpus"]:
        entry = copy.deepcopy(raw_entry)
        cid = entry["corpus_id"]
        ext = _ext_for(entry["language"])
        rel_dir = f"spec/eval/excerpts/{cid}"
        entry["pre_fix_excerpt"] = f"{rel_dir}/pre_fix{ext}"
        entry["fix_excerpt"] = f"{rel_dir}/fix{ext}"
        entry["patch_file"] = f"{rel_dir}/patch.diff"

        pre_out = base_root / entry["pre_fix_excerpt"]
        fix_out = base_root / entry["fix_excerpt"]
        patch_out = base_root / entry["patch_file"]
        pre_out.parent.mkdir(parents=True, exist_ok=True)

        repo_dir = _repo_dir_for(entry, c_dir)
        if repo_dir.is_dir():
            fp = entry["file_path"]
            p_rev = entry["pre_fix_commit"]
            f_rev = entry["fix_commit"]
            pre_bytes = subprocess.run(
                ["git", "-C", str(repo_dir), "cat-file", "blob", f"{p_rev}:{fp}"],
                capture_output=True,
                check=True,
            ).stdout
            fix_bytes = subprocess.run(
                ["git", "-C", str(repo_dir), "cat-file", "blob", f"{f_rev}:{fp}"],
                capture_output=True,
                check=True,
            ).stdout
            patch_bytes = subprocess.run(
                ["git", "-C", str(repo_dir), "diff", p_rev, f_rev, "--", fp],
                capture_output=True,
                check=True,
            ).stdout
            if git_blob_sha1(pre_bytes) != entry["pre_fix_blob_sha"]:
                raise ValueError(f"{cid}: extracted pre_fix_blob_sha mismatch")
            if git_blob_sha1(fix_bytes) != entry["fix_blob_sha"]:
                raise ValueError(f"{cid}: extracted fix_blob_sha mismatch")
            if sha256_bytes(patch_bytes) != entry["patch_sha256"]:
                raise ValueError(f"{cid}: extracted patch_sha256 mismatch")
            pre_out.write_bytes(pre_bytes)
            fix_out.write_bytes(fix_bytes)
            patch_out.write_bytes(patch_bytes)
        else:
            if not pre_out.is_file() or not fix_out.is_file() or not patch_out.is_file():
                raise FileNotFoundError(
                    f"{cid}: bare repo cache {repo_dir} not found and materialized excerpts missing under {pre_out.parent}"
                )
            if git_blob_sha1(pre_out.read_bytes()) != entry["pre_fix_blob_sha"]:
                raise ValueError(f"{cid}: existing pre_fix_blob_sha mismatch")
            if git_blob_sha1(fix_out.read_bytes()) != entry["fix_blob_sha"]:
                raise ValueError(f"{cid}: existing fix_blob_sha mismatch")
            if sha256_bytes(patch_out.read_bytes()) != entry["patch_sha256"]:
                raise ValueError(f"{cid}: existing patch_sha256 mismatch")

        entries_out.append(entry)

    cspec = sidecar["corpus_spec"]
    manifest = {
        "schema": "holon-corpus-manifest/0.1",
        "iteration": sidecar["iteration"],
        "milestone": sidecar["milestone"],
        "total_count": cspec["total_count"],
        "double_labelled_count": cspec["double_labelled_count"],
        "inter_rater_kappa": cspec["inter_rater_kappa"],
        "systems": list(cspec["systems"]),
        "rules": list(cspec["rules"]),
        "entries": entries_out,
    }
    m_path.parent.mkdir(parents=True, exist_ok=True)
    m_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_corpus(
    manifest_path: Path | str | None = None,
    sidecar_path: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    """Verify materialized corpus manifest, excerpts, patches, and identifier coverage."""
    base_root = Path(root or ROOT)
    m_path = Path(manifest_path or (base_root / "spec" / "eval" / "corpus_manifest.json"))
    s_path = Path(sidecar_path or (base_root / "spec" / "M4" / "lib" / "corpus_controls.json"))

    manifest = load_corpus_manifest(m_path)
    sidecar = json.loads(s_path.read_text(encoding="utf-8"))

    entries = manifest["entries"]
    sidecar_entries = sidecar["corpus"]
    if len(entries) != len(sidecar_entries):
        raise ValueError(f"corpus entry count mismatch: {len(entries)} != {len(sidecar_entries)}")

    by_system: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    by_language: Counter[str] = Counter()
    verified_records: list[dict] = []

    for got, exp in zip(entries, sidecar_entries):
        for k in _COMPARE_KEYS:
            if got.get(k) != exp.get(k):
                raise ValueError(f"mismatch on {exp['corpus_id']}.{k}: {got.get(k)!r} != {exp.get(k)!r}")

        cid = got["corpus_id"]
        pre_path = base_root / got["pre_fix_excerpt"]
        fix_path = base_root / got["fix_excerpt"]
        patch_path = base_root / got["patch_file"]

        pre_bytes = pre_path.read_bytes()
        fix_bytes = fix_path.read_bytes()
        patch_bytes = patch_path.read_bytes()

        if git_blob_sha1(pre_bytes) != got["pre_fix_blob_sha"]:
            raise ValueError(f"{cid}: pre_fix_blob_sha mismatch")
        if git_blob_sha1(fix_bytes) != got["fix_blob_sha"]:
            raise ValueError(f"{cid}: fix_blob_sha mismatch")
        if sha256_bytes(patch_bytes) != got["patch_sha256"]:
            raise ValueError(f"{cid}: patch_sha256 mismatch")

        pre_txt = pre_bytes.decode("utf-8")
        fix_txt = fix_bytes.decode("utf-8")
        patch_txt = patch_bytes.decode("utf-8")
        if "@@" not in patch_txt:
            raise ValueError(f"{cid}: patch.diff missing unified diff hunk header")

        for ident in got["excerpt_identifiers"]:
            if ident not in pre_txt:
                raise ValueError(f"{cid}: identifier {ident!r} missing in pre_fix excerpt")
            if ident not in fix_txt:
                raise ValueError(f"{cid}: identifier {ident!r} missing in fix excerpt")

        by_system[got["system"]] += 1
        by_rule[got["rule"]] += 1
        by_language[got["language"]] += 1
        verified_records.append(
            {
                "corpus_id": cid,
                "system": got["system"],
                "language": got["language"],
                "rule": got["rule"],
                "subform": got["subform"],
                "pre_fix_commit": got["pre_fix_commit"],
                "fix_commit": got["fix_commit"],
                "pre_fix_blob_sha": got["pre_fix_blob_sha"],
                "fix_blob_sha": got["fix_blob_sha"],
                "patch_sha256": got["patch_sha256"],
                "verified": True,
            }
        )

    return {
        "total_count": len(entries),
        "verified_count": len(verified_records),
        "double_labelled_count": manifest["double_labelled_count"],
        "inter_rater_kappa": manifest["inter_rater_kappa"],
        "by_system": dict(by_system),
        "by_rule": dict(by_rule),
        "by_language": dict(by_language),
        "entries": verified_records,
    }


def verify_git_provenance(
    manifest_path: Path | str | None = None,
    cache_dir: Path | str | None = None,
    root: Path | str | None = None,
) -> dict:
    """Verify git blob SHA-1s, patch SHA-256s, and (when cache_dir exists) live bare-repo git history."""
    base_root = Path(root or ROOT)
    m_path = Path(manifest_path or (base_root / "spec" / "eval" / "corpus_manifest.json"))
    c_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    manifest = load_corpus_manifest(m_path)

    checked: list[dict] = []
    for entry in manifest["entries"]:
        cid = entry["corpus_id"]
        pre_bytes = (base_root / entry["pre_fix_excerpt"]).read_bytes()
        fix_bytes = (base_root / entry["fix_excerpt"]).read_bytes()
        patch_bytes = (base_root / entry["patch_file"]).read_bytes()

        if git_blob_sha1(pre_bytes) != entry["pre_fix_blob_sha"]:
            raise ValueError(f"{cid}: pre_fix_blob_sha mismatch")
        if git_blob_sha1(fix_bytes) != entry["fix_blob_sha"]:
            raise ValueError(f"{cid}: fix_blob_sha mismatch")
        if sha256_bytes(patch_bytes) != entry["patch_sha256"]:
            raise ValueError(f"{cid}: patch_sha256 mismatch")

        repo_dir = _repo_dir_for(entry, c_dir)
        live_git_checked = False
        if repo_dir.is_dir():
            target_rel = entry["target_files"][0]
            t_fix = subprocess.run(
                ["git", "-C", str(repo_dir), "cat-file", "-t", entry["fix_commit"]],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if t_fix != "commit":
                raise ValueError(f"{cid}: expected commit object for {entry['fix_commit']}")
            parent_sha = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", f"{entry['fix_commit']}^1"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if parent_sha != entry["pre_fix_commit"]:
                raise ValueError(f"{cid}: parent commit mismatch {parent_sha} != {entry['pre_fix_commit']}")
            pre_blob = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", f"{entry['pre_fix_commit']}:{target_rel}"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            fix_blob = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", f"{entry['fix_commit']}:{target_rel}"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if pre_blob != entry["pre_fix_blob_sha"]:
                raise ValueError(f"{cid}: live git pre_fix_blob_sha mismatch")
            if fix_blob != entry["fix_blob_sha"]:
                raise ValueError(f"{cid}: live git fix_blob_sha mismatch")
            live_git_checked = True

        checked.append(
            {
                "corpus_id": cid,
                "system": entry["system"],
                "live_git_checked": live_git_checked,
                "verified": True,
            }
        )

    return {
        "verified_count": len(checked),
        "entries": checked,
    }
