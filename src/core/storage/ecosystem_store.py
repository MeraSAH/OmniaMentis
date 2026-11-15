"""
* UBICACION: OmniaMentis/src/core/storage/ecosystem_store.py
* PROPOSITO: Almacen UNICO de los datos de los 9 modulos del ecosistema.
*            Vive en la MISMA base SQLite que las cuentas (data/accounts.db),
*            ligado a la cuenta por clave foranea con ON DELETE CASCADE: al
*            borrar la cuenta se borran todos sus datos de modulos.
* DEPENDENCIAS: sqlite3, json (stdlib). Requiere que AccountStore ya haya
*               creado la tabla `accounts` en el mismo archivo.
* CREADO: 2026-10-17
* ESTADO: Produccion
*
* DECISIONES
*   - Una sola base y una sola cuenta (decision del responsable, 2026-10-16):
*     los modulos no tienen usuarios ni bases propias.
*   - Los modulos NO escriben aqui por su cuenta: solo el motor (OmniaMentis)
*     llama a este almacen, despues de aplicar la politica de edad.
*   - Tabla generica (module, kind, payload JSON) para no atar el esquema a
*     modulos que todavia no existen. Cuando un modulo madure y necesite
*     consultas por campo, se le crea tabla propia en ESTA misma base.
*   - Limites duros (tamano por registro y registros por cuenta) para que un
*     bucle o un abuso no llene el disco.
*   - Los datos de un modulo son datos personales: entran en el borrado de
*     cuenta (cascade) y en la exportacion (`export`).
*   - Conexion propia al mismo archivo (WAL permite varias conexiones) con
*     foreign_keys=ON en cada una: sin eso el cascade no funciona.
*   - NO guarda datos intimos de Corporal en claro: ese modulo, cuando exista,
*     guardara solo bloques ya cifrados en el dispositivo (Omnia Vault).
"""

import json
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

MAX_PAYLOAD_BYTES = 16 * 1024
MAX_RECORDS_PER_ACCOUNT = 5000
MAX_LIST_LIMIT = 500

_MODULE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{1,39}$")
_KIND_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS module_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_module_records_lookup
    ON module_records (account_id, module, kind, created_at, id);
"""


class StoreError(ValueError):
    """Base de los errores del almacen."""


class InvalidRecord(StoreError):
    """Modulo, tipo o contenido invalido."""


class AccountMissing(StoreError):
    """La cuenta no existe (o ya se borro)."""


class StoreFull(StoreError):
    """La cuenta alcanzo el maximo de registros."""


def _check_names(module: Any, kind: Any = None) -> None:
    if not isinstance(module, str) or not _MODULE_RE.match(module):
        raise InvalidRecord("Nombre de modulo invalido.")
    if kind is not None and (not isinstance(kind, str) or not _KIND_RE.match(kind)):
        raise InvalidRecord("Tipo de registro invalido.")


def _check_account(account_id: Any) -> None:
    if not isinstance(account_id, str) or not account_id or len(account_id) > 64:
        raise AccountMissing("Cuenta invalida.")


class EcosystemStore:
    """Datos de modulos, por cuenta, en la misma base que las cuentas."""

    def __init__(
        self,
        db_path: Union[str, Path],
        *,
        max_records_per_account: int = MAX_RECORDS_PER_ACCOUNT,
        max_payload_bytes: int = MAX_PAYLOAD_BYTES,
    ):
        self._max_records = int(max_records_per_account)
        self._max_payload = int(max_payload_bytes)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            has_accounts = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'"
            ).fetchone()
            if not has_accounts:
                self._conn.close()
                raise RuntimeError(
                    "La base no tiene la tabla 'accounts': crea AccountStore antes que EcosystemStore."
                )
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------ escritura
    def add(self, account_id: str, module: str, kind: str, payload: Dict[str, Any]) -> int:
        """Guarda un registro y devuelve su id. Falla cerrado ante datos raros."""
        _check_account(account_id)
        if kind is None:  # en add() el tipo es obligatorio (en list() es filtro opcional)
            raise InvalidRecord("Tipo de registro invalido.")
        _check_names(module, kind)
        if not isinstance(payload, dict):
            raise InvalidRecord("El contenido debe ser un objeto.")
        try:
            raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError):
            raise InvalidRecord("El contenido no es JSON valido.") from None
        if len(raw.encode("utf-8")) > self._max_payload:
            raise InvalidRecord("El contenido es demasiado grande.")
        with self._lock:
            try:
                n = self._conn.execute(
                    "SELECT COUNT(*) FROM module_records WHERE account_id = ?", (account_id,)
                ).fetchone()[0]
                if n >= self._max_records:
                    raise StoreFull("Se alcanzo el maximo de registros de la cuenta.")
                cur = self._conn.execute(
                    "INSERT INTO module_records (account_id, module, kind, payload, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (account_id, module, kind, raw, time.time()),
                )
                self._conn.commit()
                return int(cur.lastrowid)
            except sqlite3.IntegrityError:
                self._conn.rollback()
                raise AccountMissing("La cuenta no existe.") from None

    def delete_module(self, account_id: str, module: str) -> int:
        """Borra todos los registros de un modulo para la cuenta. Devuelve cuantos."""
        _check_account(account_id)
        _check_names(module)
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM module_records WHERE account_id = ? AND module = ?",
                (account_id, module),
            )
            self._conn.commit()
            return cur.rowcount

    # ------------------------------------------------------------------ lectura
    @staticmethod
    def _out(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "module": row["module"],
            "kind": row["kind"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }

    def list(
        self,
        account_id: str,
        module: str,
        kind: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Registros de un modulo (y tipo opcional), del mas nuevo al mas viejo."""
        _check_account(account_id)
        _check_names(module, kind)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise InvalidRecord("Limite invalido.")
        limit = min(limit, MAX_LIST_LIMIT)
        sql = "SELECT * FROM module_records WHERE account_id = ? AND module = ?"
        params: list = [account_id, module]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            return [self._out(r) for r in self._conn.execute(sql, params).fetchall()]

    def latest(self, account_id: str, module: str, kind: str) -> Optional[Dict[str, Any]]:
        rows = self.list(account_id, module, kind, limit=1)
        return rows[0] if rows else None

    def count(self, account_id: str) -> int:
        _check_account(account_id)
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM module_records WHERE account_id = ?", (account_id,)
            ).fetchone()[0]

    def counts(self, account_id: str) -> Dict[str, int]:
        """Cantidad de registros por modulo de la cuenta ({} si no tiene)."""
        _check_account(account_id)
        with self._lock:
            rows = self._conn.execute(
                "SELECT module, COUNT(*) AS n FROM module_records WHERE account_id = ? GROUP BY module",
                (account_id,),
            ).fetchall()
            return {r["module"]: int(r["n"]) for r in rows}

    def export(self, account_id: str) -> List[Dict[str, Any]]:
        """Todos los registros de la cuenta (derecho de acceso/portabilidad)."""
        _check_account(account_id)
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM module_records WHERE account_id = ? ORDER BY created_at, id",
                (account_id,),
            ).fetchall()
            return [self._out(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
