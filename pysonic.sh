#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
source "${DIR}"/venv/bin/activate
(cd "${DIR}" && python3 -m pysonic "$@")
