"""Copy existing FitSync records into a new database.

The source is read-only, and the output must be a new file.
"""

# Database transfer — Shared

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile


LEGACY_APPS = {
    "accounts",
    "memberships",
    "bookings",
    "workouts",
    "attendance",
    "activities",
    "notifications",
    "core",
    "ourteam",
    "aboutus",
    "reports",
}


def quoted(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def tables(connection):
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Existing ORIGINAL db.sqlite3 (read-only).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="NEW database path; must not already exist.",
    )
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if not source.is_file():
        parser.error("Source database does not exist.")
    if output.exists():
        parser.error(
            "Destination already exists. Choose another filename; nothing was overwritten."
        )
    if not output.parent.is_dir():
        parser.error("Destination parent folder does not exist.")

    project = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project))
    with tempfile.TemporaryDirectory(
        prefix="fitsync-import-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "single-app.sqlite3"
        snapshot = Path(temporary) / "source-snapshot.sqlite3"
        # SQLite backup provides a consistent snapshot, including committed WAL data.
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
            with sqlite3.connect(snapshot) as copy:
                original.backup(copy)

        os.environ["FITSYNC_PREVIEW_DB"] = str(staged)
        os.environ["DJANGO_SETTINGS_MODULE"] = "fitsync.settings"
        import django

        django.setup()
        from django.apps import apps
        from django.core.management import call_command
        from django.db import connections

        call_command("migrate", interactive=False, verbosity=0)
        app_models = list(
            apps.get_app_config("gym").get_models(include_auto_created=True)
        )
        table_models = {model._meta.db_table: model for model in app_models}
        label_map = {
            model._meta.model_name: "gym"
            for model in app_models
            if not model._meta.auto_created
        }
        connections.close_all()

        legacy = sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True)
        target = sqlite3.connect(staged)
        imported_counts = {}
        try:
            available = tables(legacy)
            new_public_tables = {
                "core_gymsettings",
                "core_contactmessage",
                "ourteam_teammember",
            }
            missing = set(table_models) - available - new_public_tables
            if missing:
                raise ValueError(
                    "Source schema is incomplete; missing tables: "
                    + ", ".join(sorted(missing))
                )
            unsupported_tables = sorted(
                table
                for table in available
                if table.split("_", 1)[0] in LEGACY_APPS and table not in table_models
            )
            for table in unsupported_tables:
                if legacy.execute("SELECT COUNT(*) FROM " + quoted(table)).fetchone()[
                    0
                ]:
                    raise ValueError(
                        f"{table} contains data for an incomplete/unsupported feature. Import refused to prevent data loss."
                    )
            if legacy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Source database failed its integrity check.")
            if legacy.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError(
                    "Source database has broken foreign keys. Import refused."
                )
            target.execute("PRAGMA foreign_keys=OFF")
            target.execute("BEGIN")

            # Fresh migration history, content types and permissions are kept.
            # Only business rows/groups are replaced with the snapshot's rows.
            for name in table_models:
                target.execute("DELETE FROM " + quoted(name))
            target.execute("DELETE FROM auth_group_permissions")
            target.execute("DELETE FROM auth_group")

            content_type_map = {}
            for old_id, app_label, model in legacy.execute(
                "SELECT id, app_label, model FROM django_content_type"
            ):
                new_label = (
                    label_map.get(model, app_label)
                    if app_label in LEGACY_APPS
                    else app_label
                )
                found = target.execute(
                    "SELECT id FROM django_content_type WHERE app_label=? AND model=?",
                    (new_label, model),
                ).fetchone()
                if found:
                    content_type_map[old_id] = found[0]
            permission_map = {}
            unsupported = []
            for old_id, name, old_type, codename in legacy.execute(
                "SELECT id, name, content_type_id, codename FROM auth_permission"
            ):
                new_type = content_type_map.get(old_type)
                if new_type is None:
                    unsupported.append(old_id)
                    continue
                found = target.execute(
                    "SELECT id FROM auth_permission WHERE content_type_id=? AND codename=?",
                    (new_type, codename),
                ).fetchone()
                if found is None:
                    new_id = target.execute(
                        "INSERT INTO auth_permission(name,content_type_id,codename) VALUES (?,?,?)",
                        (name, new_type, codename),
                    ).lastrowid
                else:
                    new_id = found[0]
                permission_map[old_id] = new_id

            def copy_rows(table, permission_column=None):
                if table not in available and table in new_public_tables:
                    imported_counts[table] = 0
                    return
                columns = [
                    row[1]
                    for row in legacy.execute(
                        "PRAGMA table_info(" + quoted(table) + ")"
                    )
                ]
                target_columns = [
                    row[1]
                    for row in target.execute(
                        "PRAGMA table_info(" + quoted(table) + ")"
                    )
                ]
                additions = set(target_columns) - set(columns)
                legacy_avatar = table == "accounts_memberprofile" and additions == {
                    "avatar_static_path"
                }
                if set(columns) != set(target_columns) and not legacy_avatar:
                    raise ValueError(
                        f"Schema differs for {table}; import refused rather than dropping fields."
                    )
                rows = legacy.execute(
                    "SELECT "
                    + ",".join(map(quoted, columns))
                    + " FROM "
                    + quoted(table)
                ).fetchall()
                if legacy_avatar:
                    columns.append("avatar_static_path")
                    rows = [tuple(row) + ("",) for row in rows]
                if permission_column:
                    index = columns.index(permission_column)
                    converted = []
                    for row in rows:
                        row = list(row)
                        if row[index] not in permission_map:
                            raise ValueError(
                                f"{table} assigns an unsupported legacy permission. Resolve this before importing."
                            )
                        row[index] = permission_map[row[index]]
                        converted.append(tuple(row))
                    rows = converted
                if rows:
                    target.executemany(
                        "INSERT INTO "
                        + quoted(table)
                        + "("
                        + ",".join(map(quoted, columns))
                        + ") VALUES ("
                        + ",".join("?" for _ in columns)
                        + ")",
                        rows,
                    )
                imported_counts[table] = len(rows)

            copy_rows("auth_group")
            for table in sorted(table_models):
                copy_rows(
                    table,
                    (
                        "permission_id"
                        if table == "accounts_user_user_permissions"
                        else None
                    ),
                )
            copy_rows("auth_group_permissions", "permission_id")

            if "django_admin_log" in available:
                for row in legacy.execute(
                    "SELECT id, action_time, object_id, object_repr, action_flag, change_message, content_type_id, user_id FROM django_admin_log"
                ):
                    row = list(row)
                    if row[6] is not None and row[6] not in content_type_map:
                        raise ValueError(
                            "An admin log references unsupported content. Import refused to prevent silent data loss."
                        )
                    row[6] = content_type_map.get(row[6])
                    target.execute(
                        "INSERT INTO django_admin_log(id,action_time,object_id,object_repr,action_flag,change_message,content_type_id,user_id) VALUES (?,?,?,?,?,?,?,?)",
                        row,
                    )
            failures = target.execute("PRAGMA foreign_key_check").fetchall()
            if failures:
                raise ValueError(
                    "Imported foreign-key check failed: " + repr(failures[:5])
                )
            target.commit()
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Imported database failed its integrity check.")
        except Exception:
            target.rollback()
            raise
        finally:
            legacy.close()
            target.close()

        # Add missing public details after the existing records have been copied.
        from importlib import import_module

        public_content = import_module("gym.migrations.0006_default_public_content")
        with connections["default"].schema_editor() as schema_editor:
            public_content.add_public_content(apps, schema_editor)
        connections["default"].check_constraints()
        connections.close_all()

        # Exclusive creation prevents accidentally overwriting a teammate's DB.
        with output.open("xb") as destination, staged.open("rb") as created:
            shutil.copyfileobj(created, destination)
        print(
            json.dumps(
                {
                    "created": str(output),
                    "source_unchanged": str(source),
                    "rows": imported_counts,
                    "sessions": "Not copied; users must sign in again.",
                    "empty_unsupported_tables_not_imported": unsupported_tables,
                    "unassigned_unsupported_permission_definitions": len(unsupported),
                },
                indent=2,
            )
        )
        print(
            "Uploaded files are not in SQLite. Copy the original media folder into the separate one-app project."
        )


from django.core.management.base import BaseCommand, CommandError
import subprocess


class Command(BaseCommand):
    help = "Copy a legacy SQLite database to a new file without changing its source."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        result = subprocess.run(
            [
                sys.executable,
                __file__,
                "--source",
                options["source"],
                "--output",
                options["output"],
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise CommandError(result.stderr or result.stdout)
        self.stdout.write(result.stdout)


if __name__ == "__main__":
    main()
