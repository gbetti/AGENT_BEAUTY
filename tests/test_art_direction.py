import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from catalog import ROOT, load_products
from editorial import campaign_plan
from studio import render_campaign


class ArtDirectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.products = load_products(self.root/'catalog.sqlite')
        self.shampoo = next(p for p in self.products if p['id'].endswith(':shampooing-soin-hydratant-anti-casse'))

    def test_automatic_rotation_and_actual_background_hashes_do_not_repeat(self):
        history = []
        modes, backgrounds = [], []
        for _ in range(9):
            plan = campaign_plan(self.shampoo, history, products=self.products)
            modes.append(plan['content_mode'])
            backgrounds.append(plan['scene']['design']['background_sha256'])
            history.insert(0, {'product_id': self.shampoo['id'], 'creative': plan})
        self.assertEqual(modes, ['product', 'model', 'pack']*3)
        self.assertEqual(len(set(backgrounds)), 9)
        self.assertTrue(all(p['id'].endswith((':shampooing-soin-hydratant-anti-casse', ':apres-shampooing-reparateur'))
                            for p in history[0]['creative']['scene']['design']['products']))

    def test_pack_rejects_unknown_or_incompatible_products(self):
        for key in ('unknown', 'creme-sublime-revitalisante', 'shampooing-soin-hydratant-anti-casse'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Pack'):
                campaign_plan(self.shampoo, [], mode='pack', products=self.products, pack_keys=[key])

    def test_three_layouts_preserve_source_assets_and_all_native_sizes(self):
        source = Path(self.shampoo['images'][0]['path'])
        before = source.read_bytes()
        ingredients = json.loads((ROOT/'assets/ingredients.json').read_text())['shampooing-soin-hydratant-anti-casse']
        for mode in ('product', 'model', 'pack'):
            plan = campaign_plan(self.shampoo, [], mode=mode, products=self.products)
            copy = plan['copies']['it']; copy['ingredients'] = ingredients
            folder = self.root/mode; folder.mkdir()
            result = render_campaign(self.shampoo, copy, folder, plan['scene'])
            for kind, info in result.items():
                with self.subTest(mode=mode, kind=kind):
                    elements = info['elements']
                    self.assertEqual(sum(e['kind'] == 'model' for e in elements), int(mode == 'model'))
                    self.assertEqual(sum(e['kind'] == 'product' for e in elements), 2 if mode == 'pack' else 1)
                    self.assertTrue(info['path'].is_file())
                    self.assertLess(info['text_area_ratio'], .2)
                    self.assertTrue(all(e.get('contrast_ratio', 4.5) >= 4.5 for e in elements))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), hashlib.sha256(before).hexdigest())


if __name__ == '__main__':
    unittest.main()
