"""Whitelist-based standalone source export, also available inside exported projects."""

from pathlib import Path
import shutil
import json
import hashlib


def export_template(profile, target, *, source=None):
    if source:
        root = Path(source).resolve()
    else:
        options = [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parents[2]]
        root = next(
            (path for path in options if (path / "template-manifest.json").is_file()),
            None,
        )
        if root is None:
            raise FileNotFoundError(
                "Run template export from a source project containing template-manifest.json"
            )
    manifest = json.loads((root / "template-manifest.json").read_text(encoding="utf-8"))
    if profile not in manifest["profiles"]:
        raise ValueError(f"{profile} is not included in this source distribution")
    destination = Path(target).resolve()
    if destination == root or destination in root.parents:
        raise ValueError("Export destination must not be the source or its ancestor")
    if destination.exists() and (
        not destination.is_dir() or any(destination.iterdir())
    ):
        raise FileExistsError("Export target must be absent or empty")
    selected = manifest["profiles"][profile]
    files = [*manifest["common"], *selected["files"]]
    resolved = []
    for name in files:
        src = (root / name).resolve()
        if not src.is_relative_to(root) or not src.is_file():
            raise ValueError(f"Invalid manifest file: {name}")
        if not (destination / name).resolve().is_relative_to(destination):
            raise ValueError("Manifest destination escapes project root")
        resolved.append((name, src))
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, src in resolved:
        dst = destination / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        hashes[name] = hashlib.sha256(dst.read_bytes()).hexdigest()
    dependencies = manifest["dependencies"] + selected.get("dependencies", [])
    optional = manifest.get("optional_dependencies", {})
    toml = [
        "[project]",
        f'name = "paper-template-{profile.replace("_", "-")}"',
        'version = "0.2.0"',
        'requires-python = ">=3.12"',
        'readme = "README.md"',
        "dependencies = " + json.dumps(dependencies),
        "[project.scripts]",
        'paper = "framework.runtime.cli:main"',
        "[project.optional-dependencies]",
    ]
    toml += [f"{key} = {json.dumps(value)}" for key, value in optional.items()]
    toml += [
        "[build-system]",
        'requires = ["setuptools>=77"]',
        'build-backend = "setuptools.build_meta"',
        "[tool.setuptools.packages.find]",
        'where = ["src"]',
        "[tool.pytest.ini_options]",
        'testpaths = ["tests"]',
    ]
    (destination / "pyproject.toml").write_text(
        "\n".join(toml) + "\n", encoding="utf-8"
    )
    reduced = {**manifest, "profiles": {profile: selected}}
    (destination / "template-manifest.json").write_text(
        json.dumps(reduced, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    readme = f"# PaperTemplate: {profile}\n\n独立项目，包含公共核心和当前方向源码。\n\n```powershell\nuv sync --extra dev\nuv run paper validate configs/studies/{profile}.yaml\nuv run paper run configs/studies/{profile}.yaml\nuv run pytest\n```\n\n修改 `src/project/{profile}.py` 接入自己的组件。接口和配置见 [文档](docs/README.md) 与 [方向指南](docs/profiles/{profile}.md)。\n"
    (destination / "README.md").write_text(readme, encoding="utf-8")
    for name in ("README.md", "pyproject.toml", "template-manifest.json"):
        hashes[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    (destination / "export-manifest.json").write_text(
        json.dumps(
            {"profile": profile, "files": hashes, "schema_version": 2}, indent=2
        ),
        encoding="utf-8",
    )
    return destination
