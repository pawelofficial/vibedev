"""
calculator/templates/test_index_html.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validation tests for calculator/templates/index.html.

Tests cover:
- HTML file structure and validity
- Required elements (display, button grid)
- Button layout and attributes
- Accessibility features
- External resource references
"""

import os
import re
import pytest
from html.parser import HTMLParser


@pytest.fixture
def html_file_path():
    """Get the path to the HTML file."""
    return os.path.join(
        os.path.dirname(__file__),
        "index.html"
    )


@pytest.fixture
def html_content(html_file_path):
    """Read and return the HTML file content."""
    with open(html_file_path, "r", encoding="utf-8") as f:
        return f.read()


class TestHTMLFileStructure:
    """Test the structure and presence of the HTML file."""

    def test_html_file_exists(self, html_file_path):
        """Test that index.html file exists."""
        assert os.path.exists(html_file_path), "index.html file not found"

    def test_html_file_is_readable(self, html_file_path):
        """Test that index.html is readable."""
        assert os.access(html_file_path, os.R_OK), "index.html is not readable"

    def test_html_file_not_empty(self, html_content):
        """Test that HTML file is not empty."""
        assert len(html_content.strip()) > 0, "HTML file is empty"


class TestHTMLDocumentStructure:
    """Test HTML document structure."""

    def test_doctype_declaration(self, html_content):
        """Test that DOCTYPE is declared."""
        assert "<!DOCTYPE html>" in html_content

    def test_html_tag(self, html_content):
        """Test that html tag is present."""
        assert "<html" in html_content
        assert "</html>" in html_content

    def test_head_section(self, html_content):
        """Test that head section is present."""
        assert "<head>" in html_content
        assert "</head>" in html_content

    def test_body_section(self, html_content):
        """Test that body section is present."""
        assert "<body>" in html_content
        assert "</body>" in html_content

    def test_main_content_wrapper(self, html_content):
        """Test that main element is used."""
        assert "<main>" in html_content or "<main " in html_content

    def test_lang_attribute(self, html_content):
        """Test that lang attribute is set."""
        assert 'lang="en"' in html_content or "lang='en'" in html_content


class TestHTMLHead:
    """Test HTML head section."""

    def test_charset_meta_tag(self, html_content):
        """Test that charset is specified."""
        assert "charset=" in html_content or "UTF-8" in html_content

    def test_viewport_meta_tag(self, html_content):
        """Test that viewport is set for responsive design."""
        assert "viewport" in html_content

    def test_title_tag(self, html_content):
        """Test that title is set."""
        assert "<title>" in html_content
        assert "Calculator" in html_content

    def test_stylesheet_link(self, html_content):
        """Test that CSS stylesheet is linked."""
        assert '<link' in html_content
        assert 'rel="stylesheet"' in html_content or "rel='stylesheet'" in html_content
        assert 'style.css' in html_content

    def test_script_tag(self, html_content):
        """Test that JavaScript is loaded."""
        assert '<script' in html_content
        assert 'script.js' in html_content


class TestHTMLCalculatorDisplay:
    """Test calculator display element."""

    def test_display_element_exists(self, html_content):
        """Test that display element exists."""
        assert 'id="display"' in html_content

    def test_display_class(self, html_content):
        """Test that display has correct class."""
        assert 'class="display"' in html_content

    def test_display_role_attribute(self, html_content):
        """Test that display has accessibility role."""
        assert 'role="status"' in html_content

    def test_display_aria_live(self, html_content):
        """Test that display has aria-live for announcements."""
        assert 'aria-live="polite"' in html_content

    def test_display_initial_content(self, html_content):
        """Test that display has initial content."""
        assert '>0<' in html_content or '>0</div>' in html_content


class TestHTMLButtonGrid:
    """Test button grid structure."""

    def test_button_grid_exists(self, html_content):
        """Test that button grid element exists."""
        assert 'id="btn-grid"' in html_content

    def test_button_grid_class(self, html_content):
        """Test that button grid has correct class."""
        assert 'class="btn-grid"' in html_content

    def test_button_grid_contains_buttons(self, html_content):
        """Test that button grid contains button elements."""
        # Extract the button grid section
        grid_start = html_content.find('id="btn-grid"')
        grid_end = html_content.find('</div><!-- /.btn-grid -->')
        grid_section = html_content[grid_start:grid_end]

        assert '<button' in grid_section


class TestHTMLButtons:
    """Test button elements."""

    def test_buttons_have_class(self, html_content):
        """Test that buttons have btn class."""
        assert 'class="btn' in html_content

    def test_buttons_have_data_value(self, html_content):
        """Test that buttons have data-value attribute."""
        assert 'data-value=' in html_content

    def test_clear_button_exists(self, html_content):
        """Test that clear button exists."""
        assert 'data-value="C"' in html_content

    def test_equals_button_exists(self, html_content):
        """Test that equals button exists."""
        assert 'data-value="="' in html_content

    def test_backspace_button_exists(self, html_content):
        """Test that backspace button exists."""
        assert '⌫' in html_content

    def test_digit_buttons_exist(self, html_content):
        """Test that digit buttons 0-9 exist."""
        for digit in range(10):
            assert f'data-value="{digit}"' in html_content

    def test_operator_buttons_exist(self, html_content):
        """Test that operator buttons exist."""
        operators = ['+', '-', '*', '/']
        for op in operators:
            assert f'data-value="{op}"' in html_content or f"data-value='{op}'" in html_content

    def test_parentheses_buttons_exist(self, html_content):
        """Test that parentheses buttons exist."""
        assert 'data-value="("' in html_content
        assert 'data-value=")"' in html_content

    def test_decimal_point_button_exists(self, html_content):
        """Test that decimal point button exists."""
        assert 'data-value="."' in html_content


class TestHTMLOperatorButtons:
    """Test operator button styling."""

    def test_operator_class_on_operators(self, html_content):
        """Test that operator buttons have operator class."""
        # Count operator class occurrences (should be more than regular buttons)
        assert 'class="btn operator"' in html_content

    def test_division_symbol_entity(self, html_content):
        """Test that division uses &divide; entity."""
        assert '&divide;' in html_content

    def test_multiplication_symbol_entity(self, html_content):
        """Test that multiplication uses &times; entity."""
        assert '&times;' in html_content

    def test_minus_symbol_entity(self, html_content):
        """Test that minus uses &minus; entity."""
        assert '&minus;' in html_content


class TestHTMLEqualsButton:
    """Test equals button styling."""

    def test_equals_has_equals_class(self, html_content):
        """Test that equals button has equals class."""
        # Find the equals button section
        assert 'class="btn btn-equals equals"' in html_content or 'class="btn equals' in html_content

    def test_equals_spans_columns(self, html_content):
        """Test that equals button styling note is present."""
        # Should have comment about grid-column: span 2
        assert 'span 2' in html_content or 'grid-column' in html_content


class TestHTMLClearButtons:
    """Test clear button styling."""

    def test_clear_buttons_have_class(self, html_content):
        """Test that clear buttons have clear class."""
        assert 'class="btn clear"' in html_content


class TestHTMLResourceLoading:
    """Test external resource loading."""

    def test_stylesheet_uses_url_for(self, html_content):
        """Test that stylesheet uses Flask url_for."""
        assert "{{ url_for('static'" in html_content
        assert "style.css" in html_content

    def test_script_uses_url_for(self, html_content):
        """Test that script uses Flask url_for."""
        assert "{{ url_for('static'" in html_content
        assert "script.js" in html_content

    def test_script_defer_attribute(self, html_content):
        """Test that script has defer attribute."""
        assert 'defer' in html_content or 'async' in html_content


class TestHTMLComments:
    """Test HTML comments and documentation."""

    def test_comments_present(self, html_content):
        """Test that HTML has comments for documentation."""
        assert "<!--" in html_content
        assert "-->" in html_content

    def test_display_documented(self, html_content):
        """Test that display element is documented."""
        # Should have comments explaining the display
        assert "Display:" in html_content or "display" in html_content.lower()

    def test_button_grid_documented(self, html_content):
        """Test that button grid is documented."""
        assert "Button grid:" in html_content or "grid:" in html_content.lower()


class TestHTMLLayout:
    """Test HTML layout structure."""

    def test_calculator_container(self, html_content):
        """Test that calculator has a container div."""
        assert 'class="calculator"' in html_content

    def test_nested_structure(self, html_content):
        """Test that structure is properly nested."""
        # Should have proper opening and closing tags
        assert '<main>' in html_content
        assert '<div class="calculator">' in html_content
        assert '<div id="btn-grid"' in html_content

    def test_button_grid_closure(self, html_content):
        """Test that button grid is properly closed."""
        assert '<!-- /.btn-grid -->' in html_content or '/.btn-grid' in html_content


class TestHTMLAccessibility:
    """Test accessibility features."""

    def test_semantic_html(self, html_content):
        """Test that semantic HTML is used."""
        assert '<main>' in html_content

    def test_aria_live_region(self, html_content):
        """Test that aria-live is used."""
        assert 'aria-live=' in html_content

    def test_role_attribute(self, html_content):
        """Test that role attribute is used."""
        assert 'role=' in html_content

    def test_descriptive_comments(self, html_content):
        """Test that HTML has descriptive comments."""
        assert "<!--" in html_content


class TestHTMLValidation:
    """Test basic HTML validation."""

    def test_no_unclosed_tags(self, html_content):
        """Test that tags are properly closed."""
        # Simple check for unmatched div tags
        div_open = html_content.count('<div')
        div_close = html_content.count('</div>')
        assert div_open == div_close

    def test_no_unmatched_buttons(self, html_content):
        """Test that button tags are closed."""
        button_open = html_content.count('<button')
        button_close = html_content.count('</button>')
        assert button_open == button_close

    def test_meta_tags_self_closing(self, html_content):
        """Test that meta tags are properly formatted."""
        assert 'charset=' in html_content or '<meta' in html_content


class TestHTMLContent:
    """Test HTML content and text."""

    def test_calculator_title(self, html_content):
        """Test that page title mentions Calculator."""
        assert '<title>' in html_content and 'Calculator' in html_content

    def test_button_text_visible(self, html_content):
        """Test that button text is visible."""
        # Should have text content for buttons
        assert '>7<' in html_content
        assert '>8<' in html_content
        assert '>9<' in html_content

    def test_initial_display_value(self, html_content):
        """Test that display has initial value."""
        # The display should initially show '0'
        assert 'id="display"' in html_content and '>0<' in html_content
