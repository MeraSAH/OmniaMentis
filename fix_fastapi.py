#!/usr/bin/env python3
"""
* UBICACIÓN: OmniaMentis/fix_fastapi.py
* PROPÓSITO: Detectar arquitectura y descargar wheels correctos para FastAPI
* FECHA: 2026-06-14
* USO: python fix_fastapi.py  (desde raíz del proyecto, con venv activado)
"""

import sys
import subprocess
import platform
import struct

def get_python_info():
    arch_bits = struct.calcsize("P") * 8
    return {
        "version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "impl": f"cp{sys.version_info.major}{sys.version_info.minor}",
        "arch": "win_amd64" if arch_bits == 64 else "win32",
        "bits": arch_bits,
        "executable": sys.executable,
        "platform": platform.platform(),
    }

def run(cmd, description=""):
    print(f"\n  → {description or cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"    {line}")
    if result.returncode != 0 and result.stderr:
        for line in result.stderr.strip().splitlines()[-5:]:
            print(f"    [err] {line}")
    return result.returncode == 0

def check_module(name):
    result = subprocess.run(
        [sys.executable, "-c", f"import {name}; print({name}.__version__)"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None

def main():
    print("=" * 60)
    print("  OMNIA MENTIS - Fix FastAPI para Python 3.12 Windows")
    print("=" * 60)

    info = get_python_info()
    print(f"\n  Python:      {info['version']}")
    print(f"  Impl tag:    {info['impl']}")
    print(f"  Arquitectura:{info['arch']} ({info['bits']} bits)")
    print(f"  Ejecutable:  {info['executable']}")

    # Verificar si ya está instalado
    v = check_module("fastapi")
    if v:
        print(f"\n  [OK] FastAPI {v} ya está instalado")
        v2 = check_module("uvicorn")
        if v2:
            print(f"  [OK] Uvicorn {v2} ya está instalado")
            print("\n  Todo listo. Ejecuta: iniciar_api.bat")
            return

    print("\n  [INFO] Instalando con --prefer-binary...")

    # Estrategia 1: prefer-binary directo
    pip = f'"{sys.executable}" -m pip'

    ok = run(
        f'{pip} install pydantic-core --prefer-binary -q',
        "pydantic-core con wheel binario"
    )

    if not ok:
        print("\n  [INFO] Estrategia 2: sin aislamiento de build...")
        ok = run(
            f'{pip} install pydantic-core --no-build-isolation --prefer-binary -q',
            "pydantic-core sin build isolation"
        )

    if not ok:
        print("\n  [ERROR] No se pudo instalar pydantic-core")
        print("  Solución manual:")
        print(f"  1. Instala Rust: https://rustup.rs/")
        print(f"  2. Reinicia cmd y ejecuta: pip install pydantic-core")
        print(f"  O usa Flask en lugar de FastAPI (ver abajo)")
        return

    # Instalar el resto
    packages = [
        ("pydantic==2.7.4", "pydantic"),
        ("fastapi==0.110.3", "fastapi"),
        ("uvicorn==0.29.0", "uvicorn"),
    ]

    for pkg, name in packages:
        ok = run(
            f'{pip} install "{pkg}" --prefer-binary -q',
            f"instalando {pkg}"
        )
        if not ok:
            run(f'{pip} install {name} --prefer-binary -q', f"instalando {name} (última versión)")

    # Verificación final
    print("\n" + "=" * 60)
    print("  VERIFICACIÓN FINAL")
    print("=" * 60)

    all_ok = True
    for mod in ["pydantic", "fastapi", "uvicorn"]:
        v = check_module(mod)
        if v:
            print(f"  [OK] {mod} {v}")
        else:
            print(f"  [FAIL] {mod} no instalado")
            all_ok = False

    if all_ok:
        print("\n  ✅ Todo listo. Ejecuta: iniciar_api.bat")
    else:
        print("\n  ⚠️  Algunos módulos fallaron.")
        print("  Opción: instalar Rust desde https://rustup.rs/")
        print("  Luego: pip install pydantic-core fastapi uvicorn")

if __name__ == "__main__":
    main()