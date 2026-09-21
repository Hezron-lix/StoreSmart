from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from mysql.connector import pooling


# ============================================================
# ENVIRONMENT
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
    )
)

# Preferred FastAPI/root environment file
load_dotenv(
    os.path.join(
        BASE_DIR,
        ".env",
    )
)

# Temporary compatibility with your old Node backend .env
load_dotenv(
    os.path.join(
        BASE_DIR,
        "BackEnd",
        ".env",
    ),
    override=False,
)


# ============================================================
# MYSQL CONFIG
# ============================================================

DB_CONFIG = {
    "host":
        os.getenv(
            "DB_HOST",
            "localhost",
        ),

    "user":
        os.getenv(
            "DB_USER",
            "root",
        ),

    "password":
        os.getenv(
            "DB_PASSWORD",
            "",
        ),

    "database":
        os.getenv(
            "DB_NAME",
            "storagewise",
        ),
}


def _create_pool():
    passwords = [
        os.getenv("DB_PASSWORD", ""),
        "Carrots@123",
        "velaa@2005",
        "",
    ]
    seen = set()
    last_err = None
    for pwd in passwords:
        if pwd in seen:
            continue
        seen.add(pwd)
        try:
            cfg = dict(DB_CONFIG)
            cfg["password"] = pwd
            pool = pooling.MySQLConnectionPool(
                pool_name="storagewise_pool",
                pool_size=10,
                **cfg,
            )
            return pool
        except Exception as exc:
            last_err = exc
            continue
    raise last_err or RuntimeError("Unable to initialize MySQL pool")

connection_pool = _create_pool()


def get_connection():
    return (
        connection_pool
        .get_connection()
    )


# ============================================================
# DATETIME HELPER
# ============================================================

def to_mysql_datetime(
    value,
):
    if not value:
        return None

    value = str(
        value
    )

    if value.endswith(
        "Z"
    ):
        value = (
            value[:-1]
        )

    if "T" in value:
        value = (
            value.replace(
                "T",
                " ",
            )
        )

    if "." in value:
        value = (
            value.split(
                "."
            )[0]
        )

    return value[:19]


# ============================================================
# IMPORT ASSETS
# ============================================================

def import_assets(
    records,
):
    connection = None
    cursor = None

    imported = 0
    skipped = 0

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor()
        )

        sql = """
        INSERT INTO assets
        (
            asset_id,
            source_type,
            file_name,
            file_extension,
            size_gb,
            created_ts,
            modified_ts,
            owner_dept,
            tags,
            checksum,
            policy_id,
            entropy_score,
            is_duplicate
        )
        VALUES
        (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s
        )

        ON DUPLICATE KEY UPDATE

            source_type =
                VALUES(source_type),

            file_name =
                VALUES(file_name),

            file_extension =
                VALUES(file_extension),

            size_gb =
                VALUES(size_gb),

            created_ts =
                VALUES(created_ts),

            modified_ts =
                VALUES(modified_ts),

            owner_dept =
                VALUES(owner_dept),

            tags =
                VALUES(tags),

            checksum =
                VALUES(checksum),

            policy_id =
                VALUES(policy_id),

            entropy_score =
                VALUES(entropy_score),

            is_duplicate =
                VALUES(is_duplicate)
        """

        values = []

        for record in records:
            asset_id = (
                record.get(
                    "asset_id"
                )
            )

            source_type = (
                record.get(
                    "source_type"
                )
            )

            if (
                not asset_id
                or source_type
                not in {
                    "json",
                    "csv",
                    "txt",
                    "yaml",
                }
            ):
                skipped += 1
                continue

            values.append(
                (
                    str(
                        asset_id
                    ),

                    source_type,

                    record.get(
                        "file_name"
                    ),

                    record.get(
                        "file_extension"
                    ),

                    float(
                        record.get(
                            "size_gb"
                        )
                        or 0
                    ),

                    to_mysql_datetime(
                        record.get(
                            "created_ts"
                        )
                    ),

                    to_mysql_datetime(
                        record.get(
                            "modified_ts"
                        )
                    ),

                    record.get(
                        "owner_dept"
                    )
                    or "unknown",

                    json.dumps(
                        record.get(
                            "tags"
                        )
                        or []
                    ),

                    record.get(
                        "checksum"
                    )
                    or record.get(
                        "checksum_sha256"
                    ),

                    record.get(
                        "policy_id"
                    ),

                    record.get(
                        "entropy_score"
                    ),

                    1
                    if record.get(
                        "is_duplicate"
                    )
                    else 0,
                )
            )

        if values:
            cursor.executemany(
                sql,
                values,
            )

            connection.commit()

            imported = len(
                values
            )

        return {
            "success":
                True,

            "received":
                len(records),

            "imported":
                imported,

            "skipped":
                skipped,
        }

    except Exception:
        if connection:
            connection.rollback()

        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# FETCH ALL ASSETS + AI PREDICTIONS
# ============================================================

def fetch_assets():
    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor(
                dictionary=True
            )
        )

        cursor.execute(
            """
            SELECT
                a.*,
                p.savings_percent,
                p.savings_gb,
                p.priority_score

            FROM assets a

            LEFT JOIN predictions p
                ON a.asset_id =
                   p.asset_id

            ORDER BY a.id DESC
            """
        )

        rows = (
            cursor.fetchall()
        )

        for row in rows:
            if isinstance(
                row.get(
                    "tags"
                ),
                str,
            ):
                try:
                    row["tags"] = (
                        json.loads(
                            row["tags"]
                        )
                    )

                except Exception:
                    row["tags"] = []

        return rows

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# FETCH SINGLE ASSET
# ============================================================

def fetch_asset(
    asset_id,
):
    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor(
                dictionary=True
            )
        )

        cursor.execute(
            """
            SELECT *
            FROM assets
            WHERE asset_id = %s
            """,
            (
                asset_id,
            ),
        )

        row = (
            cursor.fetchone()
        )

        if (
            row
            and isinstance(
                row.get(
                    "tags"
                ),
                str,
            )
        ):
            try:
                row["tags"] = (
                    json.loads(
                        row["tags"]
                    )
                )

            except Exception:
                row["tags"] = []

        return row

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# STORAGE HISTORY
# ============================================================

def fetch_storage_history():
    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor(
                dictionary=True
            )
        )

        cursor.execute(
            """
            SELECT
                id,
                usage_date,
                total_used_gb,
                total_capacity_gb

            FROM storage_history

            ORDER BY usage_date ASC
            """
        )

        return (
            cursor.fetchall()
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# UPSERT AI PREDICTION
# ============================================================

def upsert_prediction(
    asset_id: str,
    savings_percent: float,
    savings_gb: float,
    priority_score: float,
):
    """
    predictions.asset_id is not UNIQUE in the supplied schema.

    Therefore:
        DELETE existing prediction
        INSERT latest prediction

    This avoids duplicate prediction rows.
    """

    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor()
        )

        cursor.execute(
            """
            DELETE FROM predictions
            WHERE asset_id = %s
            """,
            (
                asset_id,
            ),
        )

        cursor.execute(
            """
            INSERT INTO predictions
            (
                asset_id,
                savings_percent,
                savings_gb,
                priority_score
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                asset_id,

                float(
                    savings_percent
                ),

                float(
                    savings_gb
                ),

                float(
                    priority_score
                ),
            ),
        )

        connection.commit()

        return {
            "success":
                True,

            "asset_id":
                asset_id,
        }

    except Exception:
        if connection:
            connection.rollback()

        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# COMPRESSION MODEL SUMMARY
# ============================================================

def fetch_compression_insights(
    limit: int = 10,
):
    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor(
                dictionary=True
            )
        )

        cursor.execute(
            """
            SELECT
                COUNT(*) AS prediction_count,
                AVG(savings_percent)
                    AS average_savings_percent,
                SUM(savings_gb)
                    AS total_savings_gb

            FROM predictions
            """
        )

        summary = (
            cursor.fetchone()
            or {}
        )

        cursor.execute(
            """
            SELECT
                p.asset_id,
                p.savings_percent,
                p.savings_gb,
                p.priority_score,

                a.file_name,
                a.file_extension,
                a.source_type,
                a.size_gb,
                a.owner_dept,
                a.entropy_score

            FROM predictions p

            JOIN assets a
                ON a.asset_id =
                   p.asset_id

            ORDER BY
                p.savings_percent DESC

            LIMIT %s
            """,
            (
                int(limit),
            ),
        )

        top_predictions = (
            cursor.fetchall()
        )

        return {
            "prediction_count":
                int(
                    summary.get(
                        "prediction_count"
                    )
                    or 0
                ),

            "average_savings_percent":
                float(
                    summary.get(
                        "average_savings_percent"
                    )
                    or 0
                ),

            "total_savings_gb":
                float(
                    summary.get(
                        "total_savings_gb"
                    )
                    or 0
                ),

            "top_predictions":
                top_predictions,
        }

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# ACTION LOG
# ============================================================

def insert_action(
    asset_id,
    user_name,
    role,
    action_type,
    policy_id,
    outcome,
    reason,
):
    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor()
        )

        cursor.execute(
            """
            INSERT INTO actions
            (
                asset_id,
                user_name,
                role,
                action_type,
                policy_id,
                outcome,
                reason
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                asset_id,
                user_name,
                role,
                action_type,
                policy_id,
                outcome,
                reason,
            ),
        )

        connection.commit()

    except Exception:
        if connection:
            connection.rollback()

        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DELETE ASSET
# ============================================================

def delete_asset(
    asset_id: str,
):
    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor()
        )

        # ----------------------------------------------------
        # DELETE AI PREDICTION FIRST
        # ----------------------------------------------------

        cursor.execute(
            """
            DELETE FROM predictions
            WHERE asset_id = %s
            """,
            (
                asset_id,
            ),
        )

        # ----------------------------------------------------
        # DELETE ACTUAL ASSET
        # ----------------------------------------------------

        cursor.execute(
            """
            DELETE FROM assets
            WHERE asset_id = %s
            """,
            (
                asset_id,
            ),
        )

        deleted = (
            cursor.rowcount
        )

        connection.commit()

        return (
            deleted > 0
        )

    except Exception:
        if connection:
            connection.rollback()

        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# COMPRESS ASSET
# ============================================================

def compress_asset(
    asset_id: str,
):
    connection = None
    cursor = None

    try:
        connection = (
            get_connection()
        )

        cursor = (
            connection.cursor(
                dictionary=True
            )
        )

        # ----------------------------------------------------
        # GET CURRENT SIZE + PREDICTED SAVINGS
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                a.size_gb,
                p.savings_gb,
                p.savings_percent

            FROM assets a

            LEFT JOIN predictions p
                ON a.asset_id =
                   p.asset_id

            WHERE a.asset_id = %s
            """,
            (
                asset_id,
            ),
        )

        row = (
            cursor.fetchone()
        )

        if not row:
            return None

        # ----------------------------------------------------
        # CURRENT SIZE
        # ----------------------------------------------------

        old_size = float(
            row.get(
                "size_gb"
            )
            or 0
        )

        # ----------------------------------------------------
        # PREDICTED SAVINGS
        # ----------------------------------------------------

        savings_gb = float(
            row.get(
                "savings_gb"
            )
            or 0
        )

        savings_percent = float(
            row.get(
                "savings_percent"
            )
            or 0
        )

        # ----------------------------------------------------
        # CALCULATE NEW SIZE
        # ----------------------------------------------------

        new_size = max(
            0.0,

            old_size
            - savings_gb,
        )

        # ----------------------------------------------------
        # UPDATE ASSET SIZE
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE assets

            SET size_gb = %s

            WHERE asset_id = %s
            """,
            (
                new_size,
                asset_id,
            ),
        )

        # ====================================================
        # IMPORTANT:
        #
        # DO NOT DELETE THE PREDICTION HERE.
        #
        # The prediction remains so the row stays visible
        # in the Action Center after frontend refresh.
        #
        # COM:
        #   - updates size
        #   - keeps prediction
        #   - row remains visible
        #
        # DEL:
        #   - deletes prediction
        #   - deletes asset
        #   - row disappears
        # ====================================================

        connection.commit()

        return {
            "old_size_gb":
                round(
                    old_size,
                    4,
                ),

            "new_size_gb":
                round(
                    new_size,
                    4,
                ),

            "saved_gb":
                round(
                    savings_gb,
                    4,
                ),

            "savings_percent":
                round(
                    savings_percent,
                    2,
                ),
        }

    except Exception:
        if connection:
            connection.rollback()

        raise

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

__all__ = [
    "get_connection",
    "fetch_assets",
    "fetch_asset",
    "fetch_storage_history",
    "upsert_prediction",
    "fetch_compression_insights",
    "insert_action",
    "delete_asset",
    "compress_asset",
    "import_assets",
    "to_mysql_datetime",
]
