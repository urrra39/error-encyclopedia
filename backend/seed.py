"""Seed the Error Encyclopedia with a handful of realistic software errors.

Run this once the stack is up to give the database and search index some real
content to exercise the UI and the `/api/search` endpoint::

    # Inside Docker (recommended):
    docker compose exec backend python seed.py

    # Or locally, from the backend/ directory with the venv active and a
    # reachable PostgreSQL + Meilisearch (see .env):
    python seed.py

The script is **idempotent**: errors are keyed by their slug, and any slug that
already exists is skipped rather than duplicated, so it is safe to re-run.

It reuses the application's own building blocks — :func:`crud.create_error`,
the Pydantic ``*Create`` schemas, and :mod:`search_index` — so seeded data goes
through exactly the same path as data created via the API.
"""

from __future__ import annotations

import asyncio
import logging

from crud import create_error, get_error_by_slug
from database import AsyncSessionLocal, dispose_engine, init_db
from models import Error
from schemas import ErrorCreate, RootCauseCreate, VerifiedFixCreate
from search_index import SearchIndexError, ensure_index, index_errors

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("error_encyclopedia.seed")


# ---------------------------------------------------------------------------
# Seed data — three common, real-world errors across Python and JavaScript.
# Explicit slugs keep the script idempotent on re-runs.
# ---------------------------------------------------------------------------

SEED_ERRORS: list[ErrorCreate] = [
    ErrorCreate(
        slug="modulenotfounderror-no-module-named",
        title="ModuleNotFoundError: No module named 'X'",
        plain_english_explanation=(
            "Python tried to import a module or package and couldn't find it on "
            "its import path. Almost always this means the package isn't "
            "installed in the interpreter that's actually running your code — or "
            "you're running a different Python (or virtual environment) than the "
            "one you installed it into."
        ),
        root_causes=[
            RootCauseCreate(
                description=(
                    "The package simply isn't installed in the active environment "
                    "(you installed it globally but are running inside a venv, or "
                    "vice versa)."
                )
            ),
            RootCauseCreate(
                description=(
                    "The import name differs from the install name — e.g. you "
                    "`pip install PyYAML` but `import yaml`, or install `Pillow` "
                    "but `import PIL`."
                )
            ),
            RootCauseCreate(
                description=(
                    "A virtual environment isn't activated, so `pip` and `python` "
                    "point at different interpreters."
                )
            ),
            RootCauseCreate(
                description=(
                    "You're running the script from a directory where your own "
                    "local package isn't importable (missing __init__.py or a "
                    "PYTHONPATH that doesn't include the project root)."
                )
            ),
        ],
        verified_fixes=[
            VerifiedFixCreate(
                explanation=(
                    "Install the missing package into the same interpreter you run "
                    "the code with. Using `python -m pip` (rather than a bare "
                    "`pip`) guarantees the install targets the active interpreter."
                ),
                before_code_snippet=(
                    "$ python app.py\n"
                    "Traceback (most recent call last):\n"
                    '  File "app.py", line 1, in <module>\n'
                    "    import requests\n"
                    "ModuleNotFoundError: No module named 'requests'"
                ),
                after_code_snippet=(
                    "$ python -m pip install requests\n"
                    "$ python app.py\n"
                    "# runs cleanly — requests is now importable"
                ),
            ),
            VerifiedFixCreate(
                explanation=(
                    "When the import name and the PyPI package name differ, install "
                    "the correct distribution but keep importing by its module name."
                ),
                before_code_snippet="import yaml  # ModuleNotFoundError: No module named 'yaml'",
                after_code_snippet=(
                    "# Install the distribution (note the different name):\n"
                    "#   python -m pip install PyYAML\n"
                    "import yaml  # now resolves"
                ),
            ),
        ],
    ),
    ErrorCreate(
        slug="cors-no-access-control-allow-origin",
        title="CORS Error: No 'Access-Control-Allow-Origin' header is present",
        plain_english_explanation=(
            "A browser blocked your frontend's request to an API on a different "
            "origin (a different scheme, host, or port) because the API's response "
            "didn't include the CORS headers the browser requires. This is a "
            "browser security policy — the request often reaches the server fine, "
            "but the browser refuses to expose the response to your JavaScript."
        ),
        root_causes=[
            RootCauseCreate(
                description=(
                    "The API server doesn't send any CORS headers, so the browser "
                    "assumes cross-origin access is disallowed."
                )
            ),
            RootCauseCreate(
                description=(
                    "The frontend's origin (e.g. http://localhost:3000) isn't in "
                    "the server's allow-list of permitted origins."
                )
            ),
            RootCauseCreate(
                description=(
                    "A preflight `OPTIONS` request fails because the required "
                    "method or custom headers aren't permitted by the server."
                )
            ),
            RootCauseCreate(
                description=(
                    "Credentialed requests are used with a wildcard `*` origin, "
                    "which the browser rejects — credentials require an explicit "
                    "origin."
                )
            ),
        ],
        verified_fixes=[
            VerifiedFixCreate(
                explanation=(
                    "Enable CORS on the API and explicitly allow the frontend's "
                    "origin. In FastAPI, add CORSMiddleware with the exact origins "
                    "your app is served from."
                ),
                before_code_snippet=(
                    "from fastapi import FastAPI\n\n"
                    "app = FastAPI()\n\n"
                    "# No CORS configured — the browser blocks calls from\n"
                    "# http://localhost:3000 with a missing-header error."
                ),
                after_code_snippet=(
                    "from fastapi import FastAPI\n"
                    "from fastapi.middleware.cors import CORSMiddleware\n\n"
                    "app = FastAPI()\n\n"
                    "app.add_middleware(\n"
                    "    CORSMiddleware,\n"
                    '    allow_origins=["http://localhost:3000"],\n'
                    "    allow_credentials=True,\n"
                    '    allow_methods=["*"],\n'
                    '    allow_headers=["*"],\n'
                    ")"
                ),
            ),
        ],
    ),
    ErrorCreate(
        slug="typeerror-cannot-read-properties-of-undefined",
        title="TypeError: Cannot read properties of undefined (reading 'x')",
        plain_english_explanation=(
            "Your JavaScript tried to read a property off a value that was "
            "`undefined` (or `null`). Usually the variable wasn't what you "
            "expected at that moment — an object hadn't loaded yet, an array "
            "lookup missed, or an API response was shaped differently than your "
            "code assumed."
        ),
        root_causes=[
            RootCauseCreate(
                description=(
                    "Accessing a nested property before the data has loaded — "
                    "common with async state in React before the first fetch "
                    "resolves."
                )
            ),
            RootCauseCreate(
                description=(
                    "An array `find`/index lookup returned `undefined` because no "
                    "element matched, and the result was then dereferenced."
                )
            ),
            RootCauseCreate(
                description=(
                    "The API response shape differs from what the code assumes "
                    "(e.g. `data.user` is missing or the payload is wrapped in "
                    "another key)."
                )
            ),
            RootCauseCreate(
                description="A typo in a property name yields `undefined`, which then chains.",
            ),
        ],
        verified_fixes=[
            VerifiedFixCreate(
                explanation=(
                    "Guard the access with optional chaining (`?.`) and provide a "
                    "fallback with nullish coalescing (`??`) so a missing value "
                    "degrades gracefully instead of throwing."
                ),
                before_code_snippet=(
                    "const user = users.find((u) => u.id === id);\n"
                    "// `user` is undefined when no id matches:\n"
                    "console.log(user.name); // TypeError: Cannot read properties of undefined"
                ),
                after_code_snippet=(
                    "const user = users.find((u) => u.id === id);\n"
                    'console.log(user?.name ?? "Unknown user");'
                ),
            ),
            VerifiedFixCreate(
                explanation=(
                    "In React, render against loading/empty states before reaching "
                    "into fetched data, so the component doesn't dereference "
                    "`undefined` on its first render."
                ),
                before_code_snippet=(
                    "function Profile({ userId }) {\n"
                    "  const { data } = useUser(userId);\n"
                    "  return <h1>{data.name}</h1>; // data is undefined on first render\n"
                    "}"
                ),
                after_code_snippet=(
                    "function Profile({ userId }) {\n"
                    "  const { data, isLoading } = useUser(userId);\n"
                    "  if (isLoading) return <Spinner />;\n"
                    "  if (!data) return <p>User not found.</p>;\n"
                    "  return <h1>{data.name}</h1>;\n"
                    "}"
                ),
            ),
        ],
    ),
]


async def seed() -> None:
    """Create the seed errors (skipping existing slugs) and index them."""
    # Make sure the schema and the search index both exist before we write.
    await init_db()
    logger.info("Database schema ready.")
    try:
        ensure_index()
        logger.info("Search index ready.")
    except SearchIndexError as exc:
        logger.warning("Could not ensure the search index now: %s", exc)

    created: list[Error] = []
    skipped: list[str] = []

    async with AsyncSessionLocal() as session:
        for payload in SEED_ERRORS:
            assert payload.slug is not None  # every seed entry sets an explicit slug
            existing = await get_error_by_slug(session, payload.slug)
            if existing is not None:
                skipped.append(payload.slug)
                logger.info("Skipping %r — already present.", payload.slug)
                continue
            error = await create_error(session, payload)
            created.append(error)
            logger.info("Created %r (%d causes, %d fixes).", error.slug,
                        len(error.root_causes), len(error.verified_fixes))
        await session.commit()

        # Push the freshly-created rows into Meilisearch so search returns them.
        # Done while the session is still open so the ORM instances (and their
        # eager-loaded relationships) are never accessed in a detached state.
        if created:
            try:
                index_errors(created)
                logger.info("Indexed %d new error(s) in Meilisearch.", len(created))
            except SearchIndexError as exc:
                logger.warning(
                    "Seeded the database, but indexing failed (%s). The rows "
                    "exist; restart the backend or re-run this script to index "
                    "them.",
                    exc,
                )

    logger.info(
        "Seeding complete: %d created, %d already present.",
        len(created),
        len(skipped),
    )


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
