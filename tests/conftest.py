# tests/conftest.py
"""
* UBICACIÓN: OmniaMentis/tests/conftest.py
* PROPÓSITO: Fixtures compartidas para toda la suite de tests pytest.
* DEPENDENCIAS: pytest
* CREADO: 2026-06-18
* ÚLTIMA MODIFICACIÓN: 2026-06-18
* ESTADO: Test Permanente
*
* pytest descarga este archivo automáticamente antes de correr cualquier
* test. Las fixtures definidas aquí están disponibles en todos los
* archivos de la carpeta tests/ y sus subdirectorios sin necesidad de
* importarlas explícitamente.
"""

import sys
from pathlib import Path

import pytest

# Garantizar que src/ esté en el path sin importar desde dónde se
# invoque pytest (raíz del proyecto, carpeta tests/, etc.)
SRC_PATH = Path(__file__).parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


# ---------------------------------------------------------------------------
# Fixture: engine
# Scope: function (nueva instancia por cada test que la use)
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """
    Instancia limpia de ConsciousnessGrowthEngine para tests de growth.
    Se recrea por cada test para garantizar estado inicial idéntico.
    """
    from core.consciousness.growth_engine import ConsciousnessGrowthEngine
    return ConsciousnessGrowthEngine()


# ---------------------------------------------------------------------------
# Fixture: ethics_dir (alias de tmp_path para legibilidad en test_ethics.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def ethics_dir(tmp_path):
    """
    Directorio temporal aislado para cada test de OmniaEthics.
    Evita que las consultas a El Fons de un test contaminen a otro.
    """
    d = tmp_path / "ethics"
    d.mkdir()
    return d