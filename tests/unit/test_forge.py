# tests/unit/test_forge.py
"""
* UBICACIÓN: OmniaMentis/tests/unit/test_forge.py
* PROPÓSITO: Tests del motor de revisión de código (src/core/forge/code_review.py) y
*            del módulo OmniaForge. El código revisado NUNCA se ejecuta: hay pruebas
*            que lo demuestran con un «veneno» que dejaría un rastro si se ejecutara.
* CREADO: 2026-10-20
* ESTADO: Test Permanente
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.forge import code_review as cr
from router.keyword_router import KeywordRouter
from router.modules.base_module import OmniaContext
from router.modules.omnia_forge import OmniaForgeModule


def kinds(result):
    return [f["kind"] for f in result["findings"]]


class TestNeverExecutes:
    def test_review_does_not_run_the_code(self, tmp_path):
        marker = tmp_path / "ejecutado.txt"
        code = f"open({str(marker)!r}, 'w').write('x')\nraise SystemExit(1)\n__import__('os').system('echo hola')\n"
        r = cr.review(code)
        assert r["valid"] is True and not marker.exists()
        assert "risky_call" in kinds(r)

    def test_module_does_not_run_the_code(self, tmp_path):
        marker = tmp_path / "ejecutado2.txt"
        msg = f"ejecuta esto ```python\nopen({str(marker)!r}, 'w').write('x')\n```"
        OmniaForgeModule().handle(msg, OmniaContext("u", 0.1, "s", age_band="adult"))
        assert not marker.exists()

    def test_infinite_loop_and_huge_computation_return_immediately(self):
        assert cr.review("while True:\n    pass\n")["valid"] is True
        assert cr.review("x = 9**9**9\n")["valid"] is True      # no se evalúa (ast.parse no calcula)


class TestExtract:
    @pytest.mark.parametrize("msg,lang,code", [
        ("revisa ```python\nprint(1)\n``` ok", "python", "print(1)"),
        ("```js\nlet a = 1\n```", "js", "let a = 1"),
        ("```\nx = 1\n```", None, "x = 1"),
        ("```python\n\n```", "python", None), ("sin bloque", None, None), ("", None, None), (None, None, None)])
    def test_extract_code(self, msg, lang, code):
        assert cr.extract_code(msg) == (lang, code)

    @pytest.mark.parametrize("lang,expected", [(None, "python"), ("py", "python"), ("python3", "python"),
                                               ("js", "javascript"), ("typescript", "javascript"), ("rust", "rust")])
    def test_normalize_language(self, lang, expected):
        assert cr.normalize_language(lang) == expected


class TestReviewInput:
    @pytest.mark.parametrize("bad", ["", "   \n", None, 5, b"x"])
    def test_empty_or_wrong_type(self, bad):
        with pytest.raises(cr.ReviewError):
            cr.review(bad)

    def test_too_long_and_null_byte(self):
        with pytest.raises(cr.ReviewError):
            cr.review("x = 1\n" * 5000)
        with pytest.raises(cr.ReviewError):
            cr.review("x = 1\x00")

    def test_syntax_error_reports_line(self):
        r = cr.review("a = 1\ndef f(:\n    pass\n")
        assert r["valid"] is False and r["error"]["line"] == 2 and r["findings"] == []

    def test_deeply_nested_code_is_handled_not_crashed(self):
        r = cr.review("x = " + "(" * 3000 + "1" + ")" * 3000)
        assert r["valid"] in (True, False)                      # no lanza RecursionError

    def test_limit_exact_boundary(self):
        assert cr.review("x = 1\n" + "#" * (cr.MAX_CODE_CHARS - 6))["valid"] is True


class TestFindings:
    def test_clean_code_has_no_findings(self):
        r = cr.review('def suma(a, b):\n    """Suma."""\n    return a + b\n')
        assert r["findings"] == [] and r["metrics"]["functions"] == 1 and r["metrics"]["functions_without_docstring"] == 0

    @pytest.mark.parametrize("code,kind,sev", [
        ("eval(x)", "risky_call", "alto"), ("exec(x)", "risky_call", "alto"),
        ("import os\nos.system('ls')", "risky_call", "alto"),
        ("import subprocess\nsubprocess.run(['ls'])", "risky_call", "medio"),
        ("import subprocess\nsubprocess.run('ls', shell=True)", "shell_true", "alto"),
        ("import pickle\npickle.loads(b)", "risky_call", "alto"),
        ("import yaml\nyaml.load(s)", "risky_call", "alto"),
        ("import requests\nrequests.get(u, verify=False)", "tls_off", "alto"),
        ("PASSWORD = 'supersecreto123'", "hardcoded_secret", "alto"),
        ("self_token = 1\nclass A:\n    api_key = 'abcdef123456'", "hardcoded_secret", "alto"),
        ("def f(a=[]): pass", "mutable_default", "medio"), ("def f(a={}): pass", "mutable_default", "medio"),
        ("def f(*, a=list()): pass", "mutable_default", "medio"),
        ("try:\n    pass\nexcept:\n    pass", "bare_except", "medio"),
        ("x = 1\nif x == None: pass", "compare_none", "bajo"),
        ("import json", "unused_import", "bajo"), ("from os import *", "import_star", "bajo"),
        ("open('a.txt', 'w')", "writes_file", "bajo"), ("import shutil\nshutil.rmtree('x')", "risky_call", "medio")])
    def test_detects(self, code, kind, sev):
        r = cr.review(code)
        assert any(f["kind"] == kind and f["severity"] == sev for f in r["findings"]), r["findings"]

    @pytest.mark.parametrize("code,kind", [
        ("import yaml\nyaml.load(s, Loader=yaml.SafeLoader)", "risky_call"),
        ("import yaml\nyaml.safe_load(s)", "risky_call"),
        ("PASSWORD = ''", "hardcoded_secret"), ("PASSWORD = 'corto'", "hardcoded_secret"),
        ("name = 'supersecreto123'", "hardcoded_secret"),
        ("def f(a=None): pass", "mutable_default"), ("def f(a=(1, 2)): pass", "mutable_default"),
        ("x = 1\nif x is None: pass", "compare_none"),
        ("import json\nprint(json.dumps({}))", "unused_import"),
        ("open('a.txt')", "writes_file"), ("open('a.txt', 'r')", "writes_file"),
        ("import requests\nrequests.get(u)", "tls_off")])
    def test_does_not_flag_safe_code(self, code, kind):
        assert kind not in kinds(cr.review(code))

    def test_alias_resolution(self):
        r = cr.review("import subprocess as sp\nsp.run('x', shell=True)")
        assert "shell_true" in kinds(r)
        r2 = cr.review("from os import system as s\ns('ls')")
        assert any(f["kind"] == "risky_call" and "os.system" in f["message"] for f in r2["findings"])

    def test_complexity_warning(self):
        body = "\n".join(f"    if x == {i}:\n        return {i}" for i in range(12))
        r = cr.review(f"def f(x):\n    \"\"\"doc\"\"\"\n{body}\n    return 0\n")
        assert "complex_function" in kinds(r) and r["metrics"]["max_complexity"] >= 13

    def test_sorted_by_severity_then_line(self):
        r = cr.review("import json\nx = 1\nif x == None: pass\neval('1')\n")
        sev = [f["severity"] for f in r["findings"]]
        assert sev == sorted(sev, key=lambda s: cr.SEVERITY_ORDER[s]) and r["findings"][0]["kind"] == "risky_call"

    def test_findings_are_capped_but_total_is_reported(self):
        code = "\n".join(f"eval('{i}')" for i in range(60))
        r = cr.review(code)
        assert len(r["findings"]) == cr.MAX_FINDINGS and r["findings_total"] == 60

    def test_metrics(self):
        r = cr.review("import os, sys\nclass A:\n    def m(self): pass\ndef f(): pass\n")
        m = r["metrics"]
        assert m["classes"] == 1 and m["functions"] == 2 and m["imports"] == ["os", "sys"] and m["lines"] == 4

    def test_format_review(self):
        assert "no es Python válido" in cr.format_review(cr.review("def (:"))
        assert "No marqué nada" in cr.format_review(cr.review("x = 1"))
        out = cr.format_review(cr.review("eval('1')"))
        assert "Hallazgos (1)" in out and "[alto]" in out and "no ejecuté nada" in out


ADULT = OmniaContext("u", 0.1, "s", age_band="adult")


class TestModule:
    m = OmniaForgeModule()

    def test_no_code_explains_and_asks(self):
        r = self.m.handle("quiero ejecutar código", ADULT)
        assert r.data["status"] == "no_execution" and "No ejecuto código" in r.text and r.requires_followup is True

    def test_automation_without_code_asks_for_code(self):
        assert self.m.handle("quiero automatizar tareas", ADULT).data["status"] == "needs_code"

    def test_reviews_python_block(self):
        r = self.m.handle("revisa este código ```python\neval(x)\n```", ADULT)
        assert r.data["status"] == "reviewed" and r.data["findings"] == 1 and "No ejecuto" not in r.text

    def test_run_request_with_code_reviews_and_explains(self):
        r = self.m.handle("ejecuta esto ```python\nprint(1)\n```", ADULT)
        assert r.data["status"] == "reviewed" and "No ejecuto código" in r.text

    def test_syntax_error_status(self):
        assert self.m.handle("revisa ```python\ndef (:\n```", ADULT).data["status"] == "syntax_error"

    def test_javascript_is_not_supported_yet(self):
        r = self.m.handle("revisa ```js\nlet a = 1\n```", ADULT)
        assert r.data["status"] == "unsupported_language" and "solo reviso Python" in r.text

    def test_too_long_code(self):
        r = self.m.handle("revisa ```python\n" + "x = 1\n" * 5000 + "```", ADULT)
        assert r.data["status"] == "invalid_input"


class TestRouting:
    @pytest.mark.parametrize("msg", ["quiero ejecutar código python en un sandbox", "revisa este código ```python\nx=1\n```"])
    def test_routes_to_forge_for_adults(self, msg):
        r = KeywordRouter().route(msg, OmniaContext("u", 0.1, "s", age_band="adult"))
        assert r.module_response.module_name == "OmniaForge"

    @pytest.mark.parametrize("band", ["minor", "minor_basic"])
    def test_minors_are_restricted(self, band):
        r = KeywordRouter().route("revisa este código ```python\nx=1\n```", OmniaContext("u", 0.1, "s", age_band=band))
        assert r.age_restricted_module == "OmniaForge" and r.module_response is None


class TestSummary:
    def test_summary_counts_by_severity_and_has_no_code(self):
        code = "import os\nSECRETO = 'abc'\nos.system('ls')\ndef f(x=[]):\n    return x\n"
        s = cr.summary(cr.review(code))
        assert set(s) == {"valid", "findings", "sev", "lines", "max_complexity"}
        assert s["valid"] is True and s["lines"] == 5
        assert sum(s["sev"].values()) == min(s["findings"], 30)
        assert s["sev"]["alto"] >= 1 and "abc" not in str(s)

    def test_summary_of_syntax_error(self):
        s = cr.summary(cr.review("def (:"))
        assert s["valid"] is False and s["findings"] == 0 and s["sev"] == {"alto": 0, "medio": 0, "bajo": 0}
