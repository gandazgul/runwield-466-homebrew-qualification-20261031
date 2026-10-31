import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path.cwd()
BASE = 'bbc7d4b649aff76e447b6ec61f42a3b106c92bf5'
SOURCE = '1f78710b1e8bed0c19d8242bf20a5b7078d17c02'
EXPECTED = {
    'mnemoteca_0.3.4_darwin_arm64.tar.gz': 'b8e4a21c40ff3288b0792034e4cb847d7237c8c985c1c99989a8aac044479174',
    'mnemoteca_0.3.4_darwin_amd64.tar.gz': '550d1c9a9f5acd8921d9658b0ed14ad0529ae3d79dc329b210e0c6108490cacb',
}

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def manifest(path):
    return json.loads((path / 'runwield-homebrew-package.json').read_text())

def snapshot(path):
    return {str(p.relative_to(path)): digest(p) for p in path.rglob('*') if p.is_file() and '.git' not in p.relative_to(path).parts}

(ROOT / 'evidence').mkdir(exist_ok=True)
if sys.argv[1] == 'prepare':
    assert run('git', '-C', 'tap-base', 'rev-parse', 'HEAD') == BASE
    assert run('git', '-C', 'source', 'rev-parse', 'HEAD') == SOURCE
    assert digest(ROOT / 'repair.patch') == '763501e9c87d880f5fdcc487484268e26e4eb8ed8ed6ca855dca5fe3b321fcfe'
    shutil.copytree('tap-base', 'repair-publication', ignore=shutil.ignore_patterns('.git'))
    subprocess.run(['git', 'init', 'repair-publication'], check=True)
    subprocess.run(['git', '-C', 'repair-publication', 'apply', '--check', str(ROOT / 'repair.patch')], check=True)
    subprocess.run(['git', '-C', 'repair-publication', 'apply', str(ROOT / 'repair.patch')], check=True)
    before = manifest(ROOT / 'tap-base')
    after = manifest(ROOT / 'repair-publication')
    assert after['mnemotecaTag'] == 'v0.3.4'
    assert {k:v for k,v in before.items() if k not in ('mnemotecaTag','generatedAt')} == {k:v for k,v in after.items() if k not in ('mnemotecaTag','generatedAt')}
    before_files = snapshot(ROOT / 'tap-base')
    after_files = snapshot(ROOT / 'repair-publication')
    assert set(before_files) == set(after_files)
    assert sorted(k for k in before_files if before_files[k] != after_files[k]) == ['Formula/mnemoteca.rb','runwield-homebrew-package.json']
    assets = ROOT / 'mnemoteca-assets'
    assets.mkdir()
    release = json.loads(run('gh','api','repos/RunWield/mnemoteca/releases/tags/v0.3.4'))
    subprocess.run(['gh','release','download','v0.3.4','--repo','RunWield/mnemoteca','--dir',str(assets),'--pattern','checksums.txt','--pattern','mnemoteca_0.3.4_darwin_*.tar.gz'], check=True)
    checks = {line.split()[1].lstrip('*'):line.split()[0] for line in (assets/'checksums.txt').read_text().splitlines() if line.strip()}
    verified = {}
    for name in ['checksums.txt', *EXPECTED]:
        found = digest(assets/name)
        asset = next(a for a in release['assets'] if a['name'] == name)
        assert asset['digest'] == 'sha256:' + found
        if name in EXPECTED:
            assert found == checks[name] == EXPECTED[name]
        verified[name] = found
    shutil.copytree('repair-publication','tap-check')
    (ROOT/'evidence/preparation.json').write_text(json.dumps({'source':SOURCE,'tapBase':BASE,'patchSha256':digest(ROOT/'repair.patch'),'wldSha256':before_files['Formula/wld.rb'],'verifiedAssets':verified,'repairedManifest':after}, indent=2)+'\n')
elif sys.argv[1] == 'verify':
    mode = os.environ['MODE']
    repaired = ROOT/'repair-publication'
    checked = ROOT/'tap-check'
    assert snapshot(repaired)['Formula/mnemoteca.rb'] == snapshot(checked)['Formula/mnemoteca.rb']
    checked_manifest = manifest(checked)
    repaired_manifest = manifest(repaired)
    excluded = ('wldTag','testOnly','generatedAt')
    assert {k:v for k,v in checked_manifest.items() if k not in excluded} == {k:v for k,v in repaired_manifest.items() if k not in excluded}
    if mode == 'repair':
        assert snapshot(repaired) == snapshot(checked)
    else:
        assert checked_manifest['wldTag'] == ('v0.14.3' if mode == 'stable' else 'v0.14.4-rc.1')
        assert checked_manifest['testOnly'] == (mode == 'candidate')
    assert run('git','-C','tap-base','status','--porcelain') == ''
    version = run('brew','list','--versions','gandazgul/tap/mnemoteca')
    assert version == 'mnemoteca 0.3.4', version
    result = {'mode':mode,'source':SOURCE,'tapBase':BASE,'manifest':checked_manifest,'installedMnemoteca':version,'checkedFiles':snapshot(checked),'repairFiles':snapshot(repaired),'completedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidatePublished':False}
    (ROOT/'evidence/result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
else:
    raise ValueError(sys.argv[1])
