"""Adversarial public-data intake and test harness checks, no service connections."""
import datetime as dt
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

from traluat.tools.forms import FormField, validate_form
from traluat.tools.reference import _CONTRACTS, RefRow, _validate
from traluat.tools.templates import TemplateQuarantined, add_template


def test_unreviewed_and_tenant_templates_rejected_before_embed():
    session, embedder = Mock(), Mock()
    for kwargs in ({}, {'public_reviewed': True, 'provenance': 'tenant:secret'}):
        with pytest.raises(TemplateQuarantined):
            add_template(session, 'x', 'Blank public form', 'Hello {name}', embedder=embedder, **kwargs)
    session.add.assert_not_called()
    embedder.embed.assert_not_called()


@pytest.mark.parametrize('kwargs', [
    {'body': 'CCCD 012345678901'}, {'title': 'Call 0912345678'},
    {'slots': [{'name': 'x', 'label': 'private@example.com'}]},
])
def test_template_pii_in_all_metadata_rejected_before_embed(kwargs):
    args = {'kind': 'x', 'title': 'Public blank form', 'body': 'Name: {x}', 'slots': ['x']}
    args.update(kwargs)
    session, embedder = Mock(), Mock()
    with pytest.raises(TemplateQuarantined):
        add_template(session, **args, public_reviewed=True, embedder=embedder)
    session.add.assert_not_called()
    embedder.embed.assert_not_called()


@pytest.mark.parametrize('dataset,value', [
    ('thue_gtgt', {'rate': -0.1}), ('thue_gtgt', {'rate': 8}),
    ('thue_gtgt', {'rate': float('nan')}), ('muc_phat', {'muc': -1}),
    ('bieu_thue_tncn', {'brackets': [[10, .1], [5, .2], [None, .3]]}),
    ('thoi_hieu', {'value': -1, 'unit': 'day'}),
    ('thoi_hieu', {'value': 1, 'unit': 'century'}),
    ('ngay_nghi', {'dates': ['2025-02-31']}),
])
def test_invalid_reference_values_never_touch_store(dataset, value):
    session = Mock()
    with pytest.raises((ValueError, TypeError)):
        _validate(session, _CONTRACTS[dataset], RefRow('2025', value, dt.date(2025, 1, 1)))
    session.execute.assert_not_called()
    session.scalar.assert_not_called()


def test_string_pii_checked_even_in_numeric_contract():
    with pytest.raises(ValueError, match='personal data'):
        _validate(Mock(), _CONTRACTS['muc_phat'], RefRow(
            'x', {'muc': 100000000000, 'note': 'private@example.com'}, dt.date(2025, 1, 1),
            source_eid='synthetic-source'))


def test_form_numbers_must_be_finite_and_patterns_bounded():
    assert validate_form([{'name': 'amount', 'type': 'number'}], {'amount': 'NaN'})
    with pytest.raises(ValueError):
        FormField.parse({'name': 'name', 'pattern': '(a+)+$'})
    with pytest.raises(ValueError):
        FormField.parse({'name': 'name', 'pattern': 'a{0,999}a{0,999}a{0,999}'})


def _harness():
    spec = importlib.util.spec_from_file_location('isolated_test_harness', Path(__file__).with_name('conftest.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_harness_does_not_infer_test_target_from_dev_url(monkeypatch):
    module = _harness()
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://private@localhost/production')
    monkeypatch.delenv('TEST_DATABASE_URL', raising=False)
    monkeypatch.delenv('REQUIRE_TEST_DATABASE', raising=False)
    migrate = Mock()
    monkeypatch.setattr(module, '_migrate', migrate)
    module.pytest_configure(None)
    import os
    assert os.environ['DATABASE_URL'] == module._DISABLED_URL
    migrate.assert_not_called()


def test_harness_rejects_dev_database_and_migration_failure(monkeypatch):
    module = _harness()
    import os
    monkeypatch.setenv('DATABASE_URL', os.environ.get('DATABASE_URL', module._DISABLED_URL))
    monkeypatch.setenv('TEST_DATABASE_URL', 'postgresql+psycopg://private@localhost/traluat')
    with pytest.raises(pytest.UsageError):
        module.pytest_configure(None)
    monkeypatch.setenv('TEST_DATABASE_URL', 'postgresql+psycopg://private@localhost/traluat_test')
    monkeypatch.setattr(module, '_migrate', Mock(side_effect=RuntimeError('synthetic migration failure')))
    with pytest.raises(pytest.UsageError):
        module.pytest_configure(None)
    assert os.environ['DATABASE_URL'] == module._DISABLED_URL


def test_seed_scripts_import_without_connecting():
    for filename in ('seed_deadlines.py', 'seed_directory.py'):
        path = Path(__file__).parents[1] / 'scripts' / filename
        spec = importlib.util.spec_from_file_location('import_only_' + filename[:-3], path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert callable(module.seed)
