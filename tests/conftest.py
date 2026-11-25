from __future__ import annotations

import pytest

from infra_defense import pipeline as P
from infra_defense.config import FIXTURE_DIR, load_config
from infra_defense.data.io import load_bundle


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def bundle():
    return load_bundle(FIXTURE_DIR)


@pytest.fixture(scope="session")
def prepared(bundle, cfg):
    return P.prepare(bundle, cfg)


@pytest.fixture(scope="session")
def fitted(prepared, tmp_path_factory):
    return P.fit(prepared, tmp_path_factory.mktemp("run"))


@pytest.fixture(scope="session")
def replayed(prepared, fitted, tmp_path_factory):
    return P.replay(prepared, fitted, tmp_path_factory.mktemp("replay"))
