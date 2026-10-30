"""Offline source-derived contracts, not execution of the upstream host."""
import json
import copy
import hashlib
import re
import stat
import unittest
from pathlib import Path

import torch

try:
    from host_contracts import host_matrix, host_tiers, replay_output, assert_custom_ui_preserved
    from test_host_compatibility_contracts import PackageImportContext
    from test_publish_candidate import _zip_bytes
except ModuleNotFoundError:
    from tests.host_contracts import host_matrix, host_tiers, replay_output, assert_custom_ui_preserved
    from tests.test_host_compatibility_contracts import PackageImportContext
    from tests.test_publish_candidate import _zip_bytes

from scripts import validate_publish_candidate as candidate

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def _fixture_sha256(payload: bytes) -> str:
    # IMPORTANT: Git may check out CRLF or LF; raw-byte hashes break Linux CI.
    # Normalize only CRLF, so whitespace, lone CR and content edits still fail.
    return hashlib.sha256(payload.replace(b'\r\n', b'\n')).hexdigest()


class CurrentHostContractsTests(unittest.TestCase):
    def test_fixture_digest_is_checkout_portable_but_detects_non_newline_edits(self):
        for name, digest in host_matrix()['historical_fixtures_sha256'].items():
            lf = (FIXTURES / name).read_bytes().replace(b'\r\n', b'\n')
            for variant in (lf, lf.replace(b'\n', b'\r\n')):
                with self.subTest(fixture=name, line_ending='CRLF' if b'\r\n' in variant else 'LF'):
                    self.assertEqual(digest['sha256'], _fixture_sha256(variant))
            for edited in (lf + b' ', lf.replace(b'\n', b'\r', 1), b'!' + lf[1:]):
                with self.subTest(fixture=name, mutation=edited[:20]):
                    self.assertNotEqual(_fixture_sha256(lf), _fixture_sha256(edited))

    def test_active_observations_distinguish_declared_and_independent_frontend(self):
        path = FIXTURES / 'host_compatibility_matrix_v1.json'
        self.assertTrue(path.exists(), 'active source matrix is missing; old current tiers cannot describe updated sources')
        matrix = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(
            ['desktop_floor', 'core_declared_frontend', 'independent_frontend_head'],
            [tier['id'] for tier in matrix['tiers']],
        )
        self.assertNotEqual(matrix['tiers'][1]['frontend']['commit'], matrix['tiers'][2]['frontend']['commit'])
        self.assertEqual(matrix['tiers'][1]['core']['declared_frontend_version'], matrix['tiers'][1]['frontend']['version'])
        self.assertFalse(matrix['host_execution_verified'])

    def test_source_identity_and_historical_fixture_integrity(self):
        matrix = host_matrix()
        self.assertEqual('source_derived_contract', matrix['evidence_kind'])
        self.assertEqual('sha256-crlf-to-lf', matrix['historical_fixtures_hash_format'])
        for tier in host_tiers():
            for source in (tier['core'], tier['frontend']):
                self.assertRegex(source['commit'], r'^[0-9a-f]{40}$')
                self.assertTrue(source['sources'])
                for path, pin in source['sources'].items():
                    self.assertEqual(source['commit'], pin['commit'])
                    self.assertRegex(pin['blob'], r'^[0-9a-f]{40}$')
                    self.assertTrue(pin['url'].endswith(f"/blob/{source['commit']}/{path}"))
                    self.assertTrue(pin['url'].startswith('https://github.com/Comfy-Org/'))
        self.assertEqual(14, matrix['tiers'][1]['core']['post_release_commits'])
        self.assertEqual(108, matrix['tiers'][2]['frontend']['post_release_commits'])
        for name, digest in matrix['historical_fixtures_sha256'].items():
            with self.subTest(fixture=name):
                self.assertEqual(digest["sha256"], _fixture_sha256((FIXTURES / name).read_bytes()))
        text = json.dumps(matrix)
        self.assertIsNone(re.search(r'(?i)\.planning|reference/docs|[A-Z]:\\|/home/', text))

    def test_current_help_and_v1_decision_are_source_pinned(self):
        matrix = host_matrix()
        contract = matrix['contracts']
        self.assertEqual('DEFER_PRODUCTION', contract['decision'])
        self.assertFalse(contract['v0_0_2_stable'])
        self.assertEqual('V1_BEFORE_V3', contract['loader_precedence'])
        tiers = matrix['tiers']
        help_blobs = {tier['frontend']['sources']['src/services/nodeHelpService.ts']['blob'] for tier in tiers}
        self.assertEqual(3, len(help_blobs))
        shim_blobs = {tier['core']['sources']['comfy_api/v0_0_2/__init__.py']['blob'] for tier in tiers}
        self.assertEqual(1, len(shim_blobs))
        self.assertEqual('/extensions/{module}/docs/{node_id}/{locale}.md', contract['localized_lookup'])
        self.assertEqual('/extensions/{module}/docs/{node_id}.md', contract['fallback_lookup'])

    def test_real_product_outputs_survive_additive_fresh_and_cache_contract(self):
        with PackageImportContext() as package:
            saver = package.NODE_CLASS_MAPPINGS['AdvancedImageSaver']()
            mask = package.NODE_CLASS_MAPPINGS['TP_SaveMask']()
            resolution = package.NODE_CLASS_MAPPINGS['TP_AdvancedResolutionSelector']()
            saved = saver.save_images(torch.zeros((1, 2, 2, 3)), output_path='.', metadata_mode='none', embed_workflow='false')
            masked = mask.save_mask(torch.zeros((1, 2, 2)))
            resolved = resolution.select_resolution('fixed', '16:9', 'landscape', 1, 1, 1.0, 8, 0)
            root = Path(saver.output_dir)
            for product in (saved, masked):
                ui = {**product['ui'], **resolved['ui']}
                frozen = copy.deepcopy(ui)
                for assets in (False, True):
                    for cached in (False, True):
                        with self.subTest(assets=assets, cached=cached):
                            result = replay_output(ui, root, assets_enabled=assets, cached=cached)
                            assert_custom_ui_preserved(ui, result)
                            self.assertEqual(ui['images'][0]['filename'], result['images'][0]['filename'])
                            self.assertEqual(assets, 'id' in result['images'][0])
                self.assertEqual(frozen, ui)
                broken = copy.deepcopy(ui)
                broken.pop('tp_advanced_resolution')
                with self.assertRaisesRegex(AssertionError, 'custom UI lost'):
                    assert_custom_ui_preserved(ui, broken)
                for field, value in [('filename', '../outside.png'), ('type', 'unknown'), ('subfolder', '../')]:
                    broken = copy.deepcopy(ui)
                    broken['images'][0][field] = value
                    with self.assertRaises(AssertionError):
                        replay_output(broken, root, assets_enabled=True)
                broken = copy.deepcopy(ui)
                broken['images'][0].pop('filename')
                with self.assertRaisesRegex(AssertionError, 'missing legacy'):
                    replay_output(broken, root, assets_enabled=False)
                enriched = replay_output(ui, root, assets_enabled=True)
                stale = copy.deepcopy(enriched)
                stale['images'][0].update(id='stale', preview_id='stale')
                replayed = replay_output(stale, root, assets_enabled=False, cached=True)
                self.assertNotIn('id', replayed['images'][0])
                self.assertNotIn('preview_id', replayed['images'][0])

    def test_archive_negative_controls_for_internal_and_bytecode_members(self):
        expected = [candidate.TrackedPath('module.py', candidate.REGULAR_FILE_MODE)]
        entry = ('module.py', b'# public module\n', stat.S_IFREG | 0o644)
        self.assertEqual(1, candidate.verify_archive_bytes(_zip_bytes([entry]), expected).member_count)
        for name in ('.planning/notes.md', 'reference/host.py', '__pycache__/module.pyc', 'prototype.py'):
            with self.subTest(name=name), self.assertRaises(candidate.CandidateError):
                candidate.verify_archive_bytes(_zip_bytes([entry, (name, b'x', stat.S_IFREG | 0o644)]), expected)
