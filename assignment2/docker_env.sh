#!/usr/bin/env bash
set -euo pipefail
# Runtime uses only Python 3.10+ standard library; no network install is needed.
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
