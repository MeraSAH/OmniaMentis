"""
* UBICACION: OmniaMentis/src/core/auth/fons_audit.py
* PROPOSITO: Bitacora de auditoria del panel del Fons: quien entro, quien fallo
*            y quien decidio que, y cuando. Solo se agrega al final (JSON Lines).
* DEPENDENCIAS: json, threading, time (stdlib)
* CREADO: 2026-10-20
* ESTADO: Produccion
*
* DECISIONES
*   - NO guarda contrasenas, tokens ni el contenido de las consultas de las personas:
*     solo el evento, el revisor, el id de la consulta y la accion tomada.
*   - Solo se aceptan eventos de una lista fija; los campos se limitan a texto corto,
*     numeros y booleanos (nada de estructuras anidadas).
*   - Rotacion simple: al pasar de max_bytes el archivo pasa a <archivo>.1 (se
*     reemplaza el anterior) para no llenar el disco.
*   - Un fallo al escribir NUNCA tumba la decision del Fons: se registra en el log
*     de la aplicacion y se devuelve False.
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)

EVENTS = frozenset({"login_ok", "login_fail", "login_blocked", "decision", "token_rejected", "remote_blocked",
                    "verification_view", "verification_approved", "verification_rejected"})
MAX_FIELD_CHARS = 200
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
MAX_READ = 200


def _clean(value: Any) -> Any:
    if isinstance(value, bool) or isinstance(value, (int, float)) or value is None:
        return value
    return str(value).replace("\n", " ").replace("\r", " ")[:MAX_FIELD_CHARS]


class FonsAudit:
    def __init__(self, path: Union[str, Path], max_bytes: int = DEFAULT_MAX_BYTES):
        self._path = Path(path)
        self._max_bytes = int(max_bytes)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, operator: str = "", **fields: Any) -> bool:
        if event not in EVENTS:
            raise ValueError(f"Evento de auditoria desconocido: {event!r}")
        entry: Dict[str, Any] = {"ts": round(time.time(), 3), "event": event, "operator": _clean(operator or "")}
        for k, v in fields.items():
            if k not in entry:
                entry[str(k)[:40]] = _clean(v)
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            with self._lock:
                if self._path.exists() and self._path.stat().st_size + len(line.encode("utf-8")) > self._max_bytes:
                    os.replace(self._path, self._path.with_name(self._path.name + ".1"))
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(line)
            return True
        except OSError as exc:
            logger.error("No se pudo escribir la auditoria del Fons: %s", exc)
            return False

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Ultimos eventos (del mas nuevo al mas viejo). Ignora lineas danadas."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            limit = 50
        limit = min(limit, MAX_READ)
        try:
            with self._lock:
                if not self._path.exists():
                    return []
                lines = self._path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            logger.error("No se pudo leer la auditoria del Fons: %s", exc)
            return []
        out: List[Dict[str, Any]] = []
        for raw in reversed(lines):
            try:
                item = json.loads(raw)
            except ValueError:
                continue
            if isinstance(item, dict):
                out.append(item)
                if len(out) >= limit:
                    break
        return out
