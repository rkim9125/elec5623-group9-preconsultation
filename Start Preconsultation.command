#!/bin/bash
cd "$(dirname "$0")"
bash scripts/start-local.sh
open 'http://127.0.0.1:8000/#/patient'
