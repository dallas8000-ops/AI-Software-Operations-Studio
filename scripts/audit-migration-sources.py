"""Read-only SQLite inventory for Studio migration planning."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def inspect_database(path: Path) -> dict:
    resolved = path.resolve()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result = {
            "path": str(resolved),
            "bytes": resolved.stat().st_size,
            "tables": {
                table: connection.execute(f'SELECT COUNT(1) FROM "{table}"').fetchone()[0]
                for table in tables
            },
        }
        if "projects_project" in tables:
            result["projects"] = [
                {
                    "id": row[0],
                    "name": row[1],
                    "slug": row[2],
                    "ownerId": row[3],
                    "organizationId": row[4],
                    "framework": row[5],
                    "language": row[6],
                    "hasLocalPath": bool(row[7]),
                    "hasGitUrl": bool(row[8]),
                    "vaultSecrets": row[9],
                    "pipelineRuns": row[10],
                }
                for row in connection.execute(
                    """
                    SELECT p.id, p.name, p.slug, p.owner_id, p.organization_id,
                           p.framework, p.language, p.local_path, p.git_url,
                           (SELECT COUNT(1) FROM vault_vaultsecret s WHERE s.project_id = p.id),
                           (SELECT COUNT(1) FROM runs_pipelinerun r WHERE r.project_id = p.id)
                    FROM projects_project p ORDER BY p.slug
                    """
                )
            ]
        elif "projects" in tables:
            result["projects"] = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT id, name, root_path AS rootPath, framework, github_repo AS githubRepo,
                           plan, last_score AS lastScore, public_slug AS publicSlug
                    FROM projects ORDER BY id
                    """
                )
            ]
        return result
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("databases", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([inspect_database(path) for path in args.databases], indent=2))


if __name__ == "__main__":
    main()
