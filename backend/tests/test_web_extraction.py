"""Tests for the extract + review web extraction pipeline.

Covers:
- HTML content extraction (script/nav/footer removal)
- Cross-field validation checks
- Value normalization for comparison
- Category-level deep compare
- Field-level merge (Gemini + OpenAI review)
- OpenAI review (mocked client)
- Pipeline integration with mocked Gemini + OpenAI responses
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import pytest

from backend.src.etl.scrape.browser import PlaywrightFetcher
from backend.src.etl.extract.dual_resolver import (
    FieldChange,
    ReviewReport,
    categories_match,
    merge_reviewed,
    normalize_for_comparison,
)
from backend.src.etl.scrape.content import html_to_text
from backend.src.etl.verify.checks import (
    ExtractionError,
    check_dimension_ranges,
    check_electrical_ranges,
    check_heater_wattage_range,
    check_jet_count_range,
    check_jet_sum_consistency,
    check_pump_count_reasonable,
    check_pump_hp_range,
    check_seating_capacity_range,
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


class TestSeatingCapacityRange:
    """Tests for check_seating_capacity_range."""

    def test_valid_capacity(self):
        assert check_seating_capacity_range({"seating_capacity": 7}) == []

    def test_too_high(self):
        errors = check_seating_capacity_range({"seating_capacity": 99})
        assert len(errors) == 1
        assert "99" in errors[0].message

    def test_too_low(self):
        errors = check_seating_capacity_range({"seating_capacity": 0})
        assert len(errors) == 1

    def test_null_no_error(self):
        assert check_seating_capacity_range({"seating_capacity": None}) == []

    def test_string_value_flagged(self):
        errors = check_seating_capacity_range({"seating_capacity": "seven"})
        assert len(errors) == 1
        assert "not numeric" in errors[0].message


class TestElectricalRanges:
    """Tests for check_electrical_ranges."""

    def test_standard_240v_50a(self):
        assert check_electrical_ranges({"voltage": 240, "amperage": 50}) == []

    def test_standard_120v(self):
        assert check_electrical_ranges({"voltage": 120, "amperage": 15}) == []

    def test_bogus_voltage(self):
        errors = check_electrical_ranges({"voltage": 999})
        assert len(errors) == 1
        assert "999" in errors[0].message

    def test_bogus_amperage(self):
        errors = check_electrical_ranges({"amperage": 200})
        assert len(errors) == 1
        assert "200" in errors[0].message

    def test_null_no_error(self):
        assert check_electrical_ranges({"voltage": None, "amperage": None}) == []

    def test_string_voltage_flagged(self):
        errors = check_electrical_ranges({"voltage": "115 V or 230 V"})
        assert len(errors) == 1
        assert "not numeric" in errors[0].message

    def test_string_amperage_flagged(self):
        errors = check_electrical_ranges({"amperage": "40A, 50A or 60A"})
        assert len(errors) == 1
        assert "not numeric" in errors[0].message


class TestHeaterWattageRange:
    """Tests for check_heater_wattage_range."""

    def test_valid_wattage(self):
        assert check_heater_wattage_range({"heater": {"wattage": 4000}}) == []

    def test_too_high(self):
        errors = check_heater_wattage_range({"heater": {"wattage": 50000}})
        assert len(errors) == 1

    def test_too_low(self):
        errors = check_heater_wattage_range({"heater": {"wattage": 100}})
        assert len(errors) == 1

    def test_null_no_error(self):
        assert check_heater_wattage_range({"heater": {"wattage": None}}) == []


class TestPumpHpRange:
    """Tests for check_pump_hp_range."""

    def test_valid_hp(self):
        data = {"jet_pumps": {"pumps": [{"position": 1, "horsepower_continuous": 2.5}]}}
        assert check_pump_hp_range(data) == []

    def test_bogus_hp(self):
        data = {"jet_pumps": {"pumps": [{"position": 1, "horsepower_continuous": 50.0}]}}
        errors = check_pump_hp_range(data)
        assert len(errors) == 1
        assert "50.0" in errors[0].message

    def test_null_hp_no_error(self):
        data = {"jet_pumps": {"pumps": [{"position": 1, "horsepower_continuous": None}]}}
        assert check_pump_hp_range(data) == []


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------


class TestNormalize:
    """Tests for normalize_for_comparison."""

    def test_none_stays_none(self):
        assert normalize_for_comparison(None) is None

    def test_string_lowered(self):
        assert normalize_for_comparison("Rotary") == "rotary"

    def test_null_string_becomes_none(self):
        assert normalize_for_comparison("null") is None
        assert normalize_for_comparison("None") is None
        assert normalize_for_comparison("n/a") is None
        assert normalize_for_comparison("N/A") is None

    def test_empty_string_becomes_none(self):
        assert normalize_for_comparison("") is None

    def test_float_rounded(self):
        assert normalize_for_comparison(91.04) == 91.0
        assert normalize_for_comparison(91.06) == 91.1

    def test_int_unchanged(self):
        assert normalize_for_comparison(42) == 42

    def test_bool_unchanged(self):
        assert normalize_for_comparison(True) is True
        assert normalize_for_comparison(False) is False

    def test_empty_list_becomes_none(self):
        assert normalize_for_comparison([]) is None

    def test_list_of_dicts_sorted_by_jet_type(self):
        items = [
            {"jet_type": "B", "quantity": 5},
            {"jet_type": "A", "quantity": 3},
        ]
        result = normalize_for_comparison(items)
        assert result[0]["jet_type"] == "a"
        assert result[1]["jet_type"] == "b"

    def test_nested_dict_normalized(self):
        data = {"model_name": "Null", "wattage": 4000}
        result = normalize_for_comparison(data)
        assert result["model_name"] is None
        assert result["wattage"] == 4000


# ---------------------------------------------------------------------------
# Category match tests
# ---------------------------------------------------------------------------


class TestCategoriesMatch:
    """Tests for categories_match."""

    def test_both_none_match(self):
        assert categories_match(None, None) is True

    def test_empty_list_vs_none_match(self):
        assert categories_match([], None) is True
        assert categories_match(None, []) is True

    def test_same_dict_match(self):
        a = {"wattage": 4000, "voltage": 240, "shared_with_series": False}
        b = {"wattage": 4000, "voltage": 240, "shared_with_series": False}
        assert categories_match(a, b) is True

    def test_case_insensitive_match(self):
        a = {"type": "Rotary", "quantity": 5}
        b = {"type": "rotary", "quantity": 5}
        assert categories_match(a, b) is True

    def test_float_precision_match(self):
        a2 = {"length_inches": 91.04}
        b2 = {"length_inches": 91.0}
        assert categories_match(a2, b2) is True

    def test_different_values_no_match(self):
        a = {"wattage": 4000}
        b = {"wattage": 5000}
        assert categories_match(a, b) is False

    def test_list_different_order_match(self):
        a = [
            {"jet_type": "B", "quantity": 5},
            {"jet_type": "A", "quantity": 3},
        ]
        b = [
            {"jet_type": "A", "quantity": 3},
            {"jet_type": "B", "quantity": 5},
        ]
        assert categories_match(a, b) is True

    def test_list_different_quantities_no_match(self):
        a = [{"jet_type": "A", "quantity": 3}]
        b = [{"jet_type": "A", "quantity": 5}]
        assert categories_match(a, b) is False


# ---------------------------------------------------------------------------
# Field-level merge tests
# ---------------------------------------------------------------------------


# Shared mock data
_BASE_EXTRACTION = {
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
        "pumps": [{"position": 1, "horsepower_continuous": 2.5}],
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
        "features": [],
        "part_number": None,
        "shared_with_series": False,
    },
    "topside_control": {
        "model_name": None,
        "features": [],
        "part_number": None,
        "shared_with_series": False,
    },
    "jets": {
        "total_jet_count": 45,
        "jet_system_type": "fixed",
        "jets_by_type": [
            {"jet_type": "Rotary", "quantity": 25},
            {"jet_type": "Directional", "quantity": 20},
        ],
        "shared_with_series": False,
    },
    "headrests": {"headrests": [], "shared_with_series": False},
    "filters": {
        "filters": [{"filter_type": "Pleated", "filtration_area_sqft": 100.0}],
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
    "lighting": {"lights": [], "water_feature": None, "shared_with_series": False},
    "cover": {
        "model_name": None,
        "features": [],
        "part_number": None,
        "shared_with_series": False,
    },
}


class TestFieldLevelMerge:
    """Tests for merge_reviewed field-level merge."""

    def test_identical_all_confirmed(self):
        """When Gemini and review are identical, all fields confirmed."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        merged, report = merge_reviewed(gemini, review, "TestModel")
        assert report.corrected == 0
        assert report.filled == 0
        assert report.nulled == 0
        assert report.confirmed > 0
        assert len(report.changes) == 0

    def test_review_corrects_value(self):
        """When review changes a value, it's reported as corrected."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        review["heater"]["wattage"] = 5000  # review corrects
        merged, report = merge_reviewed(gemini, review, "TestModel")
        assert merged["heater"]["wattage"] == 5000  # review wins
        assert report.corrected >= 1
        corrected = [c for c in report.changes if c.change_type == "corrected"]
        assert any("heater" in c.field_path and c.review_value == 5000 for c in corrected)

    def test_review_fills_null(self):
        """When Gemini has null and review fills it, it's reported as filled."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        gemini["heater"]["model_name"] = None
        review["heater"]["model_name"] = "No-Fault 4.0kW"
        merged, report = merge_reviewed(gemini, review, "TestModel")
        assert merged["heater"]["model_name"] == "No-Fault 4.0kW"
        assert report.filled >= 1

    def test_review_nulls_value(self):
        """When Gemini has a value and review sets it to null, it's reported as nulled."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        gemini["circulation_pump"]["wattage"] = 85
        review["circulation_pump"]["wattage"] = None
        merged, report = merge_reviewed(gemini, review, "TestModel")
        assert merged["circulation_pump"]["wattage"] is None
        assert report.nulled >= 1

    def test_review_wins_on_merge(self):
        """Review data is the primary result for all fields."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        review["seating_capacity"] = 6
        review["voltage"] = 120
        merged, report = merge_reviewed(gemini, review, "TestModel")
        assert merged["seating_capacity"] == 6
        assert merged["voltage"] == 120

    def test_review_missing_key_falls_back_to_gemini(self):
        """If review is missing a top-level key, Gemini's value is used."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        del review["cover"]
        merged, report = merge_reviewed(gemini, review, "TestModel")
        assert merged["cover"] == gemini["cover"]

    def test_multiple_corrections(self):
        """Multiple fields corrected across categories."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        review["heater"]["wattage"] = 5000
        review["jets"]["total_jet_count"] = 50
        review["seating_capacity"] = 8
        merged, report = merge_reviewed(gemini, review, "TestModel")
        assert merged["heater"]["wattage"] == 5000
        assert merged["jets"]["total_jet_count"] == 50
        assert merged["seating_capacity"] == 8
        assert report.corrected >= 3

    def test_report_model_name(self):
        """Report carries the model name."""
        gemini = copy.deepcopy(_BASE_EXTRACTION)
        review = copy.deepcopy(_BASE_EXTRACTION)
        _, report = merge_reviewed(gemini, review, "Grandee")
        assert report.model_name == "Grandee"


# ---------------------------------------------------------------------------
# OpenAI review tests (mocked client)
# ---------------------------------------------------------------------------


class TestOpenAIReview:
    """Tests for OpenAI review with mocked client."""

    @patch("backend.src.etl.extract.openai_extractor._get_client")
    def test_review_returns_corrected_json(self, mock_get_client):
        """OpenAI review returns corrected dict."""
        import json

        corrected = copy.deepcopy(_BASE_EXTRACTION)
        corrected["heater"]["wattage"] = 5000

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(corrected)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from backend.src.etl.extract.openai_extractor import review

        result = review(
            gemini_data=_BASE_EXTRACTION,
            page_text="page text",
            model_name="TestModel",
            manufacturer="sundance",
            series="880 Series",
        )
        assert result is not None
        assert result["heater"]["wattage"] == 5000

    @patch("backend.src.etl.extract.openai_extractor._get_client")
    def test_review_returns_none_on_failure(self, mock_get_client):
        """OpenAI review returns None when API fails."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API error")
        mock_get_client.return_value = mock_client

        from backend.src.etl.extract.openai_extractor import review

        result = review(
            gemini_data=_BASE_EXTRACTION,
            page_text="page text",
            model_name="TestModel",
            manufacturer="sundance",
            series="880 Series",
        )
        assert result is None


# ---------------------------------------------------------------------------
# OpenAI extractor tests (mocked client) — existing extract/extract_categories
# ---------------------------------------------------------------------------


class TestOpenAIExtractor:
    """Tests for OpenAI extractor with mocked client."""

    @patch("backend.src.etl.extract.openai_extractor._get_client")
    def test_extract_returns_parsed_json(self, mock_get_client):
        """OpenAI extract returns parsed dict from JSON response."""
        import json

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"seating_capacity": 7})

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from backend.src.etl.extract.openai_extractor import extract

        result = extract("page text", "TestModel", "sundance", "880 Series")
        assert result == {"seating_capacity": 7}

    @patch("backend.src.etl.extract.openai_extractor._get_client")
    def test_extract_returns_none_on_failure(self, mock_get_client):
        """OpenAI extract returns None when API fails."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API error")
        mock_get_client.return_value = mock_client

        from backend.src.etl.extract.openai_extractor import extract

        result = extract("page text", "TestModel", "sundance", "880 Series")
        assert result is None

    @patch("backend.src.etl.extract.openai_extractor._get_client")
    def test_extract_categories_returns_partial(self, mock_get_client):
        """OpenAI extract_categories returns only requested categories."""
        import json

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({"jets": {"total_jet_count": 45}})

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from backend.src.etl.extract.openai_extractor import extract_categories

        result = extract_categories(
            "page text", "TestModel", "sundance", "880 Series",
            categories=["jets"], errors=["jet count mismatch"],
        )
        assert result == {"jets": {"total_jet_count": 45}}


# ---------------------------------------------------------------------------
# Pipeline integration tests (mocked Gemini + OpenAI)
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
    """Integration tests with mocked Gemini and OpenAI responses."""

    @patch("backend.src.etl.web_pipeline.openai_extractor")
    @patch("backend.src.etl.web_pipeline.extract")
    @patch("backend.src.etl.web_pipeline._fetch_html")
    def test_successful_extraction_with_review(self, mock_fetch, mock_gemini, mock_openai_mod, tmp_path):
        """Full pipeline produces a valid SpaModel with review agreeing."""
        mock_fetch.return_value = "<html><body><p>Specs here</p></body></html>"
        mock_gemini.return_value = copy.deepcopy(MOCK_GEMINI_RESPONSE)
        mock_openai_mod.review.return_value = copy.deepcopy(MOCK_GEMINI_RESPONSE)

        from backend.src.etl.web_pipeline import run_web_model

        fetcher = MagicMock(spec=PlaywrightFetcher)
        result = run_web_model("sundance", "Aspen", fetcher)
        assert result is not None
        assert result.model_name == "Aspen"
        assert result.manufacturer.value == "sundance"
        assert result.jets.total_jet_count == 45

    @patch("backend.src.etl.web_pipeline.openai_extractor")
    @patch("backend.src.etl.web_pipeline.extract")
    @patch("backend.src.etl.web_pipeline._fetch_html")
    def test_review_failure_falls_back_to_gemini(self, mock_fetch, mock_gemini, mock_openai_mod):
        """When OpenAI review returns None, pipeline uses Gemini only."""
        mock_fetch.return_value = "<html><body><p>Specs</p></body></html>"
        mock_gemini.return_value = copy.deepcopy(MOCK_GEMINI_RESPONSE)
        mock_openai_mod.review.return_value = None

        from backend.src.etl.web_pipeline import run_web_model

        fetcher = MagicMock(spec=PlaywrightFetcher)
        result = run_web_model("sundance", "Aspen", fetcher)
        assert result is not None
        assert result.jets.total_jet_count == 45

    @patch("backend.src.etl.web_pipeline.openai_extractor")
    @patch("backend.src.etl.web_pipeline.extract")
    @patch("backend.src.etl.web_pipeline._fetch_html")
    def test_validation_loop_triggers_reextract(self, mock_fetch, mock_gemini, mock_openai_mod):
        """When jet count is hallucinated, pipeline calls extract_categories."""
        bad_response = copy.deepcopy(MOCK_GEMINI_RESPONSE)
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
        mock_gemini.return_value = bad_response
        # OpenAI review returns same bad data
        mock_openai_mod.review.return_value = copy.deepcopy(bad_response)

        with patch("backend.src.etl.web_pipeline.extract_categories") as mock_reextract:
            mock_reextract.return_value = {
                "jets": MOCK_GEMINI_RESPONSE["jets"],
            }

            from backend.src.etl.web_pipeline import run_web_model

            fetcher = MagicMock(spec=PlaywrightFetcher)
            result = run_web_model("sundance", "Aspen", fetcher)

            mock_reextract.assert_called_once()
            assert result is not None
            assert result.jets.total_jet_count == 45

    @patch("backend.src.etl.web_pipeline.openai_extractor")
    @patch("backend.src.etl.web_pipeline.extract")
    @patch("backend.src.etl.web_pipeline._fetch_html")
    def test_fetch_failure_returns_none(self, mock_fetch, mock_gemini, mock_openai_mod):
        """Pipeline returns None when page fetch fails."""
        mock_fetch.return_value = None

        from backend.src.etl.web_pipeline import run_web_model

        fetcher = MagicMock(spec=PlaywrightFetcher)
        result = run_web_model("sundance", "Aspen", fetcher)
        assert result is None
        mock_gemini.assert_not_called()
