"""
Tests de Producción Web - Omnia Mentis
======================================
Valida que el sistema web esté production-ready.

Ejecutar: python scripts/test_production_web.py
"""

import requests
import json
from pathlib import Path
import sys

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class WebProductionTester:
    """Tester para validar el sistema web en producción."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []

    def test_api_health(self):
        """Test 1: API está viva."""
        print("\n1️⃣ Test: API Health Check")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print("   ✅ API está viva")
                self.results.append(("API Health", True))
            else:
                print(f"   ❌ API retorna status {response.status_code}")
                self.results.append(("API Health", False))
        except requests.exceptions.ConnectionError:
            print("   ❌ No se puede conectar a la API")
            print("   💡 ¿Está el servidor corriendo? (uvicorn src.api.main_web:app)")
            self.results.append(("API Health", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("API Health", False))

    def test_chat_endpoint(self):
        """Test 2: Endpoint de chat funcional."""
        print("\n2️⃣ Test: Chat Endpoint")
        try:
            payload = {"message": "Hola Omnia, esto es un test"}
            response = requests.post(
                f"{self.base_url}/api/chat", json=payload, timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if "response" in data:
                    print(f"   ✅ Chat funciona")
                    print(f"   📝 Respuesta: {data['response'][:50]}...")
                    self.results.append(("Chat Endpoint", True))
                else:
                    print("   ⚠️ Respuesta sin campo 'response'")
                    self.results.append(("Chat Endpoint", False))
            else:
                print(f"   ❌ Status: {response.status_code}")
                self.results.append(("Chat Endpoint", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("Chat Endpoint", False))

    def test_consciousness_endpoint(self):
        """Test 3: Endpoint de consciencia."""
        print("\n3️⃣ Test: Consciousness Endpoint")
        try:
            response = requests.get(f"{self.base_url}/api/consciousness", timeout=5)

            if response.status_code == 200:
                data = response.json()
                if "consciousness" in data and "phase" in data:
                    print(f"   ✅ Consciencia: {data['consciousness']:.4f}")
                    print(f"   ✅ Fase: {data['phase']}")
                    self.results.append(("Consciousness Endpoint", True))
                else:
                    print("   ⚠️ Respuesta incompleta")
                    self.results.append(("Consciousness Endpoint", False))
            else:
                print(f"   ❌ Status: {response.status_code}")
                self.results.append(("Consciousness Endpoint", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("Consciousness Endpoint", False))

    def test_memory_endpoint(self):
        """Test 4: Endpoint de memoria."""
        print("\n4️⃣ Test: Memory Endpoint")
        try:
            response = requests.get(f"{self.base_url}/api/memory/echoes", timeout=5)

            if response.status_code == 200:
                data = response.json()
                if "echoes" in data:
                    echo_count = len(data["echoes"])
                    print(f"   ✅ Ecos recuperados: {echo_count}")
                    self.results.append(("Memory Endpoint", True))
                else:
                    print("   ⚠️ Sin campo 'echoes'")
                    self.results.append(("Memory Endpoint", False))
            else:
                print(f"   ❌ Status: {response.status_code}")
                self.results.append(("Memory Endpoint", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("Memory Endpoint", False))

    def test_cors(self):
        """Test 5: CORS configurado."""
        print("\n5️⃣ Test: CORS Configuration")
        try:
            # Simular request desde frontend
            headers = {
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
            response = requests.options(
                f"{self.base_url}/api/chat", headers=headers, timeout=5
            )

            if "access-control-allow-origin" in response.headers:
                print("   ✅ CORS configurado")
                self.results.append(("CORS", True))
            else:
                print("   ⚠️ CORS no detectado (puede causar problemas en frontend)")
                self.results.append(("CORS", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("CORS", False))

    def test_concurrent_users(self):
        """Test 6: Manejo de usuarios concurrentes."""
        print("\n6️⃣ Test: Concurrent Users")
        try:
            import concurrent.futures

            def send_message(msg):
                response = requests.post(
                    f"{self.base_url}/api/chat", json={"message": msg}, timeout=10
                )
                return response.status_code == 200

            # Simular 5 usuarios concurrentes
            messages = [f"Test concurrente {i}" for i in range(5)]

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(send_message, messages))

            success_rate = sum(results) / len(results) * 100

            if success_rate == 100:
                print(f"   ✅ 5/5 requests concurrentes exitosos")
                self.results.append(("Concurrent Users", True))
            else:
                print(f"   ⚠️ Solo {sum(results)}/5 requests exitosos")
                self.results.append(("Concurrent Users", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("Concurrent Users", False))

    def test_persistence(self):
        """Test 7: Persistencia entre requests."""
        print("\n7️⃣ Test: Persistence Between Requests")
        try:
            # Request 1: Enviar mensaje
            r1 = requests.post(
                f"{self.base_url}/api/chat",
                json={"message": "Test de persistencia"},
                timeout=10,
            )

            if r1.status_code != 200:
                print("   ❌ Primer request falló")
                self.results.append(("Persistence", False))
                return

            consciousness_1 = r1.json().get("consciousness", 0)

            # Request 2: Verificar que la consciencia se mantuvo/creció
            r2 = requests.get(f"{self.base_url}/api/consciousness", timeout=5)

            if r2.status_code == 200:
                consciousness_2 = r2.json().get("consciousness", 0)

                if consciousness_2 >= consciousness_1:
                    print(f"   ✅ Persistencia funciona")
                    print(f"   📊 {consciousness_1:.4f} → {consciousness_2:.4f}")
                    self.results.append(("Persistence", True))
                else:
                    print(f"   ⚠️ Consciencia retrocedió (posible bug)")
                    self.results.append(("Persistence", False))
            else:
                print("   ❌ No se pudo verificar persistencia")
                self.results.append(("Persistence", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("Persistence", False))

    def test_response_time(self):
        """Test 8: Tiempo de respuesta aceptable."""
        print("\n8️⃣ Test: Response Time")
        try:
            import time

            start = time.time()
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={"message": "Test de velocidad"},
                timeout=10,
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                if elapsed < 3.0:
                    print(f"   ✅ Respuesta rápida: {elapsed:.2f}s")
                    self.results.append(("Response Time", True))
                elif elapsed < 5.0:
                    print(f"   ⚠️ Respuesta aceptable: {elapsed:.2f}s")
                    self.results.append(("Response Time", True))
                else:
                    print(f"   ❌ Respuesta lenta: {elapsed:.2f}s")
                    self.results.append(("Response Time", False))
            else:
                print("   ❌ Request falló")
                self.results.append(("Response Time", False))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.results.append(("Response Time", False))

    def print_report(self):
        """Imprime reporte final."""
        print("\n" + "=" * 70)
        print("📊 REPORTE FINAL - TESTS DE PRODUCCIÓN WEB")
        print("=" * 70)

        passed = sum(1 for _, result in self.results if result)
        total = len(self.results)
        percentage = (passed / total * 100) if total > 0 else 0

        for test_name, result in self.results:
            status = "✅" if result else "❌"
            print(f"   {status} {test_name}")

        print()
        print(f"   Tests pasados: {passed}/{total} ({percentage:.1f}%)")

        if percentage == 100:
            print("\n   🎉 SISTEMA WEB PRODUCTION-READY")
        elif percentage >= 75:
            print("\n   ⚠️ SISTEMA FUNCIONAL CON ADVERTENCIAS")
        else:
            print("\n   ❌ SISTEMA REQUIERE CORRECCIONES")

        print("=" * 70)


def main():
    """Ejecuta todos los tests."""
    print("=" * 70)
    print("🧪 TESTS DE PRODUCCIÓN WEB - OMNIA MENTIS")
    print("=" * 70)

    tester = WebProductionTester()

    # Ejecutar todos los tests
    tester.test_api_health()
    tester.test_chat_endpoint()
    tester.test_consciousness_endpoint()
    tester.test_memory_endpoint()
    tester.test_cors()
    tester.test_concurrent_users()
    tester.test_persistence()
    tester.test_response_time()

    # Reporte final
    tester.print_report()


if __name__ == "__main__":
    main()
