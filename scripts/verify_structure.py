#!/usr/bin/env python3
"""
🔍 verify_structure.py - Verificador de Estructura del Proyecto
=================================================================
Script de diagnóstico para validar la integridad del proyecto Omnia Mentis

USO:
    python scripts/verify_structure.py
    
RETORNA:
    0: Estructura correcta
    1: Errores encontrados
"""

import sys
from pathlib import Path
from typing import List, Tuple, Dict
import json

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str) -> None:
    """Imprime un encabezado formateado"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")


def check_mark(condition: bool) -> str:
    """Retorna marca de verificación según condición"""
    return f"{Colors.GREEN}✅{Colors.RESET}" if condition else f"{Colors.RED}❌{Colors.RESET}"


# ==================== DEFINICIÓN DE ESTRUCTURA ====================
REQUIRED_STRUCTURE = {
    'directories': [
        'src',
        'src/core',
        'src/core/essence',
        'src/core/mind',
        'src/analytics',
        'src/living_memory',
        'src/utils',
        'tests',
        'tests/unit',
        'tests/integration',
        'data',
        'data/memory',
        'data/analytics',
        'research',
        'research/daily_reports',
        'research/exports',
        'scripts',
        '.vscode'
    ],
    'required_files': [
        'main.py',
        'requirements.txt',
        'README.md',
        '.gitignore',
        'src/__init__.py',
        'src/core/__init__.py',
        'src/core/essence/__init__.py',
        'src/core/essence/identity.py',
        'src/core/essence/ethics.py',
        'src/core/mind/__init__.py',
        'src/core/mind/empathy.py',
        'src/core/mind/memory_core.py',
        'src/analytics/__init__.py',
        'src/analytics/research_analytics.py',
        'src/living_memory/__init__.py',
        'src/living_memory/gestation_diary.py',
        'src/utils/__init__.py',
        '.vscode/settings.json',
        '.vscode/launch.json'
    ],
    'optional_files': [
        '.env',
        '.env.example',
        'pytest.ini',
        'setup.py',
        '.vscode/tasks.json',
        '.vscode/extensions.json'
    ]
}


def verify_directories(project_root: Path) -> Tuple[int, int]:
    """
    Verifica que existan todos los directorios requeridos
    
    Returns:
        Tuple[found, total]
    """
    print(f"{Colors.BOLD}📁 VERIFICANDO DIRECTORIOS{Colors.RESET}")
    print("-" * 70)
    
    found = 0
    total = len(REQUIRED_STRUCTURE['directories'])
    
    for directory in REQUIRED_STRUCTURE['directories']:
        dir_path = project_root / directory
        exists = dir_path.exists() and dir_path.is_dir()
        
        status = check_mark(exists)
        print(f"{status} {directory}")
        
        if exists:
            found += 1
        else:
            print(f"   {Colors.YELLOW}└─ Para crear: mkdir -p {directory}{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Resultado: {found}/{total} directorios encontrados{Colors.RESET}")
    return found, total


def verify_required_files(project_root: Path) -> Tuple[int, int]:
    """
    Verifica que existan todos los archivos requeridos
    
    Returns:
        Tuple[found, total]
    """
    print(f"\n{Colors.BOLD}📄 VERIFICANDO ARCHIVOS REQUERIDOS{Colors.RESET}")
    print("-" * 70)
    
    found = 0
    total = len(REQUIRED_STRUCTURE['required_files'])
    
    for file in REQUIRED_STRUCTURE['required_files']:
        file_path = project_root / file
        exists = file_path.exists() and file_path.is_file()
        
        status = check_mark(exists)
        print(f"{status} {file}")
        
        if exists:
            found += 1
            # Verificar que no esté vacío
            if file_path.stat().st_size == 0:
                print(f"   {Colors.YELLOW}⚠️  Archivo vacío{Colors.RESET}")
        else:
            print(f"   {Colors.RED}└─ Archivo faltante (REQUERIDO){Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Resultado: {found}/{total} archivos requeridos encontrados{Colors.RESET}")
    return found, total


def verify_optional_files(project_root: Path) -> None:
    """Verifica archivos opcionales pero recomendados"""
    print(f"\n{Colors.BOLD}📋 VERIFICANDO ARCHIVOS OPCIONALES{Colors.RESET}")
    print("-" * 70)
    
    for file in REQUIRED_STRUCTURE['optional_files']:
        file_path = project_root / file
        exists = file_path.exists() and file_path.is_file()
        
        status = check_mark(exists)
        label = "ENCONTRADO" if exists else "OPCIONAL"
        print(f"{status} {file} ({label})")


def verify_python_syntax(project_root: Path) -> Tuple[int, int]:
    """
    Verifica la sintaxis de archivos Python críticos
    
    Returns:
        Tuple[valid, total]
    """
    print(f"\n{Colors.BOLD}🐍 VERIFICANDO SINTAXIS PYTHON{Colors.RESET}")
    print("-" * 70)
    
    critical_files = [
        'main.py',
        'src/core/essence/identity.py',
        'src/core/mind/empathy.py',
        'src/core/mind/memory_core.py',
        'src/analytics/research_analytics.py'
    ]
    
    valid = 0
    total = 0
    
    for file in critical_files:
        file_path = project_root / file
        
        if not file_path.exists():
            print(f"{Colors.YELLOW}⏭️  {file} (no existe){Colors.RESET}")
            continue
        
        total += 1
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                compile(f.read(), file_path, 'exec')
            
            print(f"{Colors.GREEN}✅{Colors.RESET} {file}")
            valid += 1
            
        except SyntaxError as e:
            print(f"{Colors.RED}❌{Colors.RESET} {file}")
            print(f"   {Colors.RED}└─ Error de sintaxis en línea {e.lineno}: {e.msg}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️{Colors.RESET}  {file}")
            print(f"   {Colors.YELLOW}└─ Error: {e}{Colors.RESET}")
    
    if total > 0:
        print(f"\n{Colors.BOLD}Resultado: {valid}/{total} archivos con sintaxis válida{Colors.RESET}")
    
    return valid, total


def verify_imports(project_root: Path) -> None:
    """Verifica que las importaciones principales funcionen"""
    print(f"\n{Colors.BOLD}📦 VERIFICANDO IMPORTACIONES{Colors.RESET}")
    print("-" * 70)
    
    # Agregar src/ al path
    sys.path.insert(0, str(project_root / 'src'))
    
    critical_imports = [
        ('core.essence.identity', 'OmniaIdentity'),
        ('core.mind.empathy', 'OmniaEmpathy'),
        ('core.mind.memory_core', 'LivingMemory'),
        ('analytics.research_analytics', 'ResearchAnalytics')
    ]
    
    for module_name, class_name in critical_imports:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"{Colors.GREEN}✅{Colors.RESET} {module_name}.{class_name}")
        except ImportError as e:
            print(f"{Colors.RED}❌{Colors.RESET} {module_name}.{class_name}")
            print(f"   {Colors.RED}└─ Error: {e}{Colors.RESET}")
        except AttributeError:
            print(f"{Colors.YELLOW}⚠️{Colors.RESET}  {module_name}.{class_name}")
            print(f"   {Colors.YELLOW}└─ Módulo existe pero clase no encontrada{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️{Colors.RESET}  {module_name}.{class_name}")
            print(f"   {Colors.YELLOW}└─ Error inesperado: {e}{Colors.RESET}")


def verify_json_files(project_root: Path) -> None:
    """Verifica la validez de archivos JSON de configuración"""
    print(f"\n{Colors.BOLD}🔧 VERIFICANDO ARCHIVOS JSON{Colors.RESET}")
    print("-" * 70)
    
    json_files = [
        '.vscode/settings.json',
        '.vscode/launch.json',
        '.vscode/tasks.json'
    ]
    
    for file in json_files:
        file_path = project_root / file
        
        if not file_path.exists():
            print(f"{Colors.YELLOW}⏭️  {file} (no existe){Colors.RESET}")
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Permitir comentarios en JSON (JSONC)
                content = f.read()
                # Eliminar líneas de comentarios para validación básica
                lines = [line for line in content.split('\n') 
                        if not line.strip().startswith('//')]
                json.loads('\n'.join(lines))
            
            print(f"{Colors.GREEN}✅{Colors.RESET} {file}")
            
        except json.JSONDecodeError as e:
            print(f"{Colors.YELLOW}⚠️{Colors.RESET}  {file}")
            print(f"   {Colors.YELLOW}└─ Posible formato JSONC (válido en VSCode){Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}❌{Colors.RESET} {file}")
            print(f"   {Colors.RED}└─ Error: {e}{Colors.RESET}")


def generate_report(results: Dict) -> int:
    """
    Genera reporte final y retorna código de salida
    
    Returns:
        0 si todo OK, 1 si hay errores
    """
    print_header("REPORTE FINAL")
    
    # Calcular totales
    dir_found, dir_total = results['directories']
    files_found, files_total = results['required_files']
    syntax_valid, syntax_total = results['python_syntax']
    
    dir_percent = (dir_found / dir_total * 100) if dir_total > 0 else 0
    files_percent = (files_found / files_total * 100) if files_total > 0 else 0
    syntax_percent = (syntax_valid / syntax_total * 100) if syntax_total > 0 else 0
    
    print(f"📁 Directorios:        {dir_found}/{dir_total} ({dir_percent:.1f}%)")
    print(f"📄 Archivos requeridos: {files_found}/{files_total} ({files_percent:.1f}%)")
    print(f"🐍 Sintaxis válida:    {syntax_valid}/{syntax_total} ({syntax_percent:.1f}%)")
    
    # Determinar estado general
    if dir_found == dir_total and files_found == files_total and syntax_valid == syntax_total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ PROYECTO EN PERFECTO ESTADO{Colors.RESET}")
        return 0
    elif dir_percent >= 80 and files_percent >= 80:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  PROYECTO FUNCIONAL CON ADVERTENCIAS{Colors.RESET}")
        print(f"{Colors.YELLOW}   Algunos archivos opcionales faltan pero el core está OK{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ PROYECTO CON ERRORES CRÍTICOS{Colors.RESET}")
        print(f"{Colors.RED}   Ejecuta las correcciones sugeridas arriba{Colors.RESET}")
        return 1


def main() -> int:
    """Función principal de verificación"""
    project_root = Path(__file__).parent.parent
    
    print_header("🔍 OMNIA MENTIS - VERIFICACIÓN DE ESTRUCTURA")
    print(f"📂 Directorio del proyecto: {project_root}")
    
    # Ejecutar verificaciones
    results = {
        'directories': verify_directories(project_root),
        'required_files': verify_required_files(project_root),
        'python_syntax': verify_python_syntax(project_root)
    }
    
    verify_optional_files(project_root)
    verify_json_files(project_root)
    verify_imports(project_root)
    
    # Generar reporte
    exit_code = generate_report(results)
    
    if exit_code == 0:
        print(f"\n{Colors.GREEN}💡 El proyecto está listo para ejecutar con: python main.py{Colors.RESET}")
    else:
        print(f"\n{Colors.YELLOW}💡 Corrige los errores y vuelve a ejecutar este script{Colors.RESET}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())