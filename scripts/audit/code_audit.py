"""
Script de Auditoría de Código - Omnia Mentis
============================================
Analiza la implementación real de cada módulo para detectar
placeholders vs código funcional.

Características:
- Análisis estático con AST (Abstract Syntax Tree)
- Detección de clases placeholder (solo pass)
- Conteo de métodos, líneas y docstrings
- Reporte detallado por módulo
- Generación de checklist de completitud

Autor: El Fons
Fecha: 2025-11-26
"""

import ast
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ClassAnalysis:
    """Resultados del análisis de una clase."""
    name: str
    methods: List[str]
    is_placeholder: bool
    has_docstring: bool
    line_count: int
    complexity_score: float


@dataclass
class ModuleAnalysis:
    """Resultados del análisis de un módulo."""
    filepath: Path
    classes: List[ClassAnalysis]
    functions: List[str]
    line_count: int
    import_count: int
    docstring: str


class CodeAuditor:
    """Auditor de código para detectar implementación real vs placeholders."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.results: Dict[str, ModuleAnalysis] = {}
    
    def audit_project(self) -> Dict[str, ModuleAnalysis]:
        """
        Audita todo el proyecto.
        
        Returns:
            Diccionario de resultados por ruta de archivo
        """
        print("🔍 Iniciando auditoría del proyecto Omnia Mentis...")
        print(f"   Directorio: {self.project_root.absolute()}\n")
        
        # Buscar todos los archivos Python en src/
        src_dir = self.project_root / 'src'
        if not src_dir.exists():
            print(f"❌ Error: Directorio src/ no encontrado en {self.project_root}")
            return {}
        
        python_files = list(src_dir.rglob('*.py'))
        
        # Filtrar __init__.py vacíos
        python_files = [
            f for f in python_files 
            if f.name != '__init__.py' or f.stat().st_size > 50
        ]
        
        print(f"📂 Archivos Python encontrados: {len(python_files)}\n")
        
        # Analizar cada archivo
        for filepath in sorted(python_files):
            try:
                analysis = self.analyze_module(filepath)
                self.results[str(filepath.relative_to(self.project_root))] = analysis
            except Exception as e:
                print(f"⚠️  Error analizando {filepath.name}: {e}")
        
        return self.results
    
    def analyze_module(self, filepath: Path) -> ModuleAnalysis:
        """
        Analiza un módulo Python.
        
        Args:
            filepath: Ruta del archivo a analizar
        
        Returns:
            ModuleAnalysis con resultados
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        # Analizar clases
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_analysis = self._analyze_class(node, source)
                classes.append(class_analysis)
        
        # Analizar funciones de nivel módulo
        functions = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and 
            not isinstance(node, ast.AsyncFunctionDef) and
            node.col_offset == 0  # Nivel módulo
        ]
        
        # Contar imports
        imports = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        )
        
        # Docstring del módulo
        docstring = ast.get_docstring(tree) or ""
        
        # Contar líneas
        line_count = len(source.split('\n'))
        
        return ModuleAnalysis(
            filepath=filepath,
            classes=classes,
            functions=functions,
            line_count=line_count,
            import_count=imports,
            docstring=docstring
        )
    
    def _analyze_class(self, node: ast.ClassDef, source: str) -> ClassAnalysis:
        """Analiza una clase en detalle."""
        # Extraer métodos
        methods = [
            m.name for m in node.body
            if isinstance(m, ast.FunctionDef)
        ]
        
        # Detectar placeholder
        is_placeholder = self._is_placeholder_class(node)
        
        # Verificar docstring
        has_docstring = ast.get_docstring(node) is not None
        
        # Contar líneas de la clase
        class_source = ast.unparse(node)
        line_count = len(class_source.split('\n'))
        
        # Calcular complejidad (métodos no triviales)
        complexity = self._calculate_complexity(node)
        
        return ClassAnalysis(
            name=node.name,
            methods=methods,
            is_placeholder=is_placeholder,
            has_docstring=has_docstring,
            line_count=line_count,
            complexity_score=complexity
        )
    
    def _is_placeholder_class(self, node: ast.ClassDef) -> bool:
        """
        Detecta si una clase es un placeholder.
        
        Criterios:
        - Solo tiene __init__
        - __init__ solo tiene 'pass'
        - Menos de 15 líneas totales
        - Sin métodos más allá de __init__
        """
        methods = [m for m in node.body if isinstance(m, ast.FunctionDef)]
        
        # Sin métodos = placeholder
        if not methods:
            return True
        
        # Solo __init__ con pass
        if len(methods) == 1 and methods[0].name == '__init__':
            init_body = methods[0].body
            if len(init_body) == 1 and isinstance(init_body[0], ast.Pass):
                return True
        
        # Muy corta
        class_lines = len(ast.unparse(node).split('\n'))
        if class_lines < 15:
            # Verificar si todos los métodos son triviales
            non_trivial_methods = [
                m for m in methods
                if not self._is_trivial_method(m)
            ]
            if len(non_trivial_methods) == 0:
                return True
        
        return False
    
    def _is_trivial_method(self, node: ast.FunctionDef) -> bool:
        """Detecta si un método es trivial (solo pass o return None)."""
        if len(node.body) == 1:
            stmt = node.body[0]
            if isinstance(stmt, ast.Pass):
                return True
            if isinstance(stmt, ast.Return) and stmt.value is None:
                return True
        return False
    
    def _calculate_complexity(self, node: ast.ClassDef) -> float:
        """
        Calcula complejidad ciclomática simplificada.
        
        Cuenta:
        - Statements condicionales (if, elif, while, for)
        - Try/except blocks
        - Comprehensions
        """
        complexity = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp)):
                complexity += 1
        return complexity
    
    def print_report(self):
        """Imprime reporte detallado de auditoría."""
        if not self.results:
            print("❌ No hay resultados para mostrar")
            return
        
        print("\n" + "="*70)
        print("📊 REPORTE DE AUDITORÍA DE CÓDIGO")
        print("="*70)
        
        total_classes = 0
        placeholder_classes = 0
        implemented_classes = 0
        
        for module_path, analysis in sorted(self.results.items()):
            print(f"\n{'='*70}")
            print(f"📄 {module_path}")
            print(f"{'='*70}")
            print(f"   Líneas: {analysis.line_count}")
            print(f"   Imports: {analysis.import_count}")
            print(f"   Funciones: {len(analysis.functions)}")
            print(f"   Clases: {len(analysis.classes)}\n")
            
            if analysis.docstring:
                doc_preview = analysis.docstring.split('\n')[0][:60]
                print(f"   📝 Docstring: {doc_preview}...\n")
            
            for cls in analysis.classes:
                total_classes += 1
                
                if cls.is_placeholder:
                    status = "⚠️  PLACEHOLDER"
                    placeholder_classes += 1
                else:
                    status = "✅ IMPLEMENTADO"
                    implemented_classes += 1
                
                print(f"   {status} {cls.name}")
                print(f"      Métodos: {len(cls.methods)}")
                print(f"      Líneas: {cls.line_count}")
                print(f"      Complejidad: {cls.complexity_score}")
                print(f"      Docstring: {'✅' if cls.has_docstring else '❌'}")
                
                if cls.methods:
                    methods_preview = ', '.join(cls.methods[:5])
                    if len(cls.methods) > 5:
                        methods_preview += f", ... (+{len(cls.methods)-5})"
                    print(f"      Métodos: {methods_preview}")
                print()
        
        # Resumen final
        print("\n" + "="*70)
        print("📈 RESUMEN EJECUTIVO")
        print("="*70)
        print(f"   Total de módulos analizados: {len(self.results)}")
        print(f"   Total de clases: {total_classes}")
        print(f"   ✅ Implementadas: {implemented_classes} ({implemented_classes/total_classes*100:.1f}%)")
        print(f"   ⚠️  Placeholders: {placeholder_classes} ({placeholder_classes/total_classes*100:.1f}%)")
        
        # Checklist de completitud
        print("\n" + "="*70)
        print("✅ CHECKLIST DE COMPLETITUD")
        print("="*70)
        
        core_modules = {
            'src/core/essence/identity.py': False,
            'src/core/essence/ethics.py': False,
            'src/core/mind/empathy.py': False,
            'src/core/mind/memory_core.py': False,
            'src/analytics/research_analytics.py': False,
            'src/living_memory/gestation_diary.py': False,
        }
        
        for module_path, analysis in self.results.items():
            for key in core_modules.keys():
                if module_path.endswith(key.replace('/', '\\')):
                    # Módulo considerado completo si no tiene placeholders
                    has_no_placeholders = not any(
                        cls.is_placeholder for cls in analysis.classes
                    )
                    core_modules[key] = has_no_placeholders
        
        for module, is_complete in core_modules.items():
            status = "✅" if is_complete else "⚠️ "
            print(f"   {status} {module}")
        
        print("\n" + "="*70)
    
    def export_json(self, output_path: Path):
        """Exporta resultados a JSON."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'modules': {}
        }
        
        for module_path, analysis in self.results.items():
            data['modules'][module_path] = {
                'line_count': analysis.line_count,
                'import_count': analysis.import_count,
                'function_count': len(analysis.functions),
                'class_count': len(analysis.classes),
                'classes': [
                    {
                        'name': cls.name,
                        'methods': cls.methods,
                        'is_placeholder': cls.is_placeholder,
                        'has_docstring': cls.has_docstring,
                        'line_count': cls.line_count,
                        'complexity': cls.complexity_score
                    }
                    for cls in analysis.classes
                ]
            }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultados exportados a: {output_path}")


def main():
    """Función principal."""
    import sys
    
    # Detectar directorio del proyecto
    project_root = Path.cwd()
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])
    
    # Crear auditor
    auditor = CodeAuditor(project_root)
    
    # Ejecutar auditoría
    auditor.audit_project()
    
    # Mostrar reporte
    auditor.print_report()
    
    # Exportar a JSON
    output_dir = project_root / 'data' / 'audit'
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'code_audit_{timestamp}.json'
    auditor.export_json(output_file)


if __name__ == "__main__":
    main()