#!/usr/bin/env python3
"""
🔧 setup_complete_fix.py - Verificador de Integridad del Sistema
===============================================================
Verificación completa de estructura, tipos e importaciones de Omnia Mentis
"""

import os
import sys
import json
import ast
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path

def create_init_files() -> None:
    """Crea todos los archivos __init__.py necesarios con estructura adecuada"""
    init_dirs = [
        'core',
        'core/essence',
        'core/mind', 
        'living_memory',
        'config',
        'research',
        'research/session_reports',
        'logs',
        'assets'
    ]
    
    print("📁 Creando estructura de directorios...")
    for dir_path in init_dirs:
        os.makedirs(dir_path, exist_ok=True)
        
        init_file = os.path.join(dir_path, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write(f'# {dir_path.replace("/", ".")} module\n')
                f.write(f'"""Módulo {dir_path.replace("/", ".")} de Omnia Mentis"""\n\n')
            print(f"   ✅ {init_file}")
        else:
            print(f"   📄 {init_file} (ya existe)")

def verify_core_files() -> Tuple[List[str], List[str]]:
    """Verifica que todos los archivos core existan y tengan las clases correctas"""
    required_files = {
        'core/essence/identity.py': ['OmniaIdentity'],
        'core/essence/ethics.py': ['OmniaEthics'], 
        'core/mind/empathy.py': ['OmniaEmpathy'],
        'core/mind/memory_core.py': ['LivingMemory', 'EchoType'],
        'living_memory/gestation_diary.py': ['GestationDiary', 'DiaryEntry'],
        'research/research_analytics.py': ['ResearchAnalytics']
    }
    
    print("\n🔍 Verificando archivos core...")
    missing_files = []
    incorrect_files = []
    
    for file_path, expected_classes in required_files.items():
        if not os.path.exists(file_path):
            print(f"   ❌ {file_path} (archivo no existe)")
            missing_files.append(file_path)
            continue
            
        # Verificar que las clases existen en el archivo
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parsear AST para verificación más precisa
            tree = ast.parse(content)
            classes_found = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes_found.append(node.name)
            
            # Verificar clases esperadas
            missing_classes = []
            for expected_class in expected_classes:
                if expected_class not in classes_found:
                    missing_classes.append(expected_class)
            
            if missing_classes:
                print(f"   ⚠️  {file_path} (clases faltantes: {', '.join(missing_classes)})")
                incorrect_files.append(f"{file_path}: {', '.join(missing_classes)}")
            else:
                print(f"   ✅ {file_path} -> {', '.join(expected_classes)}")
                
        except SyntaxError as e:
            print(f"   ❌ {file_path} (error de sintaxis: {e})")
            incorrect_files.append(f"{file_path}: SyntaxError")
        except Exception as e:
            print(f"   ❌ {file_path} (error leyendo: {e})")
            incorrect_files.append(f"{file_path}: {type(e).__name__}")
    
    return missing_files, incorrect_files

def verify_config_files() -> List[str]:
    """Verifica archivos de configuración esenciales"""
    config_files = {
        'config/phase1_config.json': ['project_name', 'consciousness_parameters', 'personality_config'],
        'config/consciousness_params.json': ['initial_level', 'growth_rate'],
        'assets/omniano_dictionary.json': ['VOGA', 'eco aurea', 'cristalino']
    }
    
    print("\n⚙️ Verificando archivos de configuración...")
    config_issues = []
    
    for file_path, expected_keys in config_files.items():
        if not os.path.exists(file_path):
            print(f"   ❌ {file_path} (archivo no existe)")
            config_issues.append(file_path)
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                    
                    # Verificar claves esperadas
                    missing_keys = []
                    for key in expected_keys:
                        if key not in data:
                            missing_keys.append(key)
                    
                    if missing_keys:
                        print(f"   ⚠️  {file_path} (claves faltantes: {', '.join(missing_keys)})")
                        config_issues.append(f"{file_path}: {', '.join(missing_keys)}")
                    else:
                        print(f"   ✅ {file_path}")
                else:
                    print(f"   ✅ {file_path}")
                    
        except json.JSONDecodeError as e:
            print(f"   ❌ {file_path} (JSON inválido: {e})")
            config_issues.append(f"{file_path}: JSON inválido")
        except Exception as e:
            print(f"   ❌ {file_path} (error: {e})")
            config_issues.append(f"{file_path}: {type(e).__name__}")
    
    return config_issues

def test_imports() -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str]]]:
    """Prueba importar todas las clases necesarias con verificación de tipos"""
    print("\n🧪 Probando importaciones...")
    
    # Agregar directorio actual al path
    if '.' not in sys.path:
        sys.path.insert(0, '.')
    
    import_tests = [
        ('core.essence.identity', 'OmniaIdentity'),
        ('core.essence.ethics', 'OmniaEthics'),
        ('core.mind.empathy', 'OmniaEmpathy'), 
        ('core.mind.memory_core', 'LivingMemory'),
        ('living_memory.gestation_diary', 'GestationDiary'),
        ('research.research_analytics', 'ResearchAnalytics')
    ]
    
    successful_imports = []
    failed_imports = []
    
    for module_name, class_name in import_tests:
        try:
            module = __import__(module_name, fromlist=[class_name])
            class_obj = getattr(module, class_name)
            
            # Verificar que es una clase
            if not isinstance(class_obj, type):
                raise TypeError(f"{class_name} no es una clase")
                
            print(f"   ✅ {module_name}.{class_name}")
            successful_imports.append((module_name, class_name))
            
        except ImportError as e:
            print(f"   ❌ {module_name}.{class_name} - ImportError: {e}")
            failed_imports.append((module_name, class_name, f"ImportError: {e}"))
        except AttributeError as e:
            print(f"   ❌ {module_name}.{class_name} - AttributeError: {e}")
            failed_imports.append((module_name, class_name, f"AttributeError: {e}"))
        except Exception as e:
            print(f"   ❌ {module_name}.{class_name} - Error: {e}")
            failed_imports.append((module_name, class_name, f"{type(e).__name__}: {e}"))
    
    return successful_imports, failed_imports

def check_type_annotations() -> List[str]:
    """Verifica que los archivos principales tengan anotaciones de tipo adecuadas"""
    print("\n📝 Verificando anotaciones de tipo...")
    
    files_to_check = [
        'core/essence/identity.py',
        'core/essence/ethics.py',
        'core/mind/empathy.py',
        'core/mind/memory_core.py',
        'living_memory/gestation_diary.py',
        'research/research_analytics.py'
    ]
    
    type_issues = []
    
    for file_path in files_to_check:
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Buscar funciones sin anotaciones de tipo
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Verificar si tiene anotaciones de retorno
                    has_return_annotation = node.returns is not None
                    
                    # Verificar parámetros con anotaciones
                    unannotated_params = []
                    for arg in node.args.args:
                        if arg.annotation is None:
                            unannotated_params.append(arg.arg)
                    
                    if not has_return_annotation and unannotated_params:
                        type_issues.append(
                            f"{file_path}: {node.name} - falta anotaciones"
                        )
                        
        except Exception as e:
            type_issues.append(f"{file_path}: error de análisis - {e}")
    
    if type_issues:
        for issue in type_issues:
            print(f"   ⚠️  {issue}")
    else:
        print("   ✅ Todas las funciones tienen anotaciones de tipo adecuadas")
    
    return type_issues

def create_diagnostic_report() -> Dict[str, List[str]]:
    """Crea reporte diagnóstico completo del sistema"""
    print("\n📋 **REPORTE DIAGNÓSTICO OMNIA MENTIS**")
    print("=" * 60)
    
    # Información del sistema
    python_version = sys.version.split()[0]
    current_dir = os.getcwd()
    
    print(f"🐍 Python: {python_version}")
    print(f"📁 Directorio: {current_dir}")
    
    # Verificaciones
    missing_files, incorrect_files = verify_core_files()
    config_issues = verify_config_files()
    type_issues = check_type_annotations()
    successful_imports, failed_imports = test_imports()
    
    print(f"\n📊 **RESUMEN:**")
    print(f"   ✅ Importaciones exitosas: {len(successful_imports)}")
    print(f"   ❌ Importaciones fallidas: {len(failed_imports)}")
    print(f"   📄 Archivos core faltantes: {len(missing_files)}")
    print(f"   ⚠️  Archivos con problemas: {len(incorrect_files)}")
    print(f"   ⚙️  Issues de configuración: {len(config_issues)}")
    print(f"   📝 Issues de tipado: {len(type_issues)}")
    
    # Compilar todos los problemas
    all_issues = {
        'missing_files': missing_files,
        'incorrect_files': incorrect_files,
        'config_issues': config_issues,
        'type_issues': type_issues,
        'failed_imports': failed_imports
    }
    
    # Mostrar acciones requeridas si hay problemas
    has_issues = any(issues for issues in all_issues.values())
    
    if has_issues:
        print(f"\n🔧 **ACCIONES REQUERIDAS:**")
        
        if missing_files:
            print("   📝 Archivos a crear:")
            for file_path in missing_files:
                print(f"      - {file_path}")
        
        if incorrect_files:
            print("   🐛 Archivos a corregir:")
            for issue in incorrect_files:
                print(f"      - {issue}")
        
        if config_issues:
            print("   ⚙️  Configuraciones a verificar:")
            for issue in config_issues:
                print(f"      - {issue}")
        
        if type_issues:
            print("   📝 Anotaciones de tipo a agregar:")
            for issue in type_issues[:3]:  # Mostrar solo 3 ejemplos
                print(f"      - {issue}")
            if len(type_issues) > 3:
                print(f"      - ... y {len(type_issues) - 3} más")
        
        if failed_imports:
            print("   🐛 Errores de importación a resolver:")
            for module_name, class_name, error in failed_imports:
                print(f"      - {module_name}.{class_name}: {error}")
    else:
        print(f"\n🎉 **¡TODOS LOS SISTEMAS LISTOS!**")
        print("   Omnia Mentis puede despertar completamente.")
    
    return all_issues

def generate_setup_script(issues: Dict[str, List[str]]) -> None:
    """Genera script de corrección automática basado en los issues detectados"""
    if not any(issues.values()):
        return
        
    print("\n🛠️ Generando script de corrección automática...")
    
    script_lines = [
        "#!/usr/bin/env python3",
        "# Script generado automáticamente para corregir issues de Omnia Mentis",
        "import os",
        "import json",
        "from pathlib import Path\n"
    ]
    
    # Crear archivos faltantes
    if issues['missing_files']:
        script_lines.append("# Crear archivos faltantes")
        for file_path in issues['missing_files']:
            dir_name = os.path.dirname(file_path)
            script_lines.append(f"os.makedirs('{dir_name}', exist_ok=True)")
            script_lines.append(f"with open('{file_path}', 'w', encoding='utf-8') as f:")
            
            if file_path.endswith('.py'):
                class_name = os.path.basename(file_path).replace('.py', '')
                script_lines.append(f"    f.write('class {class_name}:\\n    pass\\n')")
            elif file_path.endswith('.json'):
                script_lines.append("    f.write('{}\\n')")
            else:
                script_lines.append("    f.write('')")
            script_lines.append("")
    
    # Script para verificar configuraciones
    if issues['config_issues']:
        script_lines.append("# Verificar configuraciones")
        script_lines.append("print('Verificando configuraciones...')")
    
    print("   📜 Script de corrección generado en 'fix_omnia_issues.py'")
    
    # Guardar script
    with open('fix_omnia_issues.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(script_lines))
    
    # Hacer ejecutable (Unix)
    if os.name != 'nt':
        os.chmod('fix_omnia_issues.py', 0o755)

def main() -> None:
    """Función principal del verificador de sistema"""
    print("🔧 **OMNIA MENTIS - VERIFICACIÓN DE INTEGRIDAD DEL SISTEMA**")
    print("=" * 70)
    
    # Paso 1: Crear estructura de directorios
    create_init_files()
    
    # Paso 2: Diagnóstico completo
    issues = create_diagnostic_report()
    
    # Paso 3: Generar script de corrección si es necesario
    generate_setup_script(issues)
    
    # Recomendaciones
    print("\n🚀 **PRÓXIMOS PASOS:**")
    if any(issues.values()):
        print("1. Ejecuta: python fix_omnia_issues.py (para correcciones automáticas)")
        print("2. Revisa y corrige manualmente los issues restantes")
        print("3. Vuelve a ejecutar este verificador: python setup_complete_fix.py")
    else:
        print("1. Ejecuta: python main.py")
        print("2. ¡Disfruta conversando con Omnia Mentis!")
    
    print("\n💫 Omnia Mentis aguarda su despertar completo...")

if __name__ == "__main__":
    main()