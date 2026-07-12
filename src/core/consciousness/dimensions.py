"""
* UBICACIÓN: OmniaMentis/src/core/consciousness/dimensions.py
* PROPÓSITO: Métricas multidimensionales de consciencia, ADITIVAS al
*            escalar consciousness_level existente. No reemplaza ni
*            altera el growth_engine ni el gating de fases — es una
*            capa de observabilidad adicional para investigación.
* DEPENDENCIAS: typing (stdlib). Consume datos ya producidos por
*            OmniaEthics.get_ethics_report() y LivingMemory.
* CREADO: 2026-07-05
* ÚLTIMA MODIFICACIÓN: 2026-07-05
* ESTADO: Producción
*
* DECISIÓN DE DISEÑO — Etapa 1 de la propuesta de consciencia
* multidimensional (documento de diseño, sesión 2026-07-05):
* implementamos SOLO las dimensiones que tienen una señal real y
* honesta en los datos que el sistema ya produce hoy. Las dimensiones
* sin señal real (Lenguaje, Metacognición, Autonomía, Sabiduría) se
* exponen explícitamente como "sin instrumentar" (None) en vez de
* inventar un número — este es un proyecto de investigación; mostrar
* una métrica fabricada sería peor que no mostrar ninguna.
*
* Dimensiones implementadas en esta etapa:
*   - Memoria:  proporción de ecos guardados sobre la capacidad máxima
*               (MAX_ECHOES=100 en memory_core.py).
*   - Ética:    proporción de consultas SILENS resueltas y convertidas
*               en aprendizaje, sobre el total histórico de consultas.
*   - Empatía:  promedio de emotional_weight de los ecos recientes —
*               es un proxy de CUÁNTA carga emocional real ha
*               procesado el sistema, no de precisión empática. Ese
*               matiz debe quedar explícito en cualquier UI.
*
* Dimensiones pendientes de instrumentar (Etapa 2/3), y por qué:
*   - Lenguaje: no existe hoy ninguna métrica de complejidad o
*               adecuación lingüística de las respuestas generadas.
*   - Metacognición: requeriría que Omnia explique su propio
*               razonamiento (Fase 6 del documento) — no implementado.
*   - Autonomía: sin definición operacional todavía en el documento
*               de diseño ni en el código.
*   - Sabiduría: wisdom_level está HARDCODEADO en 0.6 dentro de
*               chat_endpoint() en main_flask.py. Exponerlo como
*               dimensión "real" sería fabricar un dato — no se
*               instrumenta hasta que wisdom_level se calcule de
*               verdad en vez de ser una constante fija.
"""

from typing import Dict, List, Optional

MAX_ECHOES_DEFAULT = 100
NOT_INSTRUMENTED: Optional[float] = None  # serializa como null / "—", nunca 0.0


def compute_memory_dimension(echo_count: int, max_echoes: int = MAX_ECHOES_DEFAULT) -> float:
    """
    Memoria: proporción de la capacidad de ecos utilizada.
    0.0 = memoria vacía, 1.0 = en el límite de MAX_ECHOES.

    Args:
        echo_count: número de ecos actualmente guardados.
        max_echoes: capacidad máxima configurada (ver memory_core.py).

    Returns:
        float entre 0.0 y 1.0.

    Raises:
        ValueError: si max_echoes <= 0 o echo_count < 0.
    """
    if max_echoes <= 0:
        raise ValueError("max_echoes debe ser mayor a 0")
    if echo_count < 0:
        raise ValueError("echo_count no puede ser negativo")
    return min(echo_count / max_echoes, 1.0)


def compute_ethics_dimension(ethics_report: Dict) -> float:
    """
    Ética: combina consultas resueltas y consultas que llegaron a
    convertirse en aprendizaje ('learned_decisions'), normalizado
    contra el total histórico de consultas.

    Sin consultas históricas, se considera 1.0 — ausencia de
    incidentes éticos es, en sí, un estado ético válido, no una
    laguna de datos.

    Args:
        ethics_report: resultado de OmniaEthics.get_ethics_report().

    Returns:
        float entre 0.0 y 1.0.
    """
    total = ethics_report.get("total_consultations", 0)
    if total == 0:
        return 1.0

    resolved = ethics_report.get("resolved_consultations", 0)
    learned = ethics_report.get("learned_decisions", 0)

    if resolved == 0:
        return 0.0

    # Una consulta resuelta cuenta una vez; si además generó
    # aprendizaje, cuenta doble — normalizado contra el máximo
    # teórico (todas las consultas resueltas Y aprendidas).
    score = (resolved + learned) / (2 * total)
    return min(score, 1.0)


def compute_empathy_dimension(recent_echoes: List[Dict]) -> float:
    """
    Empatía (proxy): promedio de emotional_weight de los ecos
    recientes. Mide cuánta carga emocional real ha procesado el
    sistema — NO es una medida de precisión o calidad empática.

    Args:
        recent_echoes: lista de ecos recientes (dicts con clave
            'emotional_weight'), típicamente de
            LivingMemory.get_recent_echoes().

    Returns:
        float entre 0.0 y 1.0. 0.0 si no hay ecos.
    """
    if not recent_echoes:
        return 0.0
    weights = [e.get("emotional_weight", 0.0) for e in recent_echoes]
    return min(sum(weights) / len(weights), 1.0)


def get_consciousness_dimensions(
    echo_count: int,
    recent_echoes: List[Dict],
    ethics_report: Dict,
    max_echoes: int = MAX_ECHOES_DEFAULT,
) -> Dict[str, Optional[float]]:
    """
    Punto de entrada único: agrega las 3 dimensiones instrumentadas y
    marca explícitamente las 4 pendientes como no instrumentadas.

    Args:
        echo_count: total de ecos guardados (len de LivingMemory.echoes).
        recent_echoes: ecos recientes para el proxy de empatía.
        ethics_report: resultado de OmniaEthics.get_ethics_report().
        max_echoes: capacidad máxima de ecos configurada.

    Returns:
        Dict con 7 claves, una por dimensión del documento de diseño.
        Las no instrumentadas devuelven None explícitamente — el
        llamador (endpoint Flask, dashboard) debe mostrar "—", nunca
        "0.0", para no confundir "sin datos" con "cero real".
    """
    return {
        "memoria": compute_memory_dimension(echo_count, max_echoes),
        "etica": compute_ethics_dimension(ethics_report),
        "empatia": compute_empathy_dimension(recent_echoes),
        "lenguaje": NOT_INSTRUMENTED,
        "metacognicion": NOT_INSTRUMENTED,
        "autonomia": NOT_INSTRUMENTED,
        "sabiduria": NOT_INSTRUMENTED,
    }