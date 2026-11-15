"""
* UBICACIÓN: OmniaMentis/src/core/verification/verification.py
* PROPÓSITO: Verificación de edad e identidad para Corporal (solo ADULTOS). Cola de solicitudes que revisa una
*            persona (el dueño) desde el panel local de Fons. El sistema NO decide: solo guarda, expone y borra.
* DEPENDENCIAS: sqlite3, os, threading, secrets, datetime (stdlib)
* CREADO: 2026-11-15
* ESTADO: Producción
*
* REGLAS (decididas por el dueño):
*   - Corporal NO admite menores: quien declara menos de 18 años se rechaza sin guardar ninguna imagen.
*   - Niveles: "adult" (cédula + rostro) y "adult_student" (además documento universitario; 18 a 25 años).
*   - Retención mínima: las imágenes se borran 24 h después de aprobar, al rechazar, o a los 7 días sin revisar.
*     Lo único que se conserva: estado, nivel, fecha de verificación y la fecha en que el nivel estudiante
*     vence (25.º cumpleaños). NO se conserva la fecha de nacimiento.
*   - Medida sensible (peneana): solo adultos verificados y con consentimiento explícito registrado.
*   - Fail-closed: cualquier duda → sin acceso.
"""

import os
import secrets
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

TIERS = ("adult", "adult_student")
MIN_AGE = 18
STUDENT_MAX_AGE = 25
PURGE_AFTER_APPROVAL = timedelta(hours=24)
PENDING_TTL = timedelta(days=7)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_REJECTIONS = 3                      # en REJECT_WINDOW; después hay que esperar
REJECT_WINDOW = timedelta(days=30)
REQUIRED = {"adult": ("id_doc", "face"), "adult_student": ("id_doc", "face", "student_doc")}
CONSENT_KINDS = ("intimate_measure",)
CONSENT_TEXT_VERSION = "2026-11-15"


class VerificationError(ValueError):
    """Error de validación con mensaje apto para mostrar a la persona."""


def _utc(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return now if now.tzinfo else now.replace(tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


def age_on(birth: date, today: date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:                  # 29 de febrero
        return d.replace(year=d.year + years, day=28)


def sniff_image(data: bytes) -> Optional[str]:
    """Tipo real de imagen por sus primeros bytes (no confía en la extensión que envía el cliente)."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


class VerificationStore:
    def __init__(self, db_path: str, files_dir: str):
        self._db_path = db_path
        self._dir = files_dir
        self._lock = threading.Lock()
        os.makedirs(files_dir, mode=0o700, exist_ok=True)
        d = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(d, exist_ok=True)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS verifications(
                id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, tier TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT,
                reject_reason TEXT, student_until TEXT, declared_birth TEXT, purge_at TEXT NOT NULL, images_purged INTEGER NOT NULL DEFAULT 0)""")
            c.execute("""CREATE TABLE IF NOT EXISTS vimages(
                id INTEGER PRIMARY KEY AUTOINCREMENT, vid INTEGER NOT NULL, kind TEXT NOT NULL,
                fname TEXT NOT NULL, ext TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS consents(
                account_id TEXT NOT NULL, kind TEXT NOT NULL, text_version TEXT NOT NULL, granted_at TEXT NOT NULL,
                PRIMARY KEY(account_id, kind))""")

    def _conn(self):
        c = sqlite3.connect(self._db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    # ------------------------------------------------------------------ solicitud
    def submit(self, account_id: str, tier: str, birth_date: date, images: Dict[str, bytes],
               now: Optional[datetime] = None) -> int:
        """Crea una solicitud pendiente. La fecha de nacimiento declarada se guarda SOLO mientras la solicitud está
        pendiente (el revisor la compara con la cédula) y se borra al decidir o expirar."""
        now = _utc(now)
        if not account_id or not isinstance(account_id, str):
            raise VerificationError("Cuenta inválida.")
        if tier not in TIERS:
            raise VerificationError("Nivel de verificación inválido.")
        if not isinstance(birth_date, date) or isinstance(birth_date, datetime) or birth_date > now.date():
            raise VerificationError("Fecha de nacimiento inválida.")
        age = age_on(birth_date, now.date())
        if age < MIN_AGE:
            raise VerificationError("Corporal es solo para personas mayores de 18 años.")
        if tier == "adult_student" and age > STUDENT_MAX_AGE:
            raise VerificationError("El nivel estudiante es para personas de 18 a 25 años. "
                                    "Puedes verificarte como adulto.")
        need = REQUIRED[tier]
        if set(images) != set(need):
            raise VerificationError("Faltan o sobran documentos. Se requieren: " + ", ".join(need) + ".")
        checked: List[Tuple[str, bytes, str]] = []
        for kind in need:
            data = images[kind]
            if not isinstance(data, (bytes, bytearray)) or not data:
                raise VerificationError("Imagen vacía o inválida.")
            if len(data) > MAX_IMAGE_BYTES:
                raise VerificationError("Cada imagen debe pesar 5 MB o menos.")
            ext = sniff_image(bytes(data))
            if ext is None:
                raise VerificationError("Solo se aceptan imágenes JPG, PNG o WebP.")
            checked.append((kind, bytes(data), ext))
        with self._lock, self._conn() as c:
            if c.execute("SELECT 1 FROM verifications WHERE account_id=? AND status='pending'", (account_id,)).fetchone():
                raise VerificationError("Ya tienes una solicitud en revisión.")
            since = _iso(now - REJECT_WINDOW)
            n = c.execute("SELECT COUNT(*) FROM verifications WHERE account_id=? AND status='rejected' AND decided_at>=?",
                          (account_id, since)).fetchone()[0]
            if n >= MAX_REJECTIONS:
                raise VerificationError("Demasiados rechazos recientes. Inténtalo más adelante.")
            cur = c.execute("INSERT INTO verifications(account_id,tier,status,created_at,declared_birth,purge_at) "
                            "VALUES(?,?,?,?,?,?)",
                            (account_id, tier, "pending", _iso(now), birth_date.isoformat(),
                             _iso(now + PENDING_TTL)))
            vid = cur.lastrowid
            written: List[str] = []
            try:
                for kind, data, ext in checked:
                    fname = secrets.token_hex(16) + "." + ext
                    path = os.path.join(self._dir, fname)
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "wb") as f:
                        f.write(data)
                    written.append(path)
                    c.execute("INSERT INTO vimages(vid,kind,fname,ext) VALUES(?,?,?,?)", (vid, kind, fname, ext))
            except Exception:
                for p in written:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                raise
        return vid

    # ------------------------------------------------------------------ revisión (panel Fons)
    def list_pending(self) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id,account_id,tier,created_at,purge_at,declared_birth FROM verifications "
                             "WHERE status='pending' ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def read_image(self, vid: int, kind: str) -> Tuple[bytes, str]:
        """Bytes de una imagen para que el revisor la vea. Solo mientras exista (no purgada)."""
        with self._conn() as c:
            row = c.execute("SELECT i.fname,i.ext FROM vimages i JOIN verifications v ON v.id=i.vid "
                            "WHERE i.vid=? AND i.kind=? AND v.images_purged=0", (vid, kind)).fetchone()
        if not row:
            raise VerificationError("Imagen no disponible.")
        with open(os.path.join(self._dir, row["fname"]), "rb") as f:
            return f.read(), row["ext"]

    def approve(self, vid: int, reviewer: str, now: Optional[datetime] = None) -> None:
        now = _utc(now)
        with self._lock, self._conn() as c:
            row = c.execute("SELECT status,tier,declared_birth FROM verifications WHERE id=?", (vid,)).fetchone()
            if not row or row["status"] != "pending":
                raise VerificationError("La solicitud no está pendiente.")
            birth = date.fromisoformat(row["declared_birth"])
            age = age_on(birth, now.date())
            if age < MIN_AGE or (row["tier"] == "adult_student" and age > STUDENT_MAX_AGE):
                raise VerificationError("La edad declarada ya no cumple el nivel pedido: rechaza la solicitud.")
            until = _add_years(birth, STUDENT_MAX_AGE + 1).isoformat() if row["tier"] == "adult_student" else None
            c.execute("UPDATE verifications SET status='approved', decided_at=?, decided_by=?, purge_at=?, "
                      "student_until=?, declared_birth=NULL WHERE id=?",
                      (_iso(now), reviewer, _iso(now + PURGE_AFTER_APPROVAL), until, vid))

    def reject(self, vid: int, reviewer: str, reason: str, now: Optional[datetime] = None) -> None:
        now = _utc(now)
        with self._lock, self._conn() as c:
            row = c.execute("SELECT status FROM verifications WHERE id=?", (vid,)).fetchone()
            if not row or row["status"] != "pending":
                raise VerificationError("La solicitud no está pendiente.")
            c.execute("UPDATE verifications SET status='rejected', decided_at=?, decided_by=?, reject_reason=?, "
                      "purge_at=?, declared_birth=NULL WHERE id=?", (_iso(now), reviewer, (reason or "")[:200], _iso(now), vid))
        self.purge_due(now)

    # ------------------------------------------------------------------ retención
    def purge_due(self, now: Optional[datetime] = None) -> int:
        """Borra las imágenes vencidas y marca como expiradas las pendientes sin revisar. Devuelve imágenes borradas."""
        now = _utc(now)
        removed = 0
        with self._lock, self._conn() as c:
            c.execute("UPDATE verifications SET status='expired', decided_at=?, declared_birth=NULL "
                      "WHERE status='pending' AND purge_at<=?",
                      (_iso(now), _iso(now)))
            due = c.execute("SELECT id FROM verifications WHERE images_purged=0 AND status!='pending' AND purge_at<=?",
                            (_iso(now),)).fetchall()
            for v in due:
                for img in c.execute("SELECT fname FROM vimages WHERE vid=?", (v["id"],)).fetchall():
                    try:
                        os.remove(os.path.join(self._dir, img["fname"]))
                        removed += 1
                    except FileNotFoundError:
                        pass
                c.execute("DELETE FROM vimages WHERE vid=?", (v["id"],))
                c.execute("UPDATE verifications SET images_purged=1 WHERE id=?", (v["id"],))
        return removed

    def delete_account_data(self, account_id: str) -> int:
        """Derecho de supresión: borra TODO lo de la cuenta (imágenes, solicitudes y consentimientos).
        Devuelve cuántas imágenes se borraron."""
        removed = 0
        with self._lock, self._conn() as c:
            for v in c.execute("SELECT id FROM verifications WHERE account_id=?", (account_id,)).fetchall():
                for img in c.execute("SELECT fname FROM vimages WHERE vid=?", (v["id"],)).fetchall():
                    try:
                        os.remove(os.path.join(self._dir, img["fname"]))
                        removed += 1
                    except FileNotFoundError:
                        pass
                c.execute("DELETE FROM vimages WHERE vid=?", (v["id"],))
            c.execute("DELETE FROM verifications WHERE account_id=?", (account_id,))
            c.execute("DELETE FROM consents WHERE account_id=?", (account_id,))
        return removed

    # ------------------------------------------------------------------ acceso
    def access_level(self, account_id: str, now: Optional[datetime] = None) -> str:
        """'none' | 'adult' | 'adult_student'. El nivel estudiante pasa a 'adult' al cumplir 26 (vence el
        25.º año). Fail-closed ante cualquier dato raro."""
        now = _utc(now)
        try:
            with self._conn() as c:
                row = c.execute("SELECT tier,student_until FROM verifications WHERE account_id=? AND status='approved' "
                                "ORDER BY id DESC LIMIT 1", (account_id,)).fetchone()
            if not row:
                return "none"
            if row["tier"] == "adult_student":
                until = date.fromisoformat(row["student_until"])
                return "adult_student" if now.date() < until else "adult"
            return "adult" if row["tier"] == "adult" else "none"
        except Exception:
            return "none"

    def status(self, account_id: str) -> Dict:
        with self._conn() as c:
            row = c.execute("SELECT status,tier,created_at,decided_at FROM verifications WHERE account_id=? "
                            "ORDER BY id DESC LIMIT 1", (account_id,)).fetchone()
        return dict(row) if row else {"status": "none"}

    # ------------------------------------------------------------------ consentimiento (medida sensible)
    def grant_consent(self, account_id: str, kind: str, accepted_text_version: str,
                      now: Optional[datetime] = None) -> None:
        if kind not in CONSENT_KINDS:
            raise VerificationError("Consentimiento desconocido.")
        if accepted_text_version != CONSENT_TEXT_VERSION:
            raise VerificationError("Debes aceptar la versión vigente del texto.")
        if self.access_level(account_id, now) == "none":
            raise VerificationError("Primero debes verificarte como adulto.")
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO consents VALUES(?,?,?,?)",
                      (account_id, kind, accepted_text_version, _iso(_utc(now))))

    def revoke_consent(self, account_id: str, kind: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM consents WHERE account_id=? AND kind=?", (account_id, kind))

    def can_use_intimate_measure(self, account_id: str, now: Optional[datetime] = None) -> bool:
        if self.access_level(account_id, now) == "none":
            return False
        with self._conn() as c:
            row = c.execute("SELECT text_version FROM consents WHERE account_id=? AND kind='intimate_measure'",
                            (account_id,)).fetchone()
        return bool(row and row["text_version"] == CONSENT_TEXT_VERSION)
