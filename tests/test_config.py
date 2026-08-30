import shutil
from pathlib import Path

import pytest
import yaml

from domain_guard.config import ConfigurationError, load_config


ROOT = Path(__file__).resolve().parents[1]


def isolated_config(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(ROOT / "config", project / "config")
    path = project / "config" / "filter_config.yaml"
    return path, yaml.safe_load(path.read_text(encoding="utf-8"))


def test_threshold_is_loaded_from_configuration(tmp_path):
    path, values = isolated_config(tmp_path)
    values["thresholds"]["min_in_scope_score"] = 4321
    path.write_text(yaml.safe_dump(values, sort_keys=False, allow_unicode=True), encoding="utf-8")
    assert load_config(path).section("thresholds")["min_in_scope_score"] == 4321


def test_unknown_configuration_key_is_rejected(tmp_path):
    path, values = isolated_config(tmp_path)
    values["thresholds"]["hidden_cutoff"] = 9999
    path.write_text(yaml.safe_dump(values, sort_keys=False, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(path)
