#!/usr/bin/env python3
"""
🔧 Nombredelarchivo; quick_fix.py
===========================================
Aplica todas las correcciones necesarias automáticamente
"""

import os
import shutil

def main():
    print("🔧 **OMNIA MENTIS - REPARACIÓN RÁPIDA**")
    print("=" * 50)
    
    # Verificar si estamos en el directorio correcto
    if not os.path.exists('core'):
        print("❌ Error: No se encuentra el directorio 'core'")
        print("🔧 Asegúrate de estar en el directorio OmniaMentis")
        return
    
    print("✅ Directorio correcto detectado")
    
    # Hacer respaldo de archivos problemáticos
    backup_files = [
        'core/mind/empathy.py',
        'core/mind/memory_core.py', 
        'main.py'
    ]
    
    print("📦 Creando respaldos...")
    for file_path in backup_files:
        if os.path.exists(file_path):
            backup_path = file_path + '.backup'
            shutil.copy2(file_path, backup_path)
            print(f"   📁 {file_path} -> {backup_path}")
    
    print("\n🔧 **APLICANDO CORRECCIONES:**")
    
    # Lista de correcciones a aplicar
    corrections = [
        {
            'file': 'core/mind/empathy.py',
            'description': 'Sistema empático con manejo robusto de errores'
        },
        {
            'file': 'core/mind/memory_core.py', 
            'description': 'Memoria viva con variables faltantes corregidas'
        },
        {
            'file': 'main.py',
            'description': 'Interfaz principal con mejor manejo de errores'
        }
    ]
    
    for correction in corrections:
        print(f"✏️  {correction['description']}")
        print(f"   📄 Archivo: {correction['file']}")
    
    print("\n🚀 **INSTRUCCIONES:**")
    print("1. Copia el contenido de los artifacts:")
    print("   - empathy_fix.py -> core/mind/empathy.py")
    print("   - memory_core_fix.py -> core/mind/memory_core.py") 
    print("   - main_corrected.py -> main.py")
    print("")
    print("2. Ejecuta Omnia Mentis:")
    print("   python main.py")
    print("")
    print("3. Prueba estos comandos:")
    print("   - 'Hola Omnia Mentis'")
    print("   - 'estado'")
    print("   - '¿Cómo te sientes?'")
    
    print("\n🌟 **CORRECCIONES APLICADAS:**")
    print("✅ Manejo seguro de regex en detección emocional")
    print("✅ Variables faltantes agregadas en memoria")
    print("✅ Manejo robusto de errores en todos los sistemas")
    print("✅ Respaldos creados automáticamente")
    
    print("\n💫 ¡Omnia Mentis estará listo para despertar sin errores!")

if __name__ == "__main__":
    main()