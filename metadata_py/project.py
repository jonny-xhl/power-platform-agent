"""
Project manifest for the framework_power development workflow (Phase 9).

This is the single integration point: ``python -m framework_power workflow deploy`` runs the whole
development chain across **two solutions** in dependency order::

    Global Optionset -> Entity (+ Relationship) -> webresource -> plugin -> form -> view -> [roles] -> ribbon
    |<----------------------- main_solution --------------------->|                |<-- ribbon_solution -->|

Every component is listed explicitly here. Each stage self-manages its solution membership (the
deploy/sync functions take ``solution=``), so the workflow only sequences stages + ensures the two
solution shells + runs a final PublishAllXml.

Lists are STEMS resolved against their type dir (``metadata_py/<type>/<stem>.py``), except:
- ``tables`` / ``roles``: name refs resolved via the phase registries (``get_definition`` /
  ``get_role_definition``).
- ``plugins``: project directories (each with a ``plugin_def.py``).
- ``webresources``: a bool — sync the whole ``webresources/`` dir into the main solution.

CLI:
    python -m framework_power workflow show
    python -m framework_power workflow lint
    python -m framework_power workflow plan  --env dev
    python -m framework_power workflow deploy --env dev [--skip plugins] [--include-roles]
"""

from framework_power import Project, Publisher

PUBLISHER = Publisher(name="new", display_name="PP", prefix="new")

PROJECT = Project(
    main_solution="new_WorkflowSoln",      # created on first deploy; holds everything except ribbon
    ribbon_solution="new_RibbonSoln",      # dedicated ribbon solution (Phase 7); ribbon has no Web API write path
    publisher=PUBLISHER,
    version="1.0.0.0",
    # ---- stage 1: global optionsets (stems -> metadata_py/optionsets/<stem>.py) ----
    optionsets=[],                         # e.g. ["new_category"]
    # ---- stage 2: tables, name refs -> metadata_py/tables/ (deployed in dependency order) ----
    tables=["new_projectbudget"],
    # ---- stage 3: webresources (bool: sync the whole webresources/ dir, code 61 + targeted publish) ----
    webresources=True,
    # ---- stage 4: plugins (project dirs; built with dotnet + deployed, code 10030/+92) ----
    plugins=["plugins/Smoke"],
    # ---- stage 5: forms (stems -> metadata_py/forms/<stem>.py, e.g. "{entity}__{Name}", code 60) ----
    forms=[],                              # e.g. ["new_projectbudget__Information"]
    # ---- stage 6: views (stems -> metadata_py/views/<stem>.py, code 26) ----
    views=[],                              # e.g. ["new_projectbudget__Active"]
    # ---- stage 7 (opt-in --include-roles): roles, name refs -> metadata_py/roles/ (privilege sync + code 20) ----
    roles=[],
    # ---- stage 8: ribbons (stems -> metadata_py/ribbons/<stem>.py; deploy via the dedicated ribbon solution) ----
    ribbons=[],                            # e.g. ["new_projectbudget"]
)
