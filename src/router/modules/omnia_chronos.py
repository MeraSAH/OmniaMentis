"""
* UBICACION: OmniaMentis/src/router/modules/omnia_chronos.py
* PROPOSITO: Modulo de bloques de enfoque. NO calcula nada por su cuenta: usa el
*            motor (core/focus/focus.py) y guarda en el almacen unico del contexto.
* DEPENDENCIAS: base_module.py, core/focus/focus.py, core/habits/habits.py
* ULTIMA MODIFICACION: 2026-10-18
* ESTADO: Produccion
*
* CAMBIO 2026-10-18: deja de ser un stub. Inicia/termina bloques de enfoque
* (5-180 min, 25 por defecto), guarda el tiempo enfocado y devuelve el widget
* `focus_timer`. El BLOQUEO de notificaciones y el modo pantalla negra los hace
* la interfaz; el servidor no puede (ni promete) bloquear nada en el dispositivo.
"""

import logging
import time
from typing import Callable, List, Optional

from core.focus import focus as fc
from core.habits.habits import day_key
from .base_module import OmniaModule, OmniaContext, ModuleResponse

logger = logging.getLogger(__name__)

MODULE_NAME = "OmniaChronos"


class OmniaChronosModule(OmniaModule):

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock

    @property
    def name(self) -> str:
        return MODULE_NAME

    def keywords(self) -> List[str]:
        return [
            "bloque de enfoque", "modo enfoque", "pomodoro",
            "desintoxicacion digital", "desintoxicación digital",
            "reset dopaminico", "reset dopamínico",
            "auditar mi tiempo", "auditoria de tiempo", "auditoría de tiempo",
            "evolucion cognitiva", "evolución cognitiva",
            "notificaciones bloqueadas", "modo concentracion",
            "modo concentración", "tiempo enfocado", "bloque actual",
        ]

    def _resp(self, text, status, data=None, widget=None) -> ModuleResponse:
        payload = {"status": status, "domain": "time_management"}
        if data:
            payload.update(data)
        return ModuleResponse(text=text, module_name=self.name, data=payload,
                              widget_type="focus_timer" if widget else None, widget_payload=widget)

    def _open_block(self, store, uid) -> Optional[dict]:
        starts = store.list(uid, self.name, "focus_start", limit=50)
        closed = {(r.get("payload") or {}).get("start_id")
                  for r in store.list(uid, self.name, "focus_end", limit=200)}
        for r in starts:  # del más nuevo al más viejo
            if r["id"] not in closed:
                p = r.get("payload") or {}
                return {"id": r["id"], "started_at": float(p.get("started_at", 0)),
                        "minutes": int(p.get("minutes", 0)), "label": p.get("label")}
        return None

    def _today_summary(self, store, uid, now) -> dict:
        ends = [r.get("payload") or {} for r in store.list(uid, self.name, "focus_end", limit=200)]
        return fc.summarize_day(ends, day_key(now), day_key)

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        store = context.data_store
        if store is None:
            return self._resp("Ahora mismo no puedo guardar tus bloques de enfoque. Inténtalo más tarde.", "unavailable")
        uid, now = context.user_id, self._clock()
        try:
            return self._dispatch(message, store, uid, now)
        except Exception as exc:
            logger.warning("OmniaChronos: error con el almacén: %s", exc)
            return self._resp("No pude acceder a tus bloques de enfoque ahora mismo.", "unavailable")

    def _dispatch(self, message, store, uid, now) -> ModuleResponse:
        intent = fc.detect_intent(message)
        block = self._open_block(store, uid)

        if intent == "end":
            if block is None:
                return self._resp("No tienes ningún bloque de enfoque en curso.", "no_open_block")
            elapsed = fc.elapsed_minutes(block["started_at"], block["minutes"], now)
            done = now >= block["started_at"] + block["minutes"] * 60
            store.add(uid, self.name, "focus_end", {
                "start_id": block["id"], "started_at": block["started_at"], "minutes": block["minutes"],
                "elapsed_min": elapsed, "completed": done})
            day = self._today_summary(store, uid, now)
            head = "Bloque completado" if done else "Bloque terminado antes de tiempo"
            return self._resp(
                f"{head}: {elapsed} min de enfoque. Hoy llevas {day['minutes']} min en {day['blocks']} bloque(s).",
                "ended", {"elapsed_min": elapsed, "completed": done, "today": day})

        if intent == "status":
            day = self._today_summary(store, uid, now)
            if block is not None:
                left = fc.remaining_seconds(block["started_at"], block["minutes"], now)
                extra = f" Bloque en curso: {left // 60} min {left % 60} s restantes." if left else \
                        " Tu bloque ya cumplió su tiempo: dime «terminé el bloque» para cerrarlo."
            else:
                extra = " No hay bloque en curso."
            return self._resp(f"Hoy llevas {day['minutes']} min de enfoque en {day['blocks']} bloque(s).{extra}",
                              "summary", {"today": day, "open": block is not None})

        # intent == "start"
        minutes = fc.parse_minutes(message)
        if minutes is None:
            minutes = fc.DEFAULT_MINUTES
        if not fc.valid_minutes(minutes):
            return self._resp(f"Un bloque debe durar entre {fc.MIN_MINUTES} y {fc.MAX_MINUTES} minutos.",
                              "invalid_minutes")
        if block is not None:
            left = fc.remaining_seconds(block["started_at"], block["minutes"], now)
            if left > 0:
                return self._resp(
                    f"Ya tienes un bloque en curso: quedan {left // 60} min {left % 60} s. "
                    "Dime «terminé el bloque» si quieres cerrarlo antes.", "already_open",
                    {"remaining_seconds": left},
                    # se reenvía el widget del bloque abierto para que la pantalla de enfoque
                    # pueda volver a mostrarse (por ejemplo tras ocultarla con Esc)
                    {"minutes": block["minutes"], "started_at": block["started_at"],
                     "ends_at": block["started_at"] + block["minutes"] * 60,
                     "label": block.get("label"), "mode": "absolute_focus",
                     "request_block_notifications": True, "server_now": now})
            # bloque vencido que nadie cerró: se cierra con su duración completa
            store.add(uid, self.name, "focus_end", {
                "start_id": block["id"], "started_at": block["started_at"], "minutes": block["minutes"],
                "elapsed_min": float(block["minutes"]), "completed": True, "auto": True})
        label = fc.detect_label(message)
        payload = {"started_at": now, "minutes": minutes}
        if label:
            payload["label"] = label
        store.add(uid, self.name, "focus_start", payload)
        widget = {"minutes": minutes, "started_at": now, "ends_at": now + minutes * 60,
                  "label": label, "mode": "absolute_focus", "request_block_notifications": True,
                  "server_now": now}
        return self._resp(
            f"⏱ Bloque de enfoque de {minutes} min iniciado" + (f" ({label})" if label else "")
            + ". Cuando termines, dime «terminé el bloque».", "started",
            {"minutes": minutes}, widget)
