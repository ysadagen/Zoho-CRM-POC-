"""Zoho endpoint paths and URL builders.

All Zoho URLs are constructed here — no f-strings scattered across services or
the client. Paths are relative to the configured base URLs:

* OAuth lives on ``ZOHO_ACCOUNTS_URL`` (the data-centre accounts server).
* CRM module/record calls live on ``ZOHO_API_BASE_URL`` (already includes the
  ``/crm/v8`` version segment).
"""

from __future__ import annotations

# OAuth token endpoint, relative to ZOHO_ACCOUNTS_URL.
OAUTH_TOKEN_PATH = "/oauth/v2/token"

# CRM Users module, relative to ZOHO_API_BASE_URL. The ``type`` query param
# selects the cohort: ``AllUsers`` | ``ActiveUsers`` | ``CurrentUser`` | ...
USERS_PATH = "/users"

# CRM record modules ingested for productivity (Track A). These are the Zoho
# API module names; a record GET is ``{ZOHO_API_BASE_URL}/{module}``.
MODULE_LEADS = "Leads"
MODULE_CALLS = "Calls"
MODULE_EVENTS = "Events"  # Meetings live in the Events module
MODULE_TASKS = "Tasks"
MODULE_DEALS = "Deals"


def module_path(module: str) -> str:
    """Return the record-list path for a CRM ``module`` (e.g. ``/Leads``)."""
    return f"/{module}"


def accounts_url(base_url: str, path: str) -> str:
    """Join the accounts base URL with an OAuth ``path`` (no trailing slash)."""
    return f"{base_url.rstrip('/')}{path}"


def api_url(base_url: str, path: str) -> str:
    """Join the CRM API base URL with a module/record ``path``."""
    return f"{base_url.rstrip('/')}{path}"
