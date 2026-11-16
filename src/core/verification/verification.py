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
*   - Fotos de progreso (2026-11-16): solo adultos verificados con consentimiento propio; privadas (solo las ve su
*     dueña/o, nunca el panel del Fons); JPG/PNG sin metadatos (se quita EXIF/GPS); máximo 24; se borran una a una
*     o con la cuenta.
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
CONSENT_KINDS = ("intimate_measure", "progress_photos")
CONSENT_TEXT_VERSION = "2026-11-15"        # medida íntima
PHOTOS_CONSENT_VERSION = "2026-11-16"      # fotos de progreso
_CONSENT_VERSIONS = {"intimate_measure": CONSENT_TEXT_VERSION, "progress_photos": PHOTOS_CONSENT_VERSION}
MAX_PHOTOS = 24
PHOTO_NOTE_MAX = 100
DOCS_CONSENT_VERSION = "2026-11-16"     # texto de tratamiento de documentos de verificación (privacidad.html, anexo Corporal)


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


def _strip_jpeg(data: bytes) -> bytes:
    """Quita EXIF/XMP (APP1), APP13 y comentarios (COM) de un JPEG; el resto queda idéntico."""
    if data[:2] != b"\xff\xd8":
        raise VerificationError("JPG inválido.")
    out = bytearray(b"\xff\xd8")
    i, n = 2, len(data)
    while i < n:
        if data[i] != 0xFF:
            raise VerificationError("JPG dañado.")
        while i < n and data[i] == 0xFF:       # relleno 0xFF
            i += 1
        if i >= n:
            raise VerificationError("JPG dañado.")
        marker = data[i]
        i += 1
        if marker == 0xD9:                     # EOI
            out += b"\xff\xd9"
            return bytes(out)
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:      # marcadores sin longitud
            out += bytes([0xFF, marker])
            continue
        if i + 2 > n:
            raise VerificationError("JPG dañado.")
        length = (data[i] << 8) | data[i + 1]
        if length < 2 or i + length > n:
            raise VerificationError("JPG dañado.")
        seg = data[i:i + length]
        if marker == 0xDA:                      # SOS: desde aquí es la imagen comprimida; se copia tal cual
            rest = data[i + length:]
            end = rest.rfind(b"\xff\xd9")        # sin EOI = dañado; lo que haya después del EOI (cola) se descarta
            if end < 0:
                raise VerificationError("JPG dañado.")
            out += bytes([0xFF, marker]) + seg + rest[:end + 2]
            return bytes(out)
        if marker not in (0xE1, 0xED, 0xFE):
            out += bytes([0xFF, marker]) + seg
        i += length
    raise VerificationError("JPG dañado.")


_PNG_DROP = {b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"}


def _strip_png(data: bytes) -> bytes:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise VerificationError("PNG inválido.")
    out = bytearray(data[:8])
    i, n = 8, len(data)
    seen_end = False
    while i < n:
        if i + 12 > n:
            raise VerificationError("PNG dañado.")
        length = int.from_bytes(data[i:i + 4], "big")
        if i + 12 + length > n:
            raise VerificationError("PNG dañado.")
        ctype = data[i + 4:i + 8]
        if ctype not in _PNG_DROP:
            out += data[i:i + 12 + length]
        i += 12 + length
        if ctype == b"IEND":
            seen_end = True
            break
    if not seen_end:
        raise VerificationError("PNG dañado.")
    return bytes(out)


def strip_image_metadata(data: bytes) -> Tuple[bytes, str]:
    """(imagen sin metadatos, extensión). Fotos de progreso: solo JPG y PNG."""
    kind = sniff_image(data)
    if kind == "jpg":
        return _strip_jpeg(data), "jpg"
    if kind == "png":
        return _strip_png(data), "png"
    raise VerificationError("Para las fotos de progreso se aceptan solo JPG o PNG.")


class VerificationStore:
    def __init__(self, db_path: str, files_dir: str, photos_dir: Optional[str] = None):
        self._db_path = db_path
        self._dir = files_dir
        self._photos_dir = photos_dir or os.path.join(os.path.dirname(os.path.abspath(files_dir)), "progress_photos")
        self._lock = threading.Lock()
        os.makedirs(files_dir, mode=0o700, exist_ok=True)
        os.makedirs(self._photos_dir, mode=0o700, exist_ok=True)
        d = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(d, exist_ok=True)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS verifications(
                id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, tier TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT,
                reject_reason TEXT, student_until TEXT, declared_birth TEXT, docs_consent TEXT, purge_at TEXT NOT NULL, images_purged INTEGER NOT NULL DEFAULT 0)""")
            try:        # bases creadas antes de esta versión
                c.execute("ALTER TABLE verifications ADD COLUMN docs_consent TEXT")
            except sqlite3.OperationalError:
                pass
            c.execute("""CREATE TABLE IF NOT EXISTS vimages(
                id INTEGER PRIMARY KEY AUTOINCREMENT, vid INTEGER NOT NULL, kind TEXT NOT NULL,
                fname TEXT NOT NULL, ext TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS photos(
                id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, fname TEXT NOT NULL,
                ext TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS consents(
                account_id TEXT NOT NULL, kind TEXT NOT NULL, text_version TEXT NOT NULL, granted_at TEXT NOT NULL,
                PRIMARY KEY(account_id, kind))""")

    def _conn(self):
        c = sqlite3.connect(self._db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    # ------------------------------------------------------------------ solicitud
    def submit(self, account_id: str, tier: str, birth_date: date, images: Dict[str, bytes],
               now: Optional[datetime] = None, docs_consent_version: Optional[str] = None) -> int:
        """Crea una solicitud pendiente. docs_consent_version: versión del texto sobre el tratamiento de los
        documentos que la persona aceptó (se guarda como prueba del consentimiento; la API lo exige). La fecha de nacimiento declarada se guarda SOLO mientras la solicitud está
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
            cur = c.execute("INSERT INTO verifications(account_id,tier,status,created_at,declared_birth,purge_at,docs_consent) "
                            "VALUES(?,?,?,?,?,?,?)",
                            (account_id, tier, "pending", _iso(now), birth_date.isoformat(),
                             _iso(now + PENDING_TTL), docs_consent_version))
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
            for ph in c.execute("SELECT fname FROM photos WHERE account_id=?", (account_id,)).fetchall():
                try:
                    os.remove(os.path.join(self._photos_dir, ph["fname"]))
                    removed += 1
                except FileNotFoundError:
                    pass
            c.execute("DELETE FROM photos WHERE account_id=?", (account_id,))
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
        if accepted_text_version != _CONSENT_VERSIONS[kind]:
            raise VerificationError("Debes aceptar la versión vigente del texto.")
        if self.access_level(account_id, now) == "none":
            raise VerificationError("Primero debes verificarte como adulto.")
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO consents VALUES(?,?,?,?)",
                      (account_id, kind, accepted_text_version, _iso(_utc(now))))

    def revoke_consent(self, account_id: str, kind: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM consents WHERE account_id=? AND kind=?", (account_id, kind))

    def has_consent(self, account_id: str, kind: str, now: Optional[datetime] = None) -> bool:
        """Verificación vigente + consentimiento de ese tipo con la versión actual del texto. Fail-closed."""
        if kind not in CONSENT_KINDS or self.access_level(account_id, now) == "none":
            return False
        with self._conn() as c:
            row = c.execute("SELECT text_version FROM consents WHERE account_id=? AND kind=?",
                            (account_id, kind)).fetchone()
        return bool(row and row["text_version"] == _CONSENT_VERSIONS[kind])

    def can_use_intimate_measure(self, account_id: str, now: Optional[datetime] = None) -> bool:
        return self.has_consent(account_id, "intimate_measure", now)

    # ------------------------------------------------------------------ fotos de progreso (privadas)
    def add_photo(self, account_id: str, data: bytes, note: str = "", now: Optional[datetime] = None) -> int:
        if not self.has_consent(account_id, "progress_photos", now):
            raise VerificationError("Primero acepta el consentimiento de las fotos de progreso.")
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise VerificationError("Imagen vacía o inválida.")
        if len(data) > MAX_IMAGE_BYTES:
            raise VerificationError("La imagen debe pesar 5 MB o menos.")
        clean, ext = strip_image_metadata(bytes(data))
        note = " ".join(str(note or "").split())[:PHOTO_NOTE_MAX]
        with self._lock, self._conn() as c:
            n = c.execute("SELECT COUNT(*) FROM photos WHERE account_id=?", (account_id,)).fetchone()[0]
            if n >= MAX_PHOTOS:
                raise VerificationError(f"Máximo {MAX_PHOTOS} fotos. Borra alguna para agregar otra.")
            fname = secrets.token_hex(16) + "." + ext
            path = os.path.join(self._photos_dir, fname)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(clean)
            try:
                cur = c.execute("INSERT INTO photos(account_id,fname,ext,note,created_at) VALUES(?,?,?,?,?)",
                                (account_id, fname, ext, note, _iso(_utc(now))))
            except Exception:
                os.remove(path)
                raise
        return cur.lastrowid

    def list_photos(self, account_id: str) -> List[Dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id,note,created_at,ext FROM photos WHERE account_id=? ORDER BY id",
                             (account_id,)).fetchall()
        return [dict(r) for r in rows]

    def read_photo(self, account_id: str, photo_id: int) -> Tuple[bytes, str]:
        """Solo su dueña/o: el id de otra cuenta se trata como inexistente."""
        with self._conn() as c:
            row = c.execute("SELECT fname,ext FROM photos WHERE id=? AND account_id=?",
                            (photo_id, account_id)).fetchone()
        if not row:
            raise VerificationError("Foto no encontrada.")
        with open(os.path.join(self._photos_dir, row["fname"]), "rb") as f:
            return f.read(), row["ext"]

    def delete_photo(self, account_id: str, photo_id: int) -> bool:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT fname FROM photos WHERE id=? AND account_id=?", (photo_id, account_id)).fetchone()
            if not row:
                return False
            try:
                os.remove(os.path.join(self._photos_dir, row["fname"]))
            except FileNotFoundError:
                pass
            c.execute("DELETE FROM photos WHERE id=?", (photo_id,))
        return True
