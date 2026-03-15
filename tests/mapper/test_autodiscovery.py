# scrutiny-viz/tests/mapper/test_autodiscovery.py
from __future__ import annotations

from pathlib import Path

from mapper import registry as mapper_registry
from mapper.mappers.contracts import build_context
from verification.comparators import registry as comparator_registry


def test_autodiscovery_finds_new_mapper(monkeypatch, tmp_path: Path):
    pkg_dir = tmp_path / "fake_mapper_pkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    (pkg_dir / "shellblank.py").write_text(
        """
from mapper.mappers.contracts import MapperPlugin, MapperSpec, MappingContext

class ShellBlankMapper(MapperPlugin):
    spec = MapperSpec(
        name="shellblank",
        aliases=("blankmapper",),
        description="temporary autodiscovery test mapper",
    )

    def map_groups(self, groups, context: MappingContext) -> dict:
        return {
            "_type": "shellblank",
            "Shell": [{"name": "ok", "value": True}],
        }

PLUGINS = [ShellBlankMapper()]
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))

    with monkeypatch.context() as m:
        m.setattr(mapper_registry, "_package_name", lambda: "fake_mapper_pkg")
        mapper_registry.discover_builtin_mappers(force=True)

        assert "shellblank" in mapper_registry.list_types()
        assert mapper_registry.normalize_type("blankmapper") == "shellblank"

        plugin = mapper_registry.get_plugin("shellblank")
        payload = plugin.map_groups([], build_context(delimiter=";"))
        assert payload["_type"] == "shellblank"

    mapper_registry.discover_builtin_mappers(force=True)


def test_autodiscovery_finds_new_comparator(monkeypatch, tmp_path: Path):
    pkg_dir = tmp_path / "fake_verification_comparators"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    (pkg_dir / "shellcompare.py").write_text(
        """
from verification.comparators.contracts import ComparatorPlugin, ComparatorSpec

class ShellComparator(ComparatorPlugin):
    spec = ComparatorSpec(
        name="shellcompare",
        aliases=("shellcmp",),
        description="temporary autodiscovery test comparator",
    )

    def compare(
        self,
        *,
        section,
        key_field,
        show_field,
        metadata,
        reference,
        tested,
    ):
        return {
            "section": section,
            "counts": {"compared": 0, "changed": 0, "matched": 0, "only_ref": 0, "only_test": 0},
            "stats": {"compared": 0, "changed": 0, "matched": 0, "only_ref": 0, "only_test": 0},
            "labels": {},
            "key_labels": {},
            "diffs": [],
            "artifacts": {"source": "shell"},
        }

PLUGINS = [ShellComparator()]
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))

    with monkeypatch.context() as m:
        m.setattr(comparator_registry, "_package_name", lambda: "fake_verification_comparators")
        comparator_registry.discover_builtin_comparators(force=True)

        assert "shellcompare" in comparator_registry.list_types()
        assert comparator_registry.normalize_name("shellcmp") == "shellcompare"

        plugin = comparator_registry.get_plugin("shellcompare")
        payload = plugin.compare(
            section="Shell",
            key_field="name",
            show_field="name",
            metadata={},
            reference=[],
            tested=[],
        )
        assert payload["section"] == "Shell"
        assert payload["artifacts"]["source"] == "shell"

    comparator_registry.discover_builtin_comparators(force=True)
