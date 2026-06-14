"""
Script de Fix para Ethics System - Omnia Mentis
===============================================
Aplica corrección al bug de la línea 437 en ethics.py

Bug Original:
    if c.get('fons_decision', {}).get('approved', False)
    
Problema: fons_decision puede ser None, causando TypeError

Fix: Método seguro de extracción con validación de tipo

Autor: El Fons
Fecha: 2025-11-26
"""

from pathlib import Path
import shutil
from datetime import datetime
import re


class EthicsFixer:
    """Aplicador de fix para el bug de ethics.py."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.ethics_file = self.project_root / 'src' / 'core' / 'essence' / 'ethics.py'
        self.backup_file = None
    
    def apply_fix(self) -> bool:
        """
        Aplica el fix al archivo ethics.py.
        
        Returns:
            True si el fix se aplicó exitosamente
        """
        print("🔧 Aplicando fix al sistema ético...")
        print(f"   Archivo: {self.ethics_file}")
        
        # Verificar que el archivo existe
        if not self.ethics_file.exists():
            print(f"❌ Error: No se encontró {self.ethics_file}")
            return False
        
        # Crear backup
        if not self._create_backup():
            print("❌ Error: No se pudo crear backup")
            return False
        
        # Leer contenido actual
        with open(self.ethics_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Aplicar fix
        new_content = self._apply_fix_to_content(content)
        
        if new_content == content:
            print("⚠️  Advertencia: No se detectaron cambios (¿ya está corregido?)")
            return True
        
        # Escribir nuevo contenido
        try:
            with open(self.ethics_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("✅ Fix aplicado exitosamente")
            print(f"   Backup guardado en: {self.backup_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error al escribir archivo: {e}")
            # Restaurar backup
            self._restore_backup()
            return False
    
    def _create_backup(self) -> bool:
        """Crea backup del archivo original."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_file = self.ethics_file.with_suffix(f'.py.backup_{timestamp}')
        
        try:
            shutil.copy2(self.ethics_file, self.backup_file)
            print(f"✅ Backup creado: {self.backup_file.name}")
            return True
        except Exception as e:
            print(f"❌ Error al crear backup: {e}")
            return False
    
    def _restore_backup(self):
        """Restaura desde el backup."""
        if self.backup_file and self.backup_file.exists():
            shutil.copy2(self.backup_file, self.ethics_file)
            print(f"♻️  Archivo restaurado desde backup")
    
    def _apply_fix_to_content(self, content: str) -> str:
        """
        Aplica el fix al contenido del archivo.
        
        Args:
            content: Contenido actual del archivo
        
        Returns:
            Contenido con el fix aplicado
        """
        # Método seguro a agregar
        safe_method = '''    def _get_fons_approval_safe(self, consultation: dict) -> bool:
        """
        Extrae aprobación del Fons de forma segura.
        
        Schema esperado:
        {
            'fons_decision': {
                'approved': bool,
                'operator': str,
                'timestamp': str
            }
        }
        
        Args:
            consultation: Diccionario de consulta al Fons
        
        Returns:
            True si aprobado, False en caso contrario
        """
        fons_decision = consultation.get('fons_decision')
        
        # Validación de tipo
        if not isinstance(fons_decision, dict):
            self.logger.warning(
                f"fons_decision inválido (tipo {type(fons_decision).__name__})"
            )
            return False
        
        # Validación de schema
        if 'approved' not in fons_decision:
            self.logger.warning(
                f"fons_decision sin campo 'approved': {list(fons_decision.keys())}"
            )
            return False
        
        return bool(fons_decision['approved'])
'''
        
        # Buscar la clase OmniaEthics
        class_pattern = r'class OmniaEthics.*?:'
        class_match = re.search(class_pattern, content)
        
        if not class_match:
            print("⚠️  No se encontró la clase OmniaEthics")
            return content
        
        # Insertar el método después del __init__
        init_pattern = r'(def __init__.*?\n(?:.*?\n)*?        self\.logger.*?\n)'
        
        def insert_method(match):
            return match.group(1) + '\n' + safe_method + '\n'
        
        new_content = re.sub(init_pattern, insert_method, content, count=1)
        
        # Reemplazar las líneas problemáticas
        # Patrón: if c.get('fons_decision', {}).get('approved', False)
        buggy_pattern = r"if c\.get\('fons_decision', \{\}\)\.get\('approved', False\)"
        fixed_line = "if self._get_fons_approval_safe(c)"
        
        new_content = re.sub(buggy_pattern, fixed_line, new_content)
        
        # Buscar otras variantes del bug
        buggy_pattern2 = r"if consultation\.get\('fons_decision', \{\}\)\.get\('approved'\)"
        fixed_line2 = "if self._get_fons_approval_safe(consultation)"
        
        new_content = re.sub(buggy_pattern2, fixed_line2, new_content)
        
        return new_content
    
    def verify_fix(self) -> bool:
        """
        Verifica que el fix se aplicó correctamente.
        
        Returns:
            True si el archivo contiene el fix
        """
        if not self.ethics_file.exists():
            return False
        
        with open(self.ethics_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar que el método existe
        has_method = '_get_fons_approval_safe' in content
        
        # Verificar que no quedan líneas bugueadas
        has_bug = "c.get('fons_decision', {}).get('approved', False)" in content
        
        return has_method and not has_bug
    
    def print_report(self):
        """Imprime reporte del estado del fix."""
        print("\n" + "="*70)
        print("📊 REPORTE DEL FIX DE ETHICS")
        print("="*70)
        
        if self.verify_fix():
            print("✅ Fix aplicado correctamente")
            print("   - Método _get_fons_approval_safe: PRESENTE")
            print("   - Líneas bugueadas: NO ENCONTRADAS")
        else:
            print("⚠️  Fix no detectado o incompleto")
            print("   Verificar manualmente el archivo")
        
        if self.backup_file and self.backup_file.exists():
            print(f"\n   💾 Backup disponible: {self.backup_file.name}")
        
        print("="*70)


def main():
    """Función principal."""
    import sys
    
    # Detectar directorio del proyecto
    project_root = Path.cwd()
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1])
    
    print("="*70)
    print("🔧 FIX DEL SISTEMA ÉTICO - OMNIA MENTIS")
    print("="*70)
    print()
    
    # Crear fixer
    fixer = EthicsFixer(project_root)
    
    # Aplicar fix
    success = fixer.apply_fix()
    
    if success:
        # Verificar
        fixer.print_report()
    else:
        print("\n❌ El fix no se pudo aplicar")
        print("   Revisar errores arriba")
    
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)