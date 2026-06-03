"""
calculator/static/test_style_css.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validation tests for calculator/static/style.css.

Tests cover:
- CSS file existence
- CSS custom properties (variables)
- CSS selectors for key elements
- Responsive design media queries
"""

import os
import re
import pytest


@pytest.fixture
def css_file_path():
    """Get the path to the CSS file."""
    return os.path.join(
        os.path.dirname(__file__),
        "style.css"
    )


@pytest.fixture
def css_content(css_file_path):
    """Read and return the CSS file content."""
    with open(css_file_path, "r", encoding="utf-8") as f:
        return f.read()


class TestCSSFileStructure:
    """Test the structure and presence of the CSS file."""

    def test_css_file_exists(self, css_file_path):
        """Test that style.css file exists."""
        assert os.path.exists(css_file_path), "style.css file not found"

    def test_css_file_is_readable(self, css_file_path):
        """Test that style.css is readable."""
        assert os.access(css_file_path, os.R_OK), "style.css is not readable"

    def test_css_file_not_empty(self, css_content):
        """Test that CSS file is not empty."""
        assert len(css_content.strip()) > 0, "CSS file is empty"


class TestCSSVariables:
    """Test CSS custom properties (variables)."""

    def test_root_selector_exists(self, css_content):
        """Test that :root selector is defined."""
        assert ":root" in css_content

    def test_background_color_variable(self, css_content):
        """Test that --bg variable is defined."""
        assert "--bg:" in css_content or "--bg :" in css_content

    def test_text_color_variable(self, css_content):
        """Test that --text variable is defined."""
        assert "--text:" in css_content or "--text :" in css_content

    def test_accent_color_variable(self, css_content):
        """Test that --accent variable is defined."""
        assert "--accent:" in css_content or "--accent :" in css_content

    def test_equals_color_variable(self, css_content):
        """Test that --equals variable is defined."""
        assert "--equals:" in css_content or "--equals :" in css_content

    def test_border_radius_variable(self, css_content):
        """Test that --radius variable is defined."""
        assert "--radius:" in css_content or "--radius :" in css_content

    def test_transition_variable(self, css_content):
        """Test that --transition variable is defined."""
        assert "--transition:" in css_content or "--transition :" in css_content


class TestCSSSelectors:
    """Test presence of required CSS selectors."""

    def test_body_selector(self, css_content):
        """Test that body selector is defined."""
        assert "body" in css_content

    def test_calculator_class_selector(self, css_content):
        """Test that .calculator selector is defined."""
        assert ".calculator" in css_content

    def test_display_class_selector(self, css_content):
        """Test that .display selector is defined."""
        assert ".display" in css_content

    def test_button_grid_class_selector(self, css_content):
        """Test that .btn-grid selector is defined."""
        assert ".btn-grid" in css_content

    def test_button_class_selector(self, css_content):
        """Test that button selector is defined."""
        assert "button" in css_content

    def test_operator_button_selector(self, css_content):
        """Test that button.operator selector is defined."""
        assert "button.operator" in css_content

    def test_equals_button_selector(self, css_content):
        """Test that button.equals selector is defined."""
        assert "button.equals" in css_content

    def test_clear_button_selector(self, css_content):
        """Test that button.clear selector is defined."""
        assert "button.clear" in css_content


class TestCSSProperties:
    """Test presence of important CSS properties."""

    def test_flex_centering(self, css_content):
        """Test that flex centering is used for body."""
        assert "display: flex" in css_content
        assert "align-items: center" in css_content
        assert "justify-content: center" in css_content

    def test_grid_layout(self, css_content):
        """Test that grid layout is used for button grid."""
        assert "display: grid" in css_content
        assert "grid-template-columns" in css_content

    def test_backdrop_filter(self, css_content):
        """Test that backdrop filter is used for glassmorphism."""
        assert "backdrop-filter" in css_content

    def test_transition_property(self, css_content):
        """Test that transitions are defined."""
        assert "transition:" in css_content

    def test_hover_state(self, css_content):
        """Test that :hover pseudo-class is defined."""
        assert ":hover" in css_content

    def test_active_state(self, css_content):
        """Test that :active pseudo-class is defined."""
        assert ":active" in css_content


class TestCSSResponsive:
    """Test responsive design media queries."""

    def test_media_query_exists(self, css_content):
        """Test that media query is defined."""
        assert "@media" in css_content

    def test_mobile_breakpoint(self, css_content):
        """Test that mobile breakpoint is defined."""
        assert "max-width: 380px" in css_content or "max-width" in css_content

    def test_responsive_width(self, css_content):
        """Test that responsive width is defined."""
        assert "vw" in css_content or "%" in css_content


class TestCSSBoxModel:
    """Test CSS box model properties."""

    def test_box_sizing_reset(self, css_content):
        """Test that box-sizing is reset."""
        assert "box-sizing: border-box" in css_content

    def test_padding_defined(self, css_content):
        """Test that padding is used."""
        assert "padding" in css_content

    def test_margin_reset(self, css_content):
        """Test that margins are reset."""
        assert "margin: 0" in css_content

    def test_border_radius_used(self, css_content):
        """Test that border-radius is used."""
        assert "border-radius" in css_content


class TestCSSColor:
    """Test CSS color usage."""

    def test_rgba_colors_used(self, css_content):
        """Test that rgba colors are used for transparency."""
        assert "rgba(" in css_content

    def test_hex_colors_used(self, css_content):
        """Test that hex colors are used."""
        # Should have at least one hex color code
        hex_pattern = r"#[0-9a-fA-F]{3,8}"
        assert re.search(hex_pattern, css_content)

    def test_color_property(self, css_content):
        """Test that color property is used."""
        assert "color:" in css_content

    def test_background_property(self, css_content):
        """Test that background property is used."""
        assert "background" in css_content


class TestCSSFontStyling:
    """Test font-related CSS properties."""

    def test_font_family_defined(self, css_content):
        """Test that font-family is defined."""
        assert "font-family:" in css_content

    def test_font_size_defined(self, css_content):
        """Test that font-size is used."""
        assert "font-size:" in css_content

    def test_font_weight_defined(self, css_content):
        """Test that font-weight is used."""
        assert "font-weight:" in css_content


class TestCSSLayout:
    """Test layout-related properties."""

    def test_min_height_defined(self, css_content):
        """Test that min-height is used."""
        assert "min-height:" in css_content

    def test_display_property_used(self, css_content):
        """Test that display property is used."""
        assert "display:" in css_content

    def test_gap_property_used(self, css_content):
        """Test that gap property is used for spacing."""
        assert "gap:" in css_content


class TestCSSComments:
    """Test CSS documentation."""

    def test_comments_present(self, css_content):
        """Test that CSS has comments for documentation."""
        assert "/*" in css_content
        assert "*/" in css_content

    def test_section_comments(self, css_content):
        """Test that section comments are present."""
        # Should have at least one long comment section
        assert "---" in css_content or "=" in css_content
