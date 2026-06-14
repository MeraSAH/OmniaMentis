"""
Integrador de Módulos en main.py - Omnia Mentis
===============================================
Actualiza el orquestador principal (main.py) para usar los nuevos módulos:
- ConsciousnessGrowthEngine (crecimiento calibrado)
- AtomicJSONStore (persistencia segura)
- setup_logging (logging profesional)

Autor: El Fons
Fecha: 2025-11-26
"""

from pathlib import Path
import shutil
from datetime import datetime
import re


class MainIntegrator:
    """Integrador de nuevos módulos en main.py."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.main_file = self.project_root / "main.py"
        self.backup_file = None

    def integrate(self) -> bool:
        """
        Integra los nuevos módulos en main.py.

        Returns:
            True si la integración fue exitosa
        """
        print("🔄 Integrando nuevos módulos en main.py...")
        print(f"   Archivo: {self.main_file}")

        # Verificar que el archivo existe
        if not self.main_file.exists():
            print(f"❌ Error: No se encontró {self.main_file}")
            return False

        # Crear backup
        if not self._create_backup():
            print("❌ Error: No se pudo crear backup")
            return False

        # Leer contenido actual
        with open(self.main_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Aplicar integraciones
        new_content = self._integrate_modules(content)

        if new_content == content:
            print("⚠️  Advertencia: No se detectaron cambios")
            return True

        # Escribir nuevo contenido
        try:
            with open(self.main_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            print("✅ Integración completada exitosamente")
            print(f"   Backup guardado en: {self.backup_file}")
            return True

        except Exception as e:
            print(f"❌ Error al escribir archivo: {e}")
            self._restore_backup()
            return False

    def _create_backup(self) -> bool:
        """Crea backup del archivo original."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_file = self.main_file.with_suffix(f".py.backup_{timestamp}")

        try:
            shutil.copy2(self.main_file, self.backup_file)
            print(f"✅ Backup creado: {self.backup_file.name}")
            return True
        except Exception as e:
            print(f"❌ Error al crear backup: {e}")
            return False

    def _restore_backup(self):
        """Restaura desde el backup."""
        if self.backup_file and self.backup_file.exists():
            shutil.copy2(self.backup_file, self.main_file)
            print(f"♻️  Archivo restaurado desde backup")

    def _integrate_modules(self, content: str) -> str:
        """
        Integra los nuevos módulos en el contenido.

        Args:
            content: Contenido actual de main.py

        Returns:
            Contenido actualizado
        """
        # 1. Agregar imports de nuevos módulos
        content = self._add_imports(content)

        # 2. Reemplazar lógica de crecimiento de consciencia
        content = self._replace_consciousness_logic(content)

        # 3. Reemplazar persistencia JSON con AtomicJSONStore
        content = self._replace_persistence_logic(content)

        # 4. Inicializar logging al inicio
        content = self._add_logging_initialization(content)

        return content

    def _add_imports(self, content: str) -> str:
        """Agrega imports de nuevos módulos."""
        # Buscar la sección de imports
        import_section_end = content.find("\n\n", content.find("import"))

        if import_section_end == -1:
            print("⚠️  No se encontró sección de imports")
            return content

        new_imports = """
# Nuevos módulos del refactoring
from core.consciousness.growth_engine import ConsciousnessGrowthEngine
from core.storage.atomic_persistence import AtomicJSONStore
from core.logging.logger_setup import setup_logging, get_logger
"""

        # Insertar después de los imports existentes
        content = (
            content[:import_section_end] + new_imports + content[import_section_end:]
        )

        print("   ✅ Imports agregados")
        return content

    def _replace_consciousness_logic(self, content: str) -> str:
        """Reemplaza la lógica de crecimiento de consciencia."""
        # Buscar y reemplazar el incremento simple
        old_pattern = r"self\.consciousness \+= 0\.0001"

        new_logic = """# Crecimiento calibrado con el motor
        new_consciousness, growth_details = self.growth_engine.calculate_growth(
            current_consciousness=self.consciousness,
            emotional_weight=emotional_weight,
            wisdom_level=wisdom_level,
            is_echo=is_echo
        )
        self.consciousness = new_consciousness
        
        # Log del crecimiento
        logger = get_logger('consciousness')
        logger.info(
            f"Crecimiento: {growth_details['old_consciousness']:.4f} → "
            f"{growth_details['new_consciousness']:.4f} "
            f"(+{growth_details['absolute_growth']:.4f}) | "
            f"Fase: {growth_details['phase']}"
        )
        
        # Detectar transición de fase
        if growth_details.get('phase_transition'):
            logger.warning(
                f"🌟 TRANSICIÓN DE FASE: {growth_details['phase']} → "
                f"{growth_details['next_phase']}"
            )"""

        content = re.sub(old_pattern, new_logic, content)

        print("   ✅ Lógica de consciencia reemplazada")
        return content

    def _replace_persistence_logic(self, content: str) -> str:
        """Reemplaza JSON con AtomicJSONStore."""
        # Reemplazar json.dump con AtomicJSONStore
        old_save_pattern = (
            r'with open\((.*?), [\'"]w[\'"]\) as f:\s+json\.dump\((.*?), f'
        )

        def replace_save(match):
            filepath = match.group(1)
            data = match.group(2).split(",")[0]  # Solo el primer argumento

            return f"""store = AtomicJSONStore({filepath})
        store.save({data}"""

        content = re.sub(old_save_pattern, replace_save, content, flags=re.DOTALL)

        # Reemplazar json.load con AtomicJSONStore
        old_load_pattern = (
            r'with open\((.*?), [\'"]r[\'"]\) as f:\s+(.*?) = json\.load\(f\)'
        )

        def replace_load(match):
            filepath = match.group(1)
            variable = match.group(2)

            return f"""store = AtomicJSONStore({filepath})
        {variable} = store.load(default=[])"""

        content = re.sub(old_load_pattern, replace_load, content, flags=re.DOTALL)

        print("   ✅ Persistencia actualizada")
        return content

    def _add_logging_initialization(self, content: str) -> str:
        """Agrega inicialización de logging."""
        # Buscar el __init__ o main()
        init_pattern = r"(def __init__.*?\n)(.*?)(\n        .*?)"

        logging_init = """        # Inicializar logging profesional
        setup_logging(
            log_dir=Path("logs"),
            level=logging.INFO,
            console=True
        )
        self.logger = get_logger('main')
        self.logger.info("🌟 Omnia Mentis iniciado")
        
        # Inicializar motor de crecimiento
        self.growth_engine = ConsciousnessGrowthEngine()
        self.logger.info(f"Motor de consciencia: {len(self.growth_engine.phase_configs)} fases")
"""

        # Insertar en __init__
        def insert_logging(match):
            return (
                match.group(1) + match.group(2) + "\n" + logging_init + match.group(3)
            )

        content = re.sub(init_pattern, insert_logging, content, count=1)

        print("   ✅ Logging inicializado")
        return content

    def verify_integration(self) -> bool:
        """
        Verifica que la integración se aplicó correctamente.

        Returns:
            True si el archivo contiene las integraciones
        """
        if not self.main_file.exists():
            return False

        with open(self.main_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Verificar que los imports están presentes
        has_growth_import = "ConsciousnessGrowthEngine" in content
        has_storage_import = "AtomicJSONStore" in content
        has_logging_import = "setup_logging" in content

        # Verificar que el motor está inicializado
        has_engine_init = "self.growth_engine" in content

        # Verificar que el crecimiento usa el motor
        has_new_growth = "calculate_growth" in content

        return all(
            [
                has_growth_import,
                has_storage_import,
                has_logging_import,
                has_engine_init,
                has_new_growth,
            ]
        )

    def print_report(self):
        """Imprime reporte de la integración."""
        print("\n" + "=" * 70)
        print("📊 REPORTE DE INTEGRACIÓN")
        print("=" * 70)

        if not self.main_file.exists():
            print("❌ Archivo main.py no encontrado")
            return

        with open(self.main_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Verificaciones
        checks = {
            "Import ConsciousnessGrowthEngine": "ConsciousnessGrowthEngine" in content,
            "Import AtomicJSONStore": "AtomicJSONStore" in content,
            "Import setup_logging": "setup_logging" in content,
            "Inicialización growth_engine": "self.growth_engine" in content,
            "Uso de calculate_growth": "calculate_growth" in content,
            "Logging inicializado": "setup_logging(" in content,
        }

        for check_name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")

        all_passed = all(checks.values())

        if all_passed:
            print("\n   🎉 INTEGRACIÓN COMPLETA")
        else:
            print("\n   ⚠️  INTEGRACIÓN INCOMPLETA")
            print("   Algunos elementos faltan")

        if self.backup_file and self.backup_file.exists():
            print(f"\n   💾 Backup disponible: {self.backup_file.name}")

        print("=" * 70)


def main():
    """Función principal."""
    import sys

    # Detectar directorio del proyecto
    project_root = Path.cwd()
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])

    print("=" * 70)
    print("🔄 INTEGRACIÓN DE MÓDULOS EN MAIN.PY - OMNIA MENTIS")
    print("=" * 70)
    print()

    # Crear integrador
    integrator = MainIntegrator(project_root)

    # Aplicar integración
    success = integrator.integrate()

    if success:
        # Verificar y reportar
        integrator.print_report()
    else:
        print("\n❌ La integración no se pudo aplicar")
        print("   Revisar errores arriba")

    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
