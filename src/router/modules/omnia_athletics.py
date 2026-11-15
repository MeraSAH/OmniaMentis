"""
* UBICACIÓN: OmniaMentis/src/router/modules/omnia_athletics.py
* PROPÓSITO: Módulo enrutable de entrenamiento físico. NO calcula nada por su
*            cuenta: usa el motor (core/fitness/training.py) y guarda en el
*            almacén único que le entrega el contexto. Solo presenta el resultado.
* DEPENDENCIAS: base_module.py, core/fitness/training.py
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-10-18
* ESTADO: Producción
*
* CAMBIO 2026-10-18: deja de ser un stub. Arma rutinas semanales (2-6 días,
* casa o gimnasio), registra entrenamientos y resume la semana. Acceso desde
* los 15 años (policy.py). Para menores: máximo 4 días, sin fuerza máxima y sin
* metas de definición/bajar de peso (eso nunca se ofrece a menores).
"""

import logging
import re
import time
from typing import Callable, List

from core.fitness import training as tr
from .base_module import OmniaModule, OmniaContext, ModuleResponse

logger = logging.getLogger(__name__)

MODULE_NAME = "OmniaAthletics"
_LOG = re.compile(r"\bentren[eé]\b|registr\w*\s+(?:mi\s+|el\s+)?entrenamiento|hice ejercicio|"
                  r"termin[eé]\s+(?:mi\s+|el\s+)?entrenamiento", re.I)
_SUMMARY = re.compile(r"progreso|resumen|cu[aá]nto he entrenado|cu[aá]ntas veces|esta semana", re.I)


class OmniaAthleticsModule(OmniaModule):

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock

    @property
    def name(self) -> str:
        return MODULE_NAME

    def keywords(self) -> List[str]:
        return [
            "entrenar", "entrenamiento", "ejercicio", "rutina", "gym",
            "gimnasio", "pesas", "cardio", "correr", "running",
            "rendimiento deportivo", "musculo", "músculo", "fuerza",
            "resistencia", "repeticiones", "series",
            "entrené", "entrene", "mi rutina", "hice ejercicio",
        ]

    def _resp(self, text: str, status: str, followup: bool = False, data=None) -> ModuleResponse:
        payload = {"status": status, "domain": "athletics"}
        if data:
            payload.update(data)
        return ModuleResponse(text=text, module_name=self.name, requires_followup=followup, data=payload)

    def _save(self, context: OmniaContext, kind: str, payload: dict) -> bool:
        if context.data_store is None:
            return False
        try:
            context.data_store.add(context.user_id, self.name, kind, dict(payload))
            return True
        except Exception as exc:  # el resultado sigue valiendo aunque no se guarde
            logger.warning("OmniaAthletics: no se pudo guardar (%s): %s", kind, exc)
            return False

    def handle(self, message: str, context: OmniaContext) -> ModuleResponse:
        adult = context.age_band == tr.ADULT
        text = message or ""

        # Definición / bajar de peso: nunca a menores; a adultos se les remite a la parte de alimentación.
        if tr.wants_fat_loss(text):
            if not adult:
                return self._resp(
                    "No armo rutinas para definir ni para bajar de peso: a tu edad el cuerpo está creciendo y eso "
                    "debe verlo un pediatra o un profesional del deporte. Sí puedo armarte una rutina para ganar "
                    "fuerza, condición y salud, o llevar el registro de tus entrenamientos. "
                    "Si algo de tu cuerpo te preocupa, cuéntaselo a un adulto de confianza.",
                    "minor_safe_redirect")
            text_note = ("Para cambiar tu composición corporal lo más importante es la alimentación (NutriVida); "
                         "el ejercicio la acompaña. Te dejo una rutina general.\n\n")
        else:
            text_note = ""

        if _LOG.search(text):
            return self._log_workout(text, context)
        if _SUMMARY.search(text):
            return self._summary(context)
        return self._routine(text, context, text_note)

    # ------------------------------------------------------------------
    def _routine(self, text: str, context: OmniaContext, note: str) -> ModuleResponse:
        req = tr.parse_request(text)
        try:
            r = tr.build_routine(context.age_band, **req)
        except tr.InvalidRequest as exc:
            return self._resp(str(exc), "invalid_request", followup=True)
        lines = [note + tr.format_routine(r)]
        if r["assumed"]:
            lines.append("\nSupuse: " + ", ".join(r["assumed"]) + ". Dime si quieres cambiar algo "
                         "(días, nivel principiante/intermedio/avanzado, objetivo salud/fuerza/masa/resistencia, casa o gimnasio).")
        if r["adjusted"]:
            lines.append("Ajusté por tu edad: " + "; ".join(r["adjusted"]) + ".")
        lines.append("\n" + "\n".join("• " + n for n in tr.routine_notes(r["minor"])))
        data = {"days": r["days"], "level": r["level"], "goal": r["goal"], "place": r["place"],
                "sessions": len(r["sessions"])}
        data["saved"] = self._save(context, "rutina", data)
        return self._resp("\n".join(lines), "routine", followup=bool(r["assumed"]), data=data)

    def _log_workout(self, text: str, context: OmniaContext) -> ModuleResponse:
        minutes = tr.parse_minutes(text)
        if minutes is None:
            return self._resp("Dime cuánto duró tu entrenamiento, por ejemplo: «entrené 45 minutos».",
                              "needs_minutes", followup=True)
        if not tr.valid_minutes(minutes):
            return self._resp(f"Un entrenamiento debe durar entre {tr.MIN_SESSION_MIN} y {tr.MAX_SESSION_MIN} minutos.",
                              "invalid_minutes", followup=True)
        if context.data_store is None:
            return self._resp("Ahora mismo no puedo guardar tus entrenamientos. Inténtalo más tarde.", "unavailable")
        try:
            context.data_store.add(context.user_id, self.name, "entreno", {"minutes": minutes})
            week = self._week(context)
        except Exception as exc:
            logger.warning("OmniaAthletics: error con el almacén: %s", exc)
            return self._resp("No pude guardar tu entrenamiento ahora mismo.", "not_saved")
        return self._resp(
            f"Entrenamiento de {minutes:g} min registrado. Esta semana: {week['sessions']} sesión(es), "
            f"{week['minutes']:g} min. {tr.activity_reference(context.age_band)}",
            "logged", data={"minutes": minutes, "week": week})

    def _week(self, context: OmniaContext) -> dict:
        rows = context.data_store.list(context.user_id, self.name, "entreno", limit=200)
        return tr.summarize_week(rows, self._clock())

    def _summary(self, context: OmniaContext) -> ModuleResponse:
        if context.data_store is None:
            return self._resp("Ahora mismo no puedo leer tus entrenamientos. Inténtalo más tarde.", "unavailable")
        try:
            week = self._week(context)
        except Exception as exc:
            logger.warning("OmniaAthletics: error con el almacén: %s", exc)
            return self._resp("No pude leer tus entrenamientos ahora mismo.", "unavailable")
        if week["sessions"] == 0:
            msg = "No tienes entrenamientos registrados en los últimos 7 días. Cuando entrenes, dime «entrené 45 minutos»."
        else:
            msg = f"Últimos 7 días: {week['sessions']} sesión(es), {week['minutes']:g} min."
        return self._resp(msg + " " + tr.activity_reference(context.age_band), "summary", data={"week": week})
