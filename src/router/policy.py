"""
* UBICACION: OmniaMentis/src/router/policy.py
* PROPOSITO: Politica de acceso de los modulos del ecosistema por rango de edad.
*            Es el UNICO lugar donde se decide quien puede usar cada modulo.
* DEPENDENCIAS: ninguna
* CREADO: 2026-10-17
* ESTADO: Produccion
*
* PRINCIPIO (decision del responsable, 2026-10-16): OmniaMentis es el motor
* que decide todo. Los modulos NO toman decisiones ni procesan por su cuenta:
* ni siquiera deciden si el usuario puede entrar. Por eso la tabla vive aqui,
* en el motor, y no dentro de cada modulo.
*
* FAIL-CLOSED: un modulo que no aparece en la tabla, o un rango de edad
* desconocido/vacio, se DENIEGA. Un modulo nuevo queda bloqueado hasta que
* alguien lo agregue a la tabla de forma explicita.
*
* Rangos (mismos valores que devuelve accounts.age_band()):
*   minor        13-14 anos (con representante confirmado)
*   minor_basic  15-17 anos
*   adult        18+
"""

from typing import Dict

# Orden ascendente: un rango "alcanza" a todos los minimos iguales o menores.
AGE_BANDS = ("minor", "minor_basic", "adult")

# Rango MINIMO para cada modulo (clave = OmniaModule.name).
MODULE_MIN_AGE_BAND: Dict[str, str] = {
    # Capa de optimizacion personal
    "NutriVida": "minor",
    "OmniaAthletics": "minor_basic",   # rutinas de definicion/deficit: no a 13-14
    "Corporal Verified": "adult",      # menores: hasta tener criterio legal y verificacion real
    # Capa de productividad
    "OmniaHabits": "minor",
    "OmniaChronos": "minor",
    # Capa de negocio, desarrollo y estetica
    "OmniaStudio": "minor",
    "OmniaCore": "minor",
    "OmniaForge": "adult",             # ejecuta codigo
    "OmniaEngine": "adult",            # embudos de venta y cotizaciones
}


def band_allows(user_band: object, min_band: object) -> bool:
    """True si `user_band` es igual o superior a `min_band`.
    Cualquier valor desconocido (o no texto) devuelve False."""
    if not isinstance(user_band, str) or not isinstance(min_band, str):
        return False
    if user_band not in AGE_BANDS or min_band not in AGE_BANDS:
        return False
    return AGE_BANDS.index(user_band) >= AGE_BANDS.index(min_band)


def module_allowed(module_name: str, user_band: object, policy: Dict[str, str] = None) -> bool:
    """True si el rango de edad puede usar el modulo. Modulo sin regla = False."""
    table = MODULE_MIN_AGE_BAND if policy is None else policy
    min_band = table.get(module_name)
    if min_band is None:
        return False
    return band_allows(user_band, min_band)
