"""A7 evidence: GENV's unsafe-file scan versus the files bun actually loads, and the BendTT verdict of one committed
counter-law with and without a .env.local in its proof directory. Uses HOLON's own holon.bend functions."""
import os, sys
from pathlib import Path
repo = Path(sys.argv[1]); a = Path(sys.argv[2]); law = sys.argv[3]
sys.path.insert(0, str(repo))
os.chdir(repo)
from holon import bend
cfg = bend.config(repo)
proof = a / "gen/M3/proofs" / law / "PROOF.bend"
def verdict(tag):
    v = bend.check_verdict(proof, cfg)
    print(f"[{tag}] holon.bend.check_verdict ok={v.ok} code={v.code} first_line={v.first_line!r}")
    tail = [ln for ln in v.out.splitlines() if ln.strip()][-2:]
    print(f"[{tag}]   output tail: {tail}")
print("BENDTT in this process env:", os.environ.get("BENDTT"))
print("holon.bend.UNSAFE_ENV_FILES =", bend.UNSAFE_ENV_FILES)
verdict("no .env.local")
envf = proof.parent / ".env.local"
envf.write_text(f"BENDTT={a / 'fake-bendtt'}\n")
print("wrote", envf.relative_to(a), "=", envf.read_text().strip())
print("holon.bend.unsafe_env_files(root) with .env.local present:", bend.unsafe_env_files(a))
verdict("with .env.local")
print("fake kernel log:", (a / "fake-bendtt.log").read_text().strip() if (a / "fake-bendtt.log").exists() else None)
envf.unlink()
dev = proof.parent / ".env.development"
dev.write_text(f"BENDTT={a / 'fake-bendtt'}\n")
print("holon.bend.unsafe_env_files(root) with .env.development present:", bend.unsafe_env_files(a))
verdict("with .env.development")
dev.unlink()
plain = proof.parent / ".env"
plain.write_text("X=1\n")
print("holon.bend.unsafe_env_files(root) with .env present:", bend.unsafe_env_files(a))
plain.unlink()
