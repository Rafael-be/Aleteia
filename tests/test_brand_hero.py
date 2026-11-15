from pathlib import Path
import unittest

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "public"


class BrandHeroTemplateTest(unittest.TestCase):
    def setUp(self):
        self.environment = Environment(loader=FileSystemLoader(TEMPLATES))
        self.environment.globals["url_for"] = lambda endpoint, **kwargs: f"/{kwargs.get('filename', endpoint)}"

    def test_component_renders_home_and_extension_variants(self):
        template = self.environment.get_template("components/brand-hero.html")
        home = template.render(
            brand_hero_class="brand-hero--home home-brand",
            brand_hero_eyebrow="Bem-vindo à",
            brand_hero_label=None,
            brand_hero_title_id=None,
            brand_hero_logo_alt="ALETEIA",
        )
        extension = template.render(
            brand_hero_class="extension-brand",
            brand_hero_eyebrow="Seu chat, ao lado de qualquer leitura",
            brand_hero_label="Extensão para o navegador",
            brand_hero_title_id="extension-title",
            brand_hero_logo_alt="Símbolo da AleteIA",
        )

        self.assertIn('<p class="brand-hero-eyebrow">Bem-vindo à</p>', home)
        self.assertIn('<div class="brand-hero-main">', home)
        self.assertIn('<h1 class="brand-hero-title">', home)
        self.assertIn('id="extension-title" class="brand-hero-title"', extension)
        self.assertIn('Extensão para o navegador', extension)
        eyebrow_start = extension.index('<p class="brand-hero-eyebrow">')
        main_start = extension.index('<div class="brand-hero-main">')
        label_start = extension.index('<p class="brand-hero-label">')
        main_close = extension.rfind('</div>', 0, label_start)
        self.assertLess(eyebrow_start, main_start, "o texto superior não deve expandir a linha título + logo")
        self.assertLess(main_close, label_start, "o label não deve expandir a linha título + logo")

    def test_pages_include_the_shared_component(self):
        home = (TEMPLATES / "main" / "main-desktop.html").read_text(encoding="utf-8")
        extension = (TEMPLATES / "extensao" / "extensao.html").read_text(encoding="utf-8")

        self.assertIn('components/brand-hero.html', home)
        self.assertIn('components/brand-hero.html', extension)
        self.assertIn("Bem-vindo à", home)


if __name__ == "__main__":
    unittest.main()
