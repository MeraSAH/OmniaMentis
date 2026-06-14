#!/usr/bin/env python3
"""
🔧 setup_project.py - Script de Configuración Automatizada
===========================================================
Crea todos los archivos de configuración necesarios para Omnia Mentis

USO:
    python scripts/setup_project.py
    
OPCIONES:
    --force : Sobrescribir archivos existentes
    --minimal : Solo crear archivos esenciales
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def create_file(path: Path, content: str, force: bool = False) -> bool:
    """
    Crea un archivo con el contenido especificado
    
    Args:
        path: Ruta del archivo
        content: Contenido a escribir
        force: Sobrescribir si existe
    
    Returns:
        bool: True si se creó/actualizó
    """
    try:
        if path.exists() and not force:
            print(f"{Colors.YELLOW}⏭️  {Colors.RESET}{path} (ya existe, usa --force para sobrescribir)")
            return False
        
        # Crear directorio padre si no existe
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir contenido
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"{Colors.GREEN}✅{Colors.RESET} {path}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌{Colors.RESET} {path}: {e}")
        return False


# ==================== CONTENIDOS DE ARCHIVOS ====================

PY_TYPED = ""

ENV_EXAMPLE = """# Configuración de ejemplo para Omnia Mentis
# Copia este archivo a .env y ajusta los valores

# ===== CONFIGURACIÓN GENERAL =====
OMNIA_VERSION=1.0.0
RESEARCH_MODE=true
DEBUG_MODE=false

# ===== DIRECTORIOS =====
DATA_DIR=./data
RESEARCH_DIR=./research

# ===== CONSCIENCIA =====
INITIAL_CONSCIOUSNESS=0.05
CONSCIOUSNESS_INCREMENT=0.0001

# ===== LOGGING =====
LOG_LEVEL=INFO
"""

PYTEST_INI = """[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short

markers =
    unit: Tests unitarios
    integration: Tests de integración
    slow: Tests lentos
"""

GITKEEP = ""

MYPY_INI = """[mypy]
mypy_path = src
python_version = 3.10
ignore_missing_imports = True
check_untyped_defs = True
"""

PYRIGHTCONFIG = """{
  "include": ["src", "tests"],
  "exclude": ["**/__pycache__", ".venv"],
  "pythonVersion": "3.10",
  "typeCheckingMode": "basic"
}
"""

# ==================== CONFIGURACIÓN DE ARCHIVOS ====================

FILES_CONFIG: Dict[str, Dict[str, Any]] = {
    "essential": {
        "src/py.typed": PY_TYPED,
        ".env.example": ENV_EXAMPLE,
        "pytest.ini": PYTEST_INI,
        "mypy.ini": MYPY_INI,
        "data/.gitkeep": GITKEEP,
        "data/memory/.gitkeep": GITKEEP,
        "data/analytics/.gitkeep": GITKEEP,
    },
    "optional": {
        "pyrightconfig.json": PYRIGHTCONFIG,
        "logs/.gitkeep": GITKEEP,
    }
}


def setup_project(force: bool = False, minimal: bool = False) -> None:
    """
    Configura el proyecto completo
    
    Args:
        force: Sobrescribir archivos existentes
        minimal: Solo crear archivos esenciales
    """
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}🔧 CONFIGURACIÓN AUTOMATIZADA DE OMNIA MENTIS{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")
    print(f"📂 Directorio: {project_root}\n")
    
    created = 0
    skipped = 0
    failed = 0
    
    # Crear archivos esenciales
    print(f"{Colors.BOLD}📄 ARCHIVOS ESENCIALES{Colors.RESET}")
    print("-" * 70)
    
    for file_path, content in FILES_CONFIG["essential"].items():
        path = project_root / file_path
        if create_file(path, content, force):
            created += 1
        else:
            skipped += 1
    
    # Crear archivos opcionales si no es minimal
    if not minimal:
        print(f"\n{Colors.BOLD}📋 ARCHIVOS OPCIONALES{Colors.RESET}")
        print("-" * 70)
        
        for file_path, content in FILES_CONFIG["optional"].items():
            path = project_root / file_path
            if create_file(path, content, force):
                created += 1
            else:
                skipped += 1
    
    # Crear directorios vacíos con .gitkeep
    print(f"\n{Colors.BOLD}📁 ESTRUCTURA DE DIRECTORIOS{Colors.RESET}")
    print("-" * 70)
    
    directories = [
        "tests/unit",
        "tests/integration",
        "scripts",
        "docs",
        "logs",
    ]
    
    for directory in directories:
        dir_path = project_root / directory
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            gitkeep = dir_path / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()
                print(f"{Colors.GREEN}✅{Colors.RESET} {directory}/")
                created += 1
            else:
                print(f"{Colors.YELLOW}⏭️{Colors.RESET}  {directory}/ (ya existe)")
                skipped += 1
        except Exception as e:
            print(f"{Colors.RED}❌{Colors.RESET} {directory}/: {e}")
            failed += 1
    
    # Resumen
    print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}📊 RESUMEN{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"✅ Creados: {created}")
    print(f"⏭️  Omitidos: {skipped}")
    if failed > 0:
        print(f"❌ Fallidos: {failed}")
    
    # Instrucciones siguientes
    print(f"\n{Colors.BOLD}🎯 PRÓXIMOS PASOS:{Colors.RESET}")
    print("1. Copia .env.example a .env y ajusta las configuraciones")
    print("2. Ejecuta: python scripts/verify_structure.py")
    print("3. Ejecuta: python main.py")
    
    if failed > 0:
        print(f"\n{Colors.RED}⚠️  Algunos archivos no se pudieron crear. Revisa los errores arriba.{Colors.RESET}")
        sys.exit(1)
    else:
        print(f"\n{Colors.GREEN}✅ Configuración completada exitosamente{Colors.RESET}")


def main() -> None:
    """Punto de entrada principal"""
    force = "--force" in sys.argv
    minimal = "--minimal" in sys.argv
    
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    setup_project(force=force, minimal=minimal)


if __name__ == "__main__":
    main()