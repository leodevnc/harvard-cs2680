"""Keep the leaderboard src package standalone; check prevents unnoticed divergence."""
import argparse
import hashlib
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assignment2/src/mads'
TARGET = ROOT / 'assignment3/starter_code/src/mads'


def sync(check=False):
    different = []
    for path in sorted(SOURCE.glob('*.py')):
        target = TARGET / path.name
        if not target.exists() or target.read_bytes() != path.read_bytes():
            different.append(path.name)
            if not check:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    if check and different:
        raise SystemExit('Runtime copies differ: ' + ', '.join(different))
    print('Runtime copies match' if check else f'Synchronized {len(different)} files')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    sync(parser.parse_args().check)
