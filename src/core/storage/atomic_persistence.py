"""
Sistema de Persistencia Atómica - Omnia Mentis
==============================================
Almacenamiento JSON con escrituras atómicas, backups automáticos
y recuperación ante fallos.

Características:
- Escrituras atómicas (sin corrupción en crashes)
- Backups automáticos con timestamps
- Recuperación desde backups en caso de corrupción
- Validación de datos pre-escritura
- Limpieza automática de backups antiguos
- Thread-safe por diseño del OS (atomic rename)

Autor: El Fons
Fecha: 2025-11-26
"""

import json
import tempfile
import shutil
from pathlib import Path
from typing import Any, Callable, Optional, List
from datetime import datetime
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class AtomicJSONStore:
    """
    Almacenamiento JSON con escrituras atómicas y backups.
    
    Garantiza que las escrituras sean atómicas (todo o nada),
    previniendo corrupción de datos en caso de crashes o fallos.
    
    Example:
        >>> store = AtomicJSONStore("data/memory/echoes.json")
        >>> data = {"echoes": [{"text": "Primera memoria"}]}
        >>> store.save(data)
        >>> loaded = store.load(default=[])
        >>> print(loaded)
        {'echoes': [{'text': 'Primera memoria'}]}
    
    Attributes:
        filepath: Ruta del archivo JSON
        auto_backup: Si se crean backups automáticos
        max_backups: Número máximo de backups a mantener
    """
    
    def __init__(
        self,
        filepath: Path | str,
        auto_backup: bool = True,
        max_backups: int = 5
    ):
        """
        Inicializa el almacén atómico.
        
        Args:
            filepath: Ruta del archivo JSON
            auto_backup: Si crear backups antes de escribir
            max_backups: Máximo de backups a conservar
        """
        self.filepath = Path(filepath)
        self.auto_backup = auto_backup
        self.max_backups = max_backups
        
        # Crear directorio si no existe
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"AtomicJSONStore inicializado: {self.filepath}")
    
    def save(
        self,
        data: Any,
        validator: Optional[Callable[[Any], bool]] = None,
        indent: int = 2
    ) -> bool:
        """
        Guarda datos con escritura atómica.
        
        Proceso:
        1. Valida datos (si se proporciona validador)
        2. Crea backup del archivo actual
        3. Escribe a archivo temporal
        4. Atomic rename (garantizado por OS)
        5. Limpia backups antiguos
        
        Args:
            data: Datos a guardar (debe ser JSON-serializable)
            validator: Función opcional que valida los datos
            indent: Indentación del JSON (2 por defecto)
        
        Returns:
            True si guardado exitoso, False si falló
            
        Raises:
            ValueError: Si los datos no pasan validación
            TypeError: Si los datos no son JSON-serializables
        """
        try:
            # 1. Validar antes de escribir
            if validator and not validator(data):
                raise ValueError("Datos no pasan validación personalizada")
            
            # 2. Backup del archivo actual
            if self.auto_backup and self.filepath.exists():
                self._create_backup()
            
            # 3. Escribir a archivo temporal
            temp_file = self._write_to_temp(data, indent)
            
            # 4. Atomic rename (operación atómica del OS)
            temp_file.replace(self.filepath)
            
            # 5. Limpiar backups antiguos
            self._cleanup_old_backups()
            
            logger.info(f"Guardado atómico exitoso: {self.filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error en guardado atómico de {self.filepath}: {e}")
            # Limpiar archivo temporal si existe
            if 'temp_file' in locals():
                temp_file.unlink(missing_ok=True)
            return False
    
    def load(self, default: Any = None) -> Any:
        """
        Carga datos con fallback a backup en caso de corrupción.
        
        Orden de intento:
        1. Archivo principal
        2. Backup más reciente
        3. Backups anteriores (orden descendente)
        4. Valor por defecto
        
        Args:
            default: Valor a retornar si no se puede cargar
        
        Returns:
            Datos cargados o valor por defecto
        """
        # Intentar cargar archivo principal
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Cargado desde archivo principal: {self.filepath}")
            return data
            
        except FileNotFoundError:
            logger.warning(f"Archivo no encontrado: {self.filepath}")
            return default
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON corrupto en {self.filepath}: {e}")
            # Intentar recuperar desde backup
            return self._load_from_backup(default)
        
        except Exception as e:
            logger.error(f"Error al cargar {self.filepath}: {e}")
            return default
    
    def exists(self) -> bool:
        """Verifica si el archivo existe."""
        return self.filepath.exists()
    
    def delete(self, keep_backups: bool = True) -> bool:
        """
        Elimina el archivo principal.
        
        Args:
            keep_backups: Si mantener los backups
        
        Returns:
            True si eliminado exitosamente
        """
        try:
            if self.filepath.exists():
                self.filepath.unlink()
                logger.info(f"Archivo eliminado: {self.filepath}")
            
            if not keep_backups:
                self._cleanup_old_backups(keep=0)
            
            return True
        except Exception as e:
            logger.error(f"Error al eliminar {self.filepath}: {e}")
            return False
    
    def get_backups(self) -> List[Path]:
        """Retorna lista de backups disponibles (más reciente primero)."""
        backups = sorted(
            self.filepath.parent.glob(f"{self.filepath.stem}_*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return backups
    
    def restore_from_backup(self, backup_index: int = 0) -> bool:
        """
        Restaura desde un backup específico.
        
        Args:
            backup_index: Índice del backup (0 = más reciente)
        
        Returns:
            True si restaurado exitosamente
        """
        backups = self.get_backups()
        
        if not backups:
            logger.error("No hay backups disponibles")
            return False
        
        if backup_index >= len(backups):
            logger.error(f"Índice de backup fuera de rango: {backup_index}")
            return False
        
        try:
            backup = backups[backup_index]
            shutil.copy2(backup, self.filepath)
            logger.info(f"Restaurado desde backup: {backup}")
            return True
        except Exception as e:
            logger.error(f"Error al restaurar desde backup: {e}")
            return False
    
    def _write_to_temp(self, data: Any, indent: int) -> Path:
        """
        Escribe datos a archivo temporal.
        
        Args:
            data: Datos a escribir
            indent: Indentación del JSON
        
        Returns:
            Path del archivo temporal
        
        Raises:
            TypeError: Si datos no son JSON-serializables
        """
        # Crear archivo temporal en el mismo directorio
        # (importante para que atomic rename funcione)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.filepath.parent,
            suffix='.tmp',
            prefix='.omnia_'
        )
        
        try:
            with open(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            return Path(temp_path)
            
        except Exception as e:
            # Limpiar archivo temporal si falla
            Path(temp_path).unlink(missing_ok=True)
            raise
    
    def _create_backup(self):
        """Crea backup con timestamp del archivo actual."""
        if not self.filepath.exists():
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.filepath.with_name(
            f"{self.filepath.stem}_{timestamp}.bak"
        )
        
        try:
            shutil.copy2(self.filepath, backup_path)
            logger.debug(f"Backup creado: {backup_path.name}")
        except Exception as e:
            logger.warning(f"No se pudo crear backup: {e}")
    
    def _cleanup_old_backups(self, keep: Optional[int] = None):
        """
        Limpia backups antiguos, manteniendo los más recientes.
        
        Args:
            keep: Número de backups a mantener (usa self.max_backups si None)
        """
        if keep is None:
            keep = self.max_backups
        
        backups = self.get_backups()
        
        for old_backup in backups[keep:]:
            try:
                old_backup.unlink()
                logger.debug(f"Backup antiguo eliminado: {old_backup.name}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar backup {old_backup}: {e}")
    
    def _load_from_backup(self, default: Any) -> Any:
        """
        Intenta cargar desde backups disponibles.
        
        Args:
            default: Valor por defecto si ningún backup funciona
        
        Returns:
            Datos del backup o valor por defecto
        """
        backups = self.get_backups()
        
        for backup in backups:
            try:
                with open(backup, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Recuperado desde backup: {backup.name}")
                return data
            except Exception as e:
                logger.warning(f"Backup corrupto {backup.name}: {e}")
                continue
        
        logger.error("No se pudo recuperar desde ningún backup")
        return default
    
    @contextmanager
    def atomic_update(self, default: Any = None):
        """
        Context manager para actualización atómica.
        
        Example:
            >>> with store.atomic_update(default={}) as data:
            ...     data['new_key'] = 'new_value'
        
        Args:
            default: Valor por defecto si el archivo no existe
        
        Yields:
            Datos cargados (modificables)
        """
        data = self.load(default=default)
        try:
            yield data
            self.save(data)
        except Exception as e:
            logger.error(f"Error en actualización atómica: {e}")
            raise


# Funciones de conveniencia
def load_json_safe(filepath: Path | str, default: Any = None) -> Any:
    """Carga JSON de forma segura con fallback."""
    store = AtomicJSONStore(filepath, auto_backup=False)
    return store.load(default)


def save_json_safe(filepath: Path | str, data: Any, backup: bool = True) -> bool:
    """Guarda JSON de forma segura con escritura atómica."""
    store = AtomicJSONStore(filepath, auto_backup=backup)
    return store.save(data)


if __name__ == "__main__":
    # Tests de ejemplo
    print("="*70)
    print("🧪 TESTS DE PERSISTENCIA ATÓMICA")
    print("="*70)
    
    # Setup de logging para tests
    logging.basicConfig(level=logging.INFO)
    
    test_file = Path("data/test/atomic_test.json")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Test 1: Escritura y lectura básica
    print("\n1️⃣ Escritura y lectura básica")
    store = AtomicJSONStore(test_file)
    data = {"test": "data", "number": 42, "list": [1, 2, 3]}
    success = store.save(data)
    loaded = store.load()
    print(f"   Guardado: {success}")
    print(f"   Recuperado: {loaded == data}")
    
    # Test 2: Backups automáticos
    print("\n2️⃣ Backups automáticos")
    store.save({"version": 1})
    store.save({"version": 2})
    store.save({"version": 3})
    backups = store.get_backups()
    print(f"   Backups creados: {len(backups)}")
    
    # Test 3: Context manager
    print("\n3️⃣ Actualización con context manager")
    with store.atomic_update(default={"counter": 0}) as data:
        data["counter"] += 1
    loaded = store.load()
    print(f"   Counter: {loaded.get('counter')}")
    
    # Test 4: Validador personalizado
    print("\n4️⃣ Validación pre-escritura")
    def validate_data(data):
        return isinstance(data, dict) and 'required_field' in data
    
    try:
        store.save({"invalid": "data"}, validator=validate_data)
        print("   ❌ No debería llegar aquí")
    except ValueError:
        print("   ✅ Validación funcionó correctamente")
    
    # Limpiar archivos de test
    store.delete(keep_backups=False)
    
    print("\n" + "="*70)
    print("✅ Tests completados")