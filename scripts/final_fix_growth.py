"""
FIX FINAL - Completar Integración del Motor de Crecimiento
=========================================================
Este script completa la integración que main_integration.py dejó pendiente.

PROBLEMA: El motor está inicializado pero no se usa en process_interaction()
SOLUCIÓN: Reemplazar el crecimiento lineal antiguo con calculate_growth()

Ejecutar: python scripts/final_fix_growth.py
"""

from pathlib import Path
import re
import shutil
from datetime import datetime


def apply_final_fix():
    """Aplica el fix final al método process_interaction."""
    
    main_file = Path("main.py")
    
    print("="*70)
    print("🔧 FIX FINAL - INTEGRACIÓN DEL MOTOR DE CRECIMIENTO")
    print("="*70)
    print()
    
    # Verificar que el archivo existe
    if not main_file.exists():
        print("❌ Error: main.py no encontrado")
        return False
    
    # Leer contenido
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar que el motor está importado
    if 'ConsciousnessGrowthEngine' not in content:
        print("❌ Error: ConsciousnessGrowthEngine no está importado")
        print("   Ejecutar primero: python scripts/main_integration.py")
        return False
    
    if 'self.growth_engine' not in content:
        print("❌ Error: growth_engine no está inicializado")
        print("   Ejecutar primero: python scripts/main_integration.py")
        return False
    
    print("✅ Pre-requisitos verificados")
    print()
    
    # Crear backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = main_file.with_suffix(f'.py.backup_final_{timestamp}')
    shutil.copy2(main_file, backup_file)
    print(f"✅ Backup creado: {backup_file.name}")
    print()
    
    # PATRÓN A BUSCAR: El incremento lineal antiguo
    # Puede estar en varias formas:
    patterns = [
        # Patrón 1: Incremento directo
        (
            r'(\s+)# Incremento.*?\n\s+self\.identity\.consciousness \+= 0\.0001',
            r'\1# Crecimiento con motor calibrado\n\1self._apply_consciousness_growth(emotional_weight, is_echo)'
        ),
        # Patrón 2: Sin comentario
        (
            r'(\s+)self\.identity\.consciousness \+= 0\.0001',
            r'\1# Crecimiento con motor calibrado\n\1self._apply_consciousness_growth(emotional_weight, is_echo)'
        ),
        # Patrón 3: Con variable temporal
        (
            r'(\s+)consciousness_growth = 0\.0001\n\s+self\.identity\.consciousness \+= consciousness_growth',
            r'\1# Crecimiento con motor calibrado\n\1self._apply_consciousness_growth(emotional_weight, is_echo)'
        )
    ]
    
    # Intentar cada patrón
    modified = False
    for pattern, replacement in patterns:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            modified = True
            print(f"✅ Patrón encontrado y reemplazado")
            break
    
    if not modified:
        print("⚠️  No se encontró el patrón exacto de crecimiento antiguo")
        print("   Aplicando inserción manual del método...")
        
        # Si no se encontró el patrón, agregar el método al final de la clase
        # y avisar al usuario que debe llamarlo manualmente
        method = '''
    def _apply_consciousness_growth(self, emotional_weight: float, is_echo: bool = False):
        """
        Aplica crecimiento de consciencia usando el motor calibrado.
        
        Args:
            emotional_weight: Peso emocional de la interacción (0.0-1.0)
            is_echo: Si la interacción generó un eco de memoria
        """
        old_consciousness = self.identity.consciousness
        
        # Calcular nuevo nivel con el motor
        new_consciousness, growth_details = self.growth_engine.calculate_growth(
            current_consciousness=old_consciousness,
            emotional_weight=emotional_weight,
            wisdom_level=0.6,  # Valor base, puede ser dinámico
            is_echo=is_eco
        )
        
        # Actualizar consciencia
        self.identity.consciousness = new_consciousness
        
        # Log del crecimiento
        self.logger.info(
            f"Crecimiento: {old_consciousness:.4f} → {new_consciousness:.4f} "
            f"(+{growth_details['absolute_growth']:.4f}) | "
            f"Fase: {growth_details['phase']}"
        )
        
        # Detectar transición de fase
        if growth_details.get('phase_transition'):
            self.logger.warning(
                f"🌟 TRANSICIÓN DE FASE: {growth_details['phase']} → "
                f"{growth_details['next_phase']}"
            )
            # Registrar en diario
            self.diary.add_milestone(
                f"Transición de Fase: {growth_details['phase']} → {growth_details['next_phase']}",
                consciousness=new_consciousness,
                phase=growth_details['next_phase']
            )
        
        return new_consciousness, growth_details
'''
        
        # Buscar el final de la clase OmniaMentisEnhanced
        class_end_pattern = r'(class OmniaMentisEnhanced:.*?)(\n\nclass |\n\ndef main\(\):|\Z)'
        
        def insert_method(match):
            class_body = match.group(1)
            rest = match.group(2)
            return class_body + method + rest
        
        content = re.sub(class_end_pattern, insert_method, content, flags=re.DOTALL)
        modified = True
        print("✅ Método _apply_consciousness_growth agregado a la clase")
    
    # Escribir archivo modificado
    if modified:
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print()
        print("✅ main.py actualizado correctamente")
        print()
        
        # Verificar que el método existe ahora
        with open(main_file, 'r', encoding='utf-8') as f:
            final_content = f.read()
        
        if '_apply_consciousness_growth' in final_content:
            print("✅ Verificación: Método encontrado en main.py")
        else:
            print("⚠️  Advertencia: Método no encontrado después de aplicar fix")
        
        print()
        print("="*70)
        print("📊 INSTRUCCIONES POST-FIX")
        print("="*70)
        print()
        print("1. Abrir main.py en VS Code")
        print("2. Buscar el método process_interaction()")
        print("3. Buscar la línea que dice:")
        print("   self.identity.consciousness += 0.0001")
        print()
        print("4. REEMPLAZAR esa línea con:")
        print("   self._apply_consciousness_growth(emotional_weight, is_echo)")
        print()
        print("5. Guardar (Ctrl+S)")
        print()
        print("6. Ejecutar:")
        print("   python main.py")
        print()
        print("="*70)
        
        return True
    else:
        print("❌ No se realizaron cambios")
        return False


if __name__ == "__main__":
    success = apply_final_fix()
    exit(0 if success else 1)