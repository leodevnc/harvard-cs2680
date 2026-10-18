"""Download course infrastructure without overwriting implementation files."""
import argparse
import hashlib
import io
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def install(number, archive=None):
    url = f'https://cs2680.com/assignments/assignment{number}.tar.gz'
    data = Path(archive).read_bytes() if archive else urllib.request.urlopen(url, timeout=60).read()
    written, kept = [], []
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        for member in tar.getmembers():
            name = PurePosixPath(member.name)
            parts = tuple(p for p in name.parts if p != '.')
            if name.is_absolute() or '..' in parts or not parts or parts[0] != f'assignment{number}':
                raise ValueError('Archive path outside expected assignment directory')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Archive contains a link or special file')
            target = ROOT.joinpath(*parts)
            if not target.resolve().is_relative_to((ROOT / f'assignment{number}').resolve()):
                raise ValueError('Destination symlink escape')
            if target.exists():
                kept.append(str(name)); continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source:
                target.write_bytes(source.read())
            target.chmod(member.mode & 0o777)
            written.append(str(name))
    print(f'Archive sha256: {hashlib.sha256(data).hexdigest()}')
    print(f'Installed {len(written)} missing official files; preserved {len(kept)} existing files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assignment', type=int, choices=[2, 3])
    parser.add_argument('--archive', help='Use a manually downloaded official tar.gz')
    args = parser.parse_args()
    install(args.assignment, args.archive)
