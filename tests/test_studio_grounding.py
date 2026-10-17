import unittest

from PIL import Image, ImageChops, ImageDraw, ImageStat

from studio import background_plate, check_copy_space, shadow_and_product
from weekly import extract_inci


class StudioGroundingTests(unittest.TestCase):
    def test_shadow_follows_light_and_transparent_padding_does_not_lift_product(self):
        photo=Image.new('RGBA',(80,160))
        ImageDraw.Draw(photo).rectangle((20,10,59,139),fill=(180,180,180,255))
        results=[]
        for direction in (-.3,.3):
            canvas=Image.new('RGBA',(320,300),'white')
            info=shadow_and_product(canvas,photo,160,200,(40,130),
                {'cast_direction':[direction,.12],'color':[40,40,40]})
            self.assertEqual(info['box'],[140,70,180,200])
            self.assertLess(min(canvas.getpixel((160,200))[:3]),230)
            darkness=ImageChops.invert(canvas.convert('RGB'))
            # Farther from the base, the projected silhouette follows the light.
            left=ImageStat.Stat(darkness.crop((90,203,140,225))).mean[0]
            right=ImageStat.Stat(darkness.crop((180,203,230,225))).mean[0]
            results.append((left,right))
        self.assertGreater(results[0][0],results[0][1])
        self.assertGreater(results[1][1],results[1][0])

    def test_busy_background_is_rejected_even_with_high_contrast(self):
        plate=Image.new('RGB',(100,100),'white')
        draw=ImageDraw.Draw(plate)
        for x in range(0,100,4): draw.rectangle((x,0,x+1,99),fill=(180,180,180))
        elements=[{'kind':'headline','box':[10,10,90,90]}]
        with self.assertRaisesRegex(ValueError,'dettagliato'):
            check_copy_space(plate,elements,3)
        self.assertEqual(check_copy_space(Image.new('RGB',(100,100),'white'),elements,3),0)

    def test_floor_is_preserved_in_tall_story_crop(self):
        scene={'format_crops':{'story':[0,.3,1,1]},'floor_start':.78,
               'lighting':{'cast_direction':[.22,.07]}}
        image,placement=background_plate(Image.new('RGB',(1024,1536),'white'),
                                          scene,'story',(1080,1920))
        self.assertEqual(image.size,(1080,1920))
        self.assertLess(placement['floor_start_y'],1400-1920*.025)


class InciBoundaryTests(unittest.TestCase):
    def test_fragrance_free_inci_stops_before_reviews_and_related_products(self):
        text='Composition WATER (AQUA), GLYCERIN, TOCOPHEROL, POTASSIUM HYDROXIDE. Related: CERAMIDE NP, PARFUM (FRAGRANCE)'
        inci=extract_inci(text)
        self.assertIn('POTASSIUM HYDROXIDE',inci)
        self.assertNotIn('CERAMIDE NP',inci)

    def test_legacy_fragranced_formula_and_unbounded_text(self):
        self.assertIn('GLYCERIN',extract_inci('AQUA (WATER), GLYCERIN, PARFUM (FRAGRANCE) More text'))
        with self.assertRaises(ValueError): extract_inci('WATER (AQUA), GLYCERIN')


if __name__=='__main__':
    unittest.main()
