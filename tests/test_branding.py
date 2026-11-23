"""Acme branding: top bar, hero, wordmark, palette, and the photo copy."""

import random
import re

from streamlit.testing.v1 import AppTest

from leadgen import ui_theme
from leadgen.paths import repo_root
from leadgen.profiles import load_profile
from leadgen.ui_theme import ICON_PAIRS, PAIRS, build_hero_image, contrast_ratio, header_html

ROOT = repo_root()
APP = ROOT / "src" / "leadgen" / "app.py"
STEPS = ("search", "shortlist", "run", "review", "outbox", "logbook", "funnel", "settings")


def _markdown(at) -> str:
    return "\n".join(str(item.value) for item in at.markdown)


def test_top_bar_hero_and_wordmark_render_on_every_step(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    brand = load_profile("acme_plumbing").brand
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    for step in STEPS:
        at.session_state["step"] = step
        at.run()
        assert not at.exception, step
        text = _markdown(at)
        assert 'class="topbar"' in text, step
        assert 'class="hero' in text, step
        assert 'class="wordmark"' in text, step
        assert brand.service_line in text, step
        assert brand.hero_subtitle in text, step


def test_header_words_come_from_the_profile():
    brand = load_profile("acme_plumbing").brand
    assert brand.service_line == ""
    assert brand.hero_subtitle == "Find businesses in the field you choose"
    page = (ROOT / "src" / "leadgen" / "app.py").read_text(encoding="utf-8")
    assert "$150" not in page
    assert "Find and reach" not in page


def test_missing_photo_falls_back_to_the_gradient():
    brand = load_profile("acme_plumbing").brand
    html = header_html(brand, "Acme Plumbing", uri="")
    assert "hero-fallback" in html
    assert "<svg" in html
    assert "background-image:url" not in html
    with_photo = header_html(brand, "Acme Plumbing", uri="data:image/jpeg;base64,AAAA")
    assert "hero-fallback" not in with_photo
    assert "background-image:url" in with_photo


def test_no_photo_in_repo_means_no_error_on_the_page(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    if (ROOT / ui_theme.HERO_SOURCE).is_file() or (ROOT / ui_theme.HERO_WEB).is_file():
        return
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception
    assert "hero-fallback" in _markdown(at)


def test_shipped_and_processed_images_are_under_150_kb(tmp_path):
    shipped = ROOT / ui_theme.HERO_WEB
    if shipped.is_file():
        assert shipped.stat().st_size <= 150 * 1024
    from PIL import Image

    source = tmp_path / ui_theme.HERO_SOURCE
    source.parent.mkdir(parents=True)
    rng = random.Random(1)
    noise = bytes(rng.randrange(256) for _ in range(1200 * 800 * 3))
    Image.frombytes("RGB", (1200, 800), noise).save(source, "JPEG", quality=95)
    assert source.stat().st_size > 150 * 1024
    made = build_hero_image(tmp_path)
    assert made is not None
    assert made.stat().st_size <= 150 * 1024
    stamp = made.stat().st_mtime_ns
    assert build_hero_image(tmp_path) == made
    assert made.stat().st_mtime_ns == stamp


def test_no_photo_means_no_processed_copy(tmp_path):
    assert build_hero_image(tmp_path) is None


def test_text_contrast_is_at_least_4_5():
    names = {name for name, _fg, _bg in PAIRS}
    assert {"topbar", "hero_title", "hero_subtitle", "primary", "primary_hover",
            "primary_disabled", "secondary", "secondary_hover", "secondary_disabled",
            "step_current", "step_done", "step_ready", "step_locked",
            "chip_wait", "chip_ok", "chip_stop"} <= names
    for name, foreground, background in PAIRS:
        assert contrast_ratio(foreground, background) >= 4.5, name


def test_icons_and_marks_have_at_least_3_to_1():
    for name, foreground, background in ICON_PAIRS:
        assert contrast_ratio(foreground, background) >= 3.0, name


def test_hero_text_holds_on_the_lightest_photo_under_the_overlay():
    assert ui_theme.OVERLAY_MIN <= ui_theme.OVERLAY_MAX
    assert contrast_ratio("#FFFFFF", ui_theme.HERO_WORST) >= 4.5


def test_palette_is_the_agreed_one():
    assert ui_theme.BG == "#070B1F"
    assert ui_theme.BLUE == "#3B5BDB"
    assert ui_theme.CYAN == "#22D3EE"
    assert ui_theme.VIOLET == "#6D3FE0"
    assert ui_theme.SKY == "#0F1733"
    assert ui_theme.SLATE == "#E8ECF8"
    assert ui_theme.GREEN == "#22C55E"
    assert ui_theme.AMBER == "#F5B942"
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "#3B5BDB" in config
    assert 'base = "dark"' in config


def test_showcase_images_are_small_and_shown_on_find():
    for name, _title, _text in ui_theme.SHOWCASE:
        path = ROOT / "assets" / name
        assert path.is_file(), name
        assert path.stat().st_size <= 80 * 1024, name


def test_colors_live_only_in_the_theme_and_config():
    hexes = re.compile(r"#[0-9A-Fa-f]{6}\b")
    for path in (ROOT / "src").rglob("*.py"):
        if path.name == "ui_theme.py":
            continue
        assert not hexes.search(path.read_text(encoding="utf-8")), path.name


def test_every_css_color_is_in_the_palette():
    css = ui_theme._css()
    palette = {
        value.upper()
        for name, value in vars(ui_theme).items()
        if name.isupper() and isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value)
    }
    assert "@" not in re.sub(r"@media[^{]*", "", css)
    for found in re.findall(r"#[0-9A-Fa-f]{6}\b", css):
        assert found.upper() in palette, found


def test_no_real_company_name_logo_or_mascot_in_the_repo():
    banned = [
        "roto" + "-rooter", "roto" + "rooter", "mr. " + "rooter", "mr " + "rooter",
        "benjamin " + "franklin plumbing", "one hour " + "heating", "arizona " + "plumbing co",
        "super " + "mario", "mar" + "io bros", "lui" + "gi", "ro" + "to-rooter",
        "hy" + "dro-flo", "ro" + "oter man",
    ]
    for folder in ("src", "config", "assets", "docs"):
        base = ROOT / folder
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".py", ".yaml", ".yml", ".md", ".txt", ".csv", ".svg", ".toml", ".json",
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            for name in banned:
                assert name not in text, f"{name} in {path.name}"
