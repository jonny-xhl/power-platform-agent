#!/usr/bin/env python3
"""
Thin runner example: deploy the registered ``new_ProjectBudget`` definition.

The table definition lives in ``metadata_py/tables/new_projectbudget.py`` (the single
source of truth). This script just loads it and calls ``deploy_table`` — the same
thing ``python -m framework_power deploy new_projectbudget --env dev`` does, shown as
a programmatic entrypoint.

Usage:
    python -m framework_power.examples.setup_projectbudget --env dev
"""

from __future__ import annotations

import json

from metadata_py.tables.new_projectbudget import TABLE

from framework_power import deploy_table, get_client
from framework_power.runtime import argparse_env


def main() -> int:
    env = argparse_env(description="Deploy new_ProjectBudget")
    client = get_client(env)
    result = deploy_table(client, TABLE)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
