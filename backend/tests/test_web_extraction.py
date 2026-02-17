"""Tests for the v2 web extraction pipeline.

Covers:
- HTML content extraction (script/nav/footer removal)
- Cross-field validation checks
- Fetcher selection (httpx vs Playwright by domain)
- Pipeline integration with mocked Gemini responses
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.src.etl.scrape.config import needs_browser
from backend.src.etl.scrape.content import html_to_text
from backend.src.etl.scrape.fetcher import PageFetcher
from backend.src.etl.verify.checks import (
    ExtractionError,
    check_dimension_ranges,
    check_jet_count_range,
    check_jet_sum_consistency,
    check_pump_count_reasonable,
    get_extraction_errors,
)


# ---------------------------------------------------------------------------
# Content extraction tests
# ---------------------------------------------------------------------------


class TestHtmlToText:
    """Tests for html_to_text content cleaning."""

    def test_removes_script_tags(self):
        html = "<html><body><script>var x=1;</script><p>Specs</p></body></html>"
        text = html_to_text(html)
        assert "var x" not in text
        assert "Specs" in text

    def test_removes_style_tags(self):
        html = "<html><body><style>.foo{color:red}</style><p>Data</p></body></html>"
        text = html_to_text(html)
        assert "color" not in text
        assert "Data" in text

    def test_removes_nav_footer_header(self):
        html = (
            "<html><body>"
            "<header>Site Header</header>"
            "<nav>Menu Item</nav>"
            "<main><p>Jet Count: 45</p></main>"
            "<footer>Copyright</footer>"
            "</body></html>"
        )
        text = html_to_text(html)
        assert "Site Header" not in text
        assert "Menu Item" not in text
        assert "Copyright" not in text
        assert "Jet Count: 45" in text

    def test_removes_noscript_iframe(self):
        html = (
            "<html><body>"
            "<noscript>Enable JS</noscript>"
            "<iframe src='ad.html'></iframe>"
            "<p>Content</p>"
            "</body></html>"
        )
        text = html_to_text(html)
        assert "Enable JS" not in text
        assert "Content" in text

    def test_preserves_text_content(self):
        html = (
            "<html><body>"
            "<div><h1>Grandee</h1>"
            "<p>Seating: 7</p>"
            "<p>Jets: 65</p>"
            "</div></body></html>"
        )
        text = html_to_text(html)
        assert "Grandee" in text
        assert "Seating: 7" in text
        assert "Jets: 65" in text


# ---------------------------------------------------------------------------
# Cross-field validation check tests
# ---------------------------------------------------------------------------


class TestJetSumConsistency:
    """Tests for check_jet_sum_consistency."""

    def test_matching_sums_no_error(self):
        data = {
            "jets": {
                "total_jet_count": 10,
                "jets_by_type": [
                    {"jet_type": "A", "quantity": 6},
                    {"jet_type": "B", "quantity": 4},
                ],
            }
        }
        assert check_jet_sum_consistency(data) == []

    def test_small_diff_within_tolerance(self):
        data = {
            "jets": {
                "total_jet_count": 10,
                "jets_by_type": [
                    {"jet_type": "A", "quantity": 6},
                    {"jet_type": "B", "quantity": 3},  # sum=9, diff=1
                ],
            }
        }
        assert check_jet_sum_consistency(data) == []

    def test_large_diff_triggers_error(self):
        data = {
            "jets": {
                "total_jet_count": 65,
                "jets_by_type": [
                    {"jet_type": "A", "quantity": 20},
                    {"jet_type": "B", "quantity": 10},  # sum=30, diff=35
                ],
            }
        }
        errors = check_jet_sum_consistency(data)
        assert len(errors) == 1
        assert "mismatch" in errors[0].message.lower()

    def test_no_jets_no_error(self):
        data = {}
        assert check_jet_sum_consistency(data) == []

    def test_no_total_no_error(self):
        data = {
            "jets": {
                "total_jet_count": None,
                "jets_by_type": [{"jet_type": "A", "quantity": 5}],
            }
        }
        assert check_jet_sum_consistency(data) == []


class TestPumpCountReasonable:
    """Tests for check_pump_count_reasonable."""

    def test_normal_pump_count(self):
        data = {"jet_pumps": {"pumps": [{"position": 1}, {"position": 2}]}}
        assert check_pump_count_reasonable(data) == []

    def test_zero_pumps_error(self):
        data = {"jet_pumps": {"pumps": []}}
        errors = check_pump_count_reasonable(data)
        assert len(errors) == 1

    def test_five_pumps_error(self):
        data = {"jet_pumps": {"pumps": [{"position": i} for i in range(1, 6)]}}
        errors = check_pump_count_reasonable(data)
        assert len(errors) == 1


class TestDimensionRanges:
    """Tests for check_dimension_ranges."""

    def test_valid_dimensions(self):
        data = {
            "dimensions": {
                "length_inches": 91.0,
                "width_inches": 91.0,
                "height_inches": 38.5,
            }
        }
        assert check_dimension_ranges(data) == []

    def test_length_too_large(self):
        data = {"dimensions": {"length_inches": 200.0}}
        errors = check_dimension_ranges(data)
        assert len(errors) == 1
        assert "length_inches" in errors[0].message

    def test_height_too_small(self):
        data = {"dimensions": {"height_inches": 10.0}}
        errors = check_dimension_ranges(data)
        assert len(errors) == 1
        assert "height_inches" in errors[0].message


class TestJetCountRange:
    """Tests for check_jet_count_range."""

    def test_normal_jet_count(self):
        data = {"jets": {"total_jet_count": 65}}
        assert check_jet_count_range(data) == []

    def test_hallucinated_high_count(self):
        data = {"jets": {"total_jet_count": 184}}
        errors = check_jet_count_range(data)
        assert len(errors) == 1
        assert "184" in errors[0].message

    def test_too_few_jets(self):
        data = {"jets": {"total_jet_count": 2}}
        errors = check_jet_count_range(data)
        assert len(errors) == 1

    def test_null_count_no_error(self):
        data = {"jets": {"total_jet_count": None}}
        assert check_jet_count_range(data) == []


class TestGetExtractionErrors:
    """Tests for get_extraction_errors aggregator."""

    def test_clean_data_no_errors(self):
        data = {
            "jets": {
                "total_jet_count": 45,
                "jets_by_type": [
                    {"jet_type": "A", "quantity": 25},
                    {"jet_type": "B", "quantity": 20},
                ],
            },
            "jet_pumps": {"pumps": [{"position": 1}, {"position": 2}]},
            "dimensions": {
                "length_inches": 91.0,
                "width_inches": 91.0,
                "height_inches": 38.5,
            },
        }
        assert get_extraction_errors(data) == []

    def test_multiple_errors(self):
        data = {
            "jets": {"total_jet_count": 323},  # hallucinated
            "jet_pumps": {"pumps": []},  # zero pumps
            "dimensions": {"height_inches": 5.0},  # too small
        }
        errors = get_extraction_errors(data)
        assert len(errors) >= 2  # at least jet count + pump count + dimension


# ---------------------------------------------------------------------------
# Fetcher selection tests
# ---------------------------------------------------------------------------


class TestNeedsBrowser:
    """Tests for needs_browser URL routing."""

    def test_bullfrog_needs_browser(self):
        assert needs_browser("https://www.bullfrogspas.com/spas/m-series-hot-tubs/m9/") is True

    def test_sundance_uses_httpx(self):
        assert needs_browser("https://www.sundancespas.com/en-us/aspen-880-series/Aspen.html") is False

    def test_hotspring_needs_browser(self):
        assert needs_browser("https://www.hotspring.com/shop/highlife/grandee") is True


# ---------------------------------------------------------------------------
# Pipeline integration tests (mocked Gemini)
# ---------------------------------------------------------------------------


MOCK_GEMINI_RESPONSE = {
    "seating_capacity": 7,
    "voltage": 240,
    "amperage": 50,
    "dimensions": {
        "length_inches": 91.0,
        "width_inches": 91.0,
        "height_inches": 38.5,
        "dry_weight_lbs": 850.0,
        "filled_weight_lbs": 4500.0,
        "water_capacity_gallons": 420.0,
    },
    "jet_pumps": {
        "pumps": [
            {
                "position": 1,
                "model_name": None,
                "horsepower_continuous": 2.5,
                "horsepower_breakdown": None,
                "speed": "2-speed",
                "amperage_max": None,
                "frame": None,
                "voltage": 240,
                "part_number": None,
            }
        ],
        "diverter_valves": 2,
        "total_brake_horsepower": None,
        "shared_with_series": False,
    },
    "circulation_pump": {
        "model_name": None,
        "description": "Silent circulation",
        "is_dedicated": True,
        "wattage": 85,
        "part_number": None,
        "shared_with_series": False,
    },
    "spa_pak": {
        "model_name": None,
        "display_type": None,
        "voltage": 240,
        "amperage": None,
        "frequency_hz": 60,
        "features": [],
        "part_number": None,
        "shared_with_series": False,
    },
    "topside_control": {
        "model_name": None,
        "type": None,
        "features": [],
        "smart_connectivity": None,
        "part_number": None,
        "shared_with_series": False,
    },
    "jets": {
        "total_jet_count": 45,
        "jet_system_type": "fixed",
        "jets_by_type": [
            {"jet_type": "Rotary", "quantity": 25, "zone": None, "part_number": None, "description": None},
            {"jet_type": "Directional", "quantity": 20, "zone": None, "part_number": None, "description": None},
        ],
        "jetpak_count": None,
        "jetpak_options": None,
        "shared_with_series": False,
    },
    "headrests": {
        "headrests": [],
        "shared_with_series": False,
    },
    "filters": {
        "filters": [
            {
                "system_name": None,
                "filter_type": "Pleated",
                "filtration_area_sqft": 100.0,
                "quantity": 1,
                "description": None,
                "no_bypass": None,
                "part_number": None,
            }
        ],
        "shared_with_series": False,
    },
    "heater": {
        "model_name": None,
        "wattage": 4000,
        "voltage": 240,
        "material": None,
        "part_number": None,
        "shared_with_series": False,
    },
    "lighting": {
        "lights": [],
        "water_feature": None,
        "shared_with_series": False,
    },
    "cover": {
        "model_name": None,
        "thickness": None,
        "material": None,
        "features": [],
        "length_inches": None,
        "width_inches": None,
        "part_number": None,
        "shared_with_series": False,
    },
}


class TestPipelineIntegration:
    """Integration tests with mocked Gemini and HTTP responses."""

    @patch("backend.src.etl.web_pipeline.extract")
    @patch("backend.src.etl.web_pipeline._fetch_html")
    def test_successful_extraction(self, mock_fetch, mock_extract, tmp_path):
        """Full pipeline produces a valid SpaModel with mocked Gemini."""
        mock_fetch.return_value = "<html><body><p>Specs here</p></body></html>"
        mock_extract.return_value = MOCK_GEMINI_RESPONSE.copy()

        from backend.src.etl.web_pipeline import run_web_model
        from backend.src.etl.scrape.fetcher import PageFetcher

        fetcher = MagicMock(spec=PageFetcher)
        result = run_web_model("sundance", "Aspen", fetcher)
        assert result is not None
        assert result.model_name == "Aspen"
        assert result.manufacturer.value == "sundance"
        assert result.jets.total_jet_count == 45

    @patch("backend.src.etl.web_pipeline.extract")
    @patch("backend.src.etl.web_pipeline._fetch_html")
    def test_validation_loop_triggers_reextract(self, mock_fetch, mock_extract):
        """When jet count is hallucinated, pipeline calls extract_categories."""
        bad_response = MOCK_GEMINI_RESPONSE.copy()
        bad_response["jets"] = {
            "total_jet_count": 184,  # hallucinated
            "jet_system_type": "fixed",
            "jets_by_type": [
                {"jet_type": "Rotary", "quantity": 20, "zone": None, "part_number": None, "description": None},
            ],
            "jetpak_count": None,
            "jetpak_options": None,
            "shared_with_series": False,
        }
        mock_fetch.return_value = "<html><body><p>Specs</p></body></html>"
        mock_extract.return_value = bad_response

        with patch("backend.src.etl.web_pipeline.extract_categories") as mock_reextract:
            mock_reextract.return_value = {
                "jets": MOCK_GEMINI_RESPONSE["jets"],
            }

            from backend.src.etl.web_pipeline import run_web_model

            fetcher = MagicMock(spec=PageFetcher)
            result = run_web_model("sundance", "Aspen", fetcher)

            mock_reextract.assert_called_once()
            assert result is not None
            assert result.jets.total_jet_count == 45

    @patch("backend.src.etl.web_pipeline.extract")
    @patch("backend.src.etl.web_pipeline._fetch_html")
    def test_fetch_failure_returns_none(self, mock_fetch, mock_extract):
        """Pipeline returns None when page fetch fails."""
        mock_fetch.return_value = None

        from backend.src.etl.web_pipeline import run_web_model

        fetcher = MagicMock(spec=PageFetcher)
        result = run_web_model("sundance", "Aspen", fetcher)
        assert result is None
        mock_extract.assert_not_called()
