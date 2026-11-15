"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_habits.py
* PROPÓSITO: Módulo de hábitos. NO calcula nada por su cuenta: usa el motor
*            (core/habits/habits.py) y guarda en el almacén único que entrega el
*            contexto. Solo presenta el resultado.
* DEPENDENCIAS: base_module.py, core/habits/habits.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-10-18
* ESTADO: Producción
*
* CAMBIO 2026-10-18: deja de ser un stub. "completé el entrenamiento de élite"
* registra el hábito (una vez por día), suma puntos con multiplicador, devuelve
* el color para el pulso de luz ("Aura Canvas", widget `aura_pulse`), el
* progreso del día y la racha.
"""

import logging
import time
from typing import Callable, List

from core.habits import habits as hb
from .base_module import OmniaModule, OmniaContext, ModuleResponse

logger = logging.getLogger(__name__)

MODULE_NAME = "OmniaHabits"
HISTORY_WINDOW = 500  # últimos registros leídos (tope del almacén por consulta)


class OmniaHabitsModule(OmniaModule):

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock

    @property
    def name(self) -> str:
        return MODULE_NAME

    def keywords(self) -> List[str]:
        return [
            "habito", "hábito", "racha", "constancia", "rutina diaria",
            "recordatorio", "meta diaria", "objetivo diario",
            "seguimiento de habitos", "seguimiento de hábitos",
            "streak", "disciplina",
            # hábitos del catálogo y verbos de cumplimiento
            "victoria magistral", "ducha de choque", "entrenamiento de élite",
            "entrenamiento de elite", "estado de sobriedad", "bitácora de objetivos",
            "bitacora de objetivos", "completé", "complete el", "marqué", "marque el",
        ]

    def _resp(self, text, status, data=None, widget=None) -> ModuleResponse:
        payload = {"status": status, "domain": "habits"}
        if data:
            payload.update(data)
        return ModuleResponse(
            text=text, module_name=self.name, requires_followup=False, data=payload,
            widget_type="aura_pulse" if widget else None, widget_payload=widget)

    @staticmethod
    def _catalog_text() -> str:
        return "; ".join(f"{h['name']} (×{h['multiplier']})" for h in hb.HABITS)

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        store = context.data_store
        if store is None:
            return self._resp("Ahora mismo no puedo guardar tus hábitos. Inténtalo más tarde.", "unavailable")

        now = self._clock()
        today = hb.day_key(now)
        try:
            rows = store.list(context.user_id, self.name, "check", limit=HISTORY_WINDOW)
        except Exception as exc:
            logger.warning("OmniaHabits: no se pudo leer el historial: %s", exc)
            return self._resp("No pude leer tu historial de hábitos ahora mismo.", "unavailable")

        payloads = [r.get("payload") or {} for r in rows]
        today_ids = [p.get("habit") for p in payloads if p.get("day") == today]
        habit = hb.find_habit(message)
        completing = habit is not None and hb.is_completion(message)

        if completing and habit["id"] in today_ids:
            return self._summary(f"Ya registraste «{habit['name']}» hoy: no suma dos veces el mismo día.",
                                 "already_done", payloads, today_ids, today)

        if completing:
            pts = hb.points_for(habit["id"])
            try:
                store.add(context.user_id, self.name, "check",
                          {"habit": habit["id"], "day": today, "points": pts})
            except Exception as exc:
                logger.warning("OmniaHabits: no se pudo guardar el hábito: %s", exc)
                return self._resp("No pude guardar ese hábito, así que no se sumaron puntos. Inténtalo de nuevo.",
                                  "not_saved")
            today_ids.append(habit["id"])
            payloads = payloads + [{"habit": habit["id"], "day": today}]
            widget = {"color_hex": habit["color_hex"], "color_name": habit["color_name"],
                      "habit": habit["name"], "points": pts}
            return self._summary(f"✅ {habit['name']} registrado: +{pts} puntos (×{habit['multiplier']}).",
                                 "checked", payloads, today_ids, today,
                                 extra={"habit": habit["id"], "points": pts}, widget=widget)

        if habit is not None:
            return self._summary(
                f"«{habit['name']}» vale {hb.points_for(habit['id'])} puntos (×{habit['multiplier']}). "
                f"Cuando lo cumplas, dime «completé {habit['name'].lower()}».",
                "info", payloads, today_ids, today)

        if hb.is_status_request(message):
            return self._summary("Así vas hoy:", "summary", payloads, today_ids, today)

        return self._summary(
            "Puedo llevar tus hábitos con puntos. Hábitos y multiplicadores: " + self._catalog_text()
            + ". Dime, por ejemplo, «completé el entrenamiento de élite».",
            "help", payloads, today_ids, today)

    def _summary(self, head, status, payloads, today_ids, today, extra=None, widget=None) -> ModuleResponse:
        prog = hb.progress(today_ids)
        run = hb.streak([p.get("day") for p in payloads], today)
        text = (f"{head}\nPuntos de hoy: {prog['obtained']} · Restantes: {prog['remaining']} · "
                f"Carga: {prog['percent']} %\nRacha: {run} día(s).")
        data = {"progress": prog, "streak": run}
        if extra:
            data.update(extra)
        return self._resp(text, status, data, widget)
