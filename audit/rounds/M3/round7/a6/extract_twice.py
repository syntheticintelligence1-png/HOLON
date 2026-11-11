"""A6: extract a Go document twice from a scratch clone of the pinned checkout with HOLON's own frontend
(holon extract go, the document's own config), write each in the committed document's JSON format (as holon audit
mutation does), and compare the bytes with each other and with the committed file."""
import json, subprocess, sys, hashlib
from pathlib import Path
ROOT = Path(sys.argv[1]); src = Path(sys.argv[2]); out = Path(sys.argv[3]); rel = sys.argv[4]
sys.path.insert(0, str(ROOT))
from holon.audit.mutation import Doc, json_format
d = Doc(ROOT, rel)
stem = Path(rel).name[:-len('.json')]
for suf in ('.extracted', '.go'):
    stem = stem[:-len(suf)] if stem.endswith(suf) else stem
fmt = json_format(d.text) or (2, False)
res = {}
for i in (1, 2):
    o = out / f'run{i}'
    p = subprocess.run([sys.executable, '-m', 'holon', 'extract', 'go', '--root', str(ROOT), '--config', str(ROOT / d.config),
                        '--src', str(src), '--out-dir', str(o), '--doc', stem], cwd=str(ROOT), capture_output=True, text=True)
    f = o / f'{stem}.go.extracted.json'
    text = json.dumps(json.loads(f.read_text()), indent=fmt[0], sort_keys=True, ensure_ascii=fmt[1]) + '\n'
    res[f'run{i}'] = {'exit': p.returncode, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                      'raw_sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
    f.unlink()
res['committed_sha256'] = d.sha256
res['runs_identical'] = res['run1']['sha256'] == res['run2']['sha256'] and res['run1']['raw_sha256'] == res['run2']['raw_sha256']
res['reproduces_committed'] = res['run1']['sha256'] == d.sha256
print(json.dumps({rel: res}, indent=1))
