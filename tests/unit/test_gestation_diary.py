# tests/unit/test_gestation_diary.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_gestation_diary.py
* PROPÓSITO: Tests unitarios para GestationDiary v2.0 (SQLite)
  (src/living_memory/gestation_diary.py)
* DEPENDENCIAS: pytest, tmp_path, monkeypatch
* CREADO: 2026-10-09
* ESTADO: Test Permanente

Cubre: inicialización y entrada de nacimiento, altas por categoría,
persistencia entre instancias, consultas, estadísticas, exportaciones
(incluido el escape HTML y que NO se ensucie el directorio de trabajo),
migración única desde el JSON anterior, recuperación ante base corrupta
(se aparta, no se borra) y concurrencia desde varios threads.
"""

import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from living_memory.gestation_diary import GestationDiary, PHASE_NAMES


def make_diary(tmp_path, name="diary"):
    return GestationDiary(diary_dir=str(tmp_path / name))


class TestInitialization:

    def test_new_diary_has_exactly_the_birth_entry(self, tmp_path):
        diary = make_diary(tmp_path)
        assert len(diary.entries) == 1
        assert diary.entries[0]["entry_id"] == "diary_birth_00000000_000000"

    def test_creates_database_file(self, tmp_path):
        diary = make_diary(tmp_path)
        assert diary.db_path.exists()

    def test_birth_entry_not_duplicated_on_reopen(self, tmp_path):
        make_diary(tmp_path).close()
        diary2 = make_diary(tmp_path)
        assert len(diary2.entries) == 1


class TestAddingEntries:

    def test_add_entry_returns_id_and_persists_in_memory_list(self, tmp_path):
        diary = make_diary(tmp_path)
        entry_id = diary.add_entry("t", "c", "reflection", 0.1, phase=1)
        assert entry_id.startswith("diary_")
        assert entry_id in [e["entry_id"] for e in diary.entries]

    def test_ids_are_unique_for_rapid_additions(self, tmp_path):
        diary = make_diary(tmp_path)
        ids = {diary.add_entry(f"t{i}", "c", "learning", 0.1) for i in range(50)}
        assert len(ids) == 50

    def test_helpers_set_category_and_tags(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_milestone("m", "d", 0.1, 1)
        diary.add_reflection("r", "d", 0.1, 1)
        diary.add_learning("x", "d", 0.1, 1)
        diary.add_emotional_experience("tristeza", "d", 0.1, 1)
        cats = [e["category"] for e in diary.entries[1:]]
        assert cats == ["milestone", "reflection", "learning", "emotion"]
        assert "tristeza" in diary.entries[-1]["tags"]

    def test_phase_name_stored_and_unknown_phase_does_not_crash(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_entry("t", "c", "growth", 0.1, phase=2)
        diary.add_entry("t", "c", "growth", 0.1, phase=42)
        assert diary.entries[-2]["phase"] == PHASE_NAMES[2]
        assert diary.entries[-1]["phase"] == "Fase 42"

    def test_phase_transition_with_unknown_phase_does_not_raise(self, tmp_path):
        diary = make_diary(tmp_path)
        entry_id = diary.record_phase_transition(1, 99, 0.2, "reflexión")
        assert entry_id.startswith("diary_")

    def test_significance_capped_at_one(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_entry("t", "c", "milestone", 5.0)
        assert diary.entries[-1]["significance"] == 1.0

    def test_unicode_and_emoji_content_roundtrip(self, tmp_path):
        diary = make_diary(tmp_path)
        text = "Ñandú ♋ 💝 «prueba»"
        diary.add_entry(text, text, "emotion", 0.1)
        diary.close()
        reopened = make_diary(tmp_path)
        assert reopened.entries[-1]["title"] == text


class TestPersistence:

    def test_entries_survive_reopen_in_order(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_entry("primera", "c", "reflection", 0.1)
        diary.add_entry("segunda", "c", "reflection", 0.1)
        diary.close()

        reopened = make_diary(tmp_path)
        titles = [e["title"] for e in reopened.entries]
        assert titles[-2:] == ["primera", "segunda"]

    def test_tags_and_metadata_survive_reopen(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_entry("t", "c", "growth", 0.1, tags=["a", "b"], metadata={"k": 1})
        diary.close()
        last = make_diary(tmp_path).entries[-1]
        assert last["tags"] == ["a", "b"]
        assert last["metadata"] == {"k": 1}

    def test_save_entries_is_harmless_noop(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.save_entries()
        diary._save_entries()
        assert len(diary.entries) == 1

    def test_two_diaries_in_different_dirs_are_isolated(self, tmp_path):
        a = make_diary(tmp_path, "a")
        b = make_diary(tmp_path, "b")
        a.add_entry("solo en a", "c", "reflection", 0.1)
        assert len(a.entries) == 2
        assert len(b.entries) == 1


class TestQueries:

    def test_recent_entries_newest_first_and_limited(self, tmp_path):
        diary = make_diary(tmp_path)
        for i in range(5):
            diary.add_entry(f"e{i}", "c", "reflection", 0.1)
        recent = diary.get_recent_entries(3)
        assert [e["title"] for e in recent] == ["e4", "e3", "e2"]

    def test_recent_entries_zero_limit_is_empty(self, tmp_path):
        assert make_diary(tmp_path).get_recent_entries(0) == []

    def test_filter_by_phase_and_category(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_milestone("m", "d", 0.1, 3)
        diary.add_reflection("r", "d", 0.1, 3)
        assert len(diary.get_entries_by_phase(3)) == 2
        assert [e["title"] for e in diary.get_reflections()] == ["r"]
        assert "m" in [e["title"] for e in diary.get_milestones()]

    def test_search_is_case_insensitive_in_title_and_content(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_entry("Título Especial", "contenido normal", "learning", 0.1)
        diary.add_entry("otro", "Hay un SECRETO aquí", "learning", 0.1)
        assert len(diary.search_entries("especial")) == 1
        assert len(diary.search_entries("secreto")) == 1
        assert diary.search_entries("inexistente") == []


class TestStatistics:

    def test_statistics_counts(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_milestone("m", "d", 0.1, 1)
        diary.add_reflection("r", "d", 0.1, 1)
        stats = diary.get_diary_statistics()
        assert stats["total_entries"] == 3
        assert stats["by_category"]["milestone"] == 2  # nacimiento + m
        assert stats["by_category"]["reflection"] == 1
        assert 0.0 < stats["avg_significance"] <= 1.0
        assert stats["days_active"] >= 0


class TestExports:

    def test_exports_go_to_diary_dir_not_cwd(self, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        diary = make_diary(tmp_path)
        path = diary.export_diary(format="markdown")
        assert diary.export_dir in path.parents
        assert not (cwd / "data").exists()

    def test_export_dir_not_created_until_export(self, tmp_path):
        diary = make_diary(tmp_path)
        assert not diary.export_dir.exists()

    def test_all_formats_write_files(self, tmp_path):
        diary = make_diary(tmp_path)
        for fmt, ext in (("json", ".json"), ("markdown", ".md"), ("html", ".html")):
            path = diary.export_diary(format=fmt, filename=f"x_{fmt}")
            assert path.exists() and path.suffix == ext

    def test_json_export_is_valid_and_complete(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_entry("t", "c", "learning", 0.1)
        data = json.loads(diary.export_diary(format="json").read_text(encoding="utf-8"))
        assert len(data["entries"]) == 2
        assert data["statistics"]["total_entries"] == 2

    def test_html_export_escapes_markup(self, tmp_path):
        diary = make_diary(tmp_path)
        diary.add_entry("<script>alert(1)</script>", "<img src=x onerror=1>", "learning", 0.1)
        body = diary.export_diary(format="html").read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body
        assert "<img src=x" not in body

    def test_unsupported_format_raises(self, tmp_path):
        import pytest
        with pytest.raises(ValueError):
            make_diary(tmp_path).export_diary(format="pdf")

    def test_filename_cannot_escape_export_dir(self, tmp_path):
        diary = make_diary(tmp_path)
        path = diary.export_diary(format="json", filename="../../evil")
        assert diary.export_dir in path.parents


class TestLegacyJsonMigration:

    def _write_legacy(self, directory: Path, entries):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "gestation_diary.json").write_text(
            json.dumps(entries, ensure_ascii=False), encoding="utf-8"
        )

    def test_imports_legacy_entries_once_and_renames_file(self, tmp_path):
        d = tmp_path / "diary"
        self._write_legacy(d, [
            {"entry_id": "old_1", "timestamp": "2026-06-01T10:00:00", "phase": PHASE_NAMES[1],
             "consciousness_level": 0.05, "title": "Viejo 1", "content": "c",
             "category": "milestone", "significance": 0.9, "tags": ["x"], "metadata": {}},
            {"entry_id": "old_2", "timestamp": "2026-06-02T10:00:00", "phase": PHASE_NAMES[1],
             "consciousness_level": 0.06, "title": "Viejo 2", "content": "c",
             "category": "reflection", "significance": 0.5, "tags": [], "metadata": {}},
        ])
        diary = GestationDiary(diary_dir=str(d))
        titles = [e["title"] for e in diary.entries]
        assert titles == ["Viejo 1", "Viejo 2"]  # sin entrada de nacimiento extra
        assert not (d / "gestation_diary.json").exists()
        assert (d / "gestation_diary.json.migrated").exists()

        diary.close()
        again = GestationDiary(diary_dir=str(d))
        assert len(again.entries) == 2  # no se reimporta

    def test_incomplete_legacy_entries_get_safe_defaults(self, tmp_path):
        d = tmp_path / "diary"
        self._write_legacy(d, [{"entry_id": "solo_id"}, "basura", {"sin": "id"}])
        diary = GestationDiary(diary_dir=str(d))
        assert [e["entry_id"] for e in diary.entries] == ["solo_id"]
        assert diary.entries[0]["title"] == ""

    def test_corrupt_legacy_json_is_left_intact_and_does_not_crash(self, tmp_path):
        d = tmp_path / "diary"
        d.mkdir()
        (d / "gestation_diary.json").write_text("{esto no es json", encoding="utf-8")
        diary = GestationDiary(diary_dir=str(d))
        assert len(diary.entries) == 1  # solo nacimiento
        assert (d / "gestation_diary.json").exists()


class TestCorruptDatabase:

    def test_corrupt_db_is_set_aside_not_deleted(self, tmp_path):
        d = tmp_path / "diary"
        first = GestationDiary(diary_dir=str(d))
        first.close()
        (d / "diary.db").write_bytes(b"esto no es un archivo sqlite valido")

        diary = GestationDiary(diary_dir=str(d))
        assert len(diary.entries) == 1  # base nueva con nacimiento
        assert list(d.glob("diary.db.corrupt-*")), "la base corrupta debe conservarse"
        diary.add_entry("sigue funcionando", "c", "reflection", 0.1)
        assert len(diary.entries) == 2


class TestConcurrency:

    def test_parallel_adds_are_all_persisted(self, tmp_path):
        diary = make_diary(tmp_path)
        errors = []

        def worker(n):
            try:
                for i in range(20):
                    diary.add_entry(f"w{n}-{i}", "c", "learning", 0.1)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(diary.entries) == 1 + 100
        diary.close()
        assert len(make_diary(tmp_path).entries) == 101