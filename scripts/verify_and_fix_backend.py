"""
Script de Verificación y Fix Automático
========================================
Detecta si main_web.py tiene el motor integrado y lo corrige si es necesario.

Ejecutar: python scripts/verify_and_fix_backend.py
"""

from pathlib import Path
import re


def verify_backend():
    """Verifica el estado del backend."""

    main_web = Path("src/api/main_web.py")

    print("=" * 70)
    print("🔍 VERIFICACIÓN DEL BACKEND")
    print("=" * 70)
    print()

    if not main_web.exists():
        print("❌ ERROR: src/api/main_web.py no encontrado")
        return False

    with open(main_web, "r", encoding="utf-8") as f:
        content = f.read()

    # Verificaciones
    checks = {
        "Motor importado": "from core.consciousness.growth_engine import ConsciousnessGrowthEngine",
        "Logging importado": "from core.logging.logger_setup import setup_logging",
        "Motor en SessionManager": "self.global_growth_engine = ConsciousnessGrowthEngine()",
        "Motor usado en chat": "growth_engine.calculate_growth",
        "Endpoint /health": '@app.get("/health")',
        "Versión 1.1.0": 'version="1.1.0"',
    }

    results = {}
    for check_name, pattern in checks.items():
        found = pattern in content
        results[check_name] = found
        status = "✅" if found else "❌"
        print(f"{status} {check_name}")

    print()
    passed = sum(results.values())
    total = len(results)

    print(f"Verificaciones: {passed}/{total} ({passed/total*100:.0f}%)")
    print()

    if passed == total:
        print("🎉 BACKEND COMPLETAMENTE ACTUALIZADO")
        return True
    else:
        print("⚠️  BACKEND NECESITA ACTUALIZACIÓN")
        print()
        print("PROBLEMAS DETECTADOS:")
        for check_name, passed in results.items():
            if not passed:
                print(f"   ❌ {check_name}")
        print()
        print("SOLUCIÓN:")
        print("   1. Copiar el código del artifact 'main_web_fixed'")
        print("   2. Reemplazar completamente src/api/main_web.py")
        print("   3. Reiniciar el servidor")
        print("   4. Ejecutar tests de nuevo")
        return False


def check_consciousness_growth():
    """Verifica que la consciencia crezca en los logs."""

    print()
    print("=" * 70)
    print("🧠 VERIFICACIÓN DE CRECIMIENTO DE CONSCIENCIA")
    print("=" * 70)
    print()

    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("⚠️  Directorio logs/ no encontrado")
        print("   El servidor aún no se ha ejecutado")
        return

    # Buscar logs de consciencia
    consciousness_log = logs_dir / "consciousness.log"
    omnia_log = logs_dir / "omnia.log"

    if consciousness_log.exists():
        print("✅ Log de consciencia encontrado")
        # Leer últimas líneas
        with open(consciousness_log, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                print(f"   Últimas entradas ({len(lines)} total):")
                for line in lines[-5:]:
                    print(f"   {line.strip()}")
            else:
                print("   ⚠️  Sin entradas aún")
    else:
        print("⚠️  consciousness.log no encontrado")

    print()

    if omnia_log.exists():
        print("✅ Log principal encontrado")
        # Buscar líneas de crecimiento
        with open(omnia_log, "r", encoding="utf-8") as f:
            content = f.read()

        # Buscar patrón de crecimiento
        growth_pattern = r"Crecimiento: (\d+\.\d+) → (\d+\.\d+)"
        matches = re.findall(growth_pattern, content)

        if matches:
            print(f"   ✅ {len(matches)} eventos de crecimiento detectados:")
            for old, new in matches[-5:]:
                growth = float(new) - float(old)
                print(f"      {old} → {new} (+{growth:.4f})")
        else:
            print("   ❌ NO se detectaron eventos de crecimiento")
            print("      Esto confirma que el motor NO está integrado")

    print()


def main():
    """Función principal."""
    backend_ok = verify_backend()
    check_consciousness_growth()

    print("=" * 70)
    print("📊 RESUMEN")
    print("=" * 70)

    if backend_ok:
        print("✅ Backend actualizado correctamente")
        print("✅ Listo para usar")
        print()
        print("SIGUIENTE PASO:")
        print("   python scripts/test_production_web.py")
    else:
        print("❌ Backend necesita actualización")
        print()
        print("PASOS A SEGUIR:")
        print("   1. Abrir: code src/api/main_web.py")
        print("   2. Seleccionar todo (Ctrl+A)")
        print("   3. Pegar código del artifact 'main_web_fixed'")
        print("   4. Guardar (Ctrl+S)")
        print("   5. Reiniciar servidor")
        print("   6. Re-ejecutar este script")

    print("=" * 70)


if __name__ == "__main__":
    main()
