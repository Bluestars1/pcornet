"""
Test suite to verify HTML br tag cleanup in table formatting.
"""

import os
import pytest

os.environ['PYTHONWARNINGS'] = 'ignore'

from modules.interactive_session import interactive_session, DataItem


@pytest.fixture
def test_session():
    """Create a test session and clean up after."""
    session_id = "test_br_cleanup"
    interactive_session.start_session(session_id)
    yield session_id
    interactive_session.clear_session(session_id)


def test_table_format_br_cleanup(test_session):
    """Test that br tags are replaced with commas in table format."""
    test_data = DataItem(
        key="TEST_CODE",
        value="111552007 <br> 609561005 <br> 42954008 <br> 609562003 <br> 609575003",
        item_type="snomed_code"
    )
    
    interactive_session.add_data_item(test_session, test_data)
    table_output = interactive_session.format_data_as_table(test_session)
    
    assert "<br>" not in table_output, "br tags should be removed from table output"


def test_summary_format_br_cleanup(test_session):
    """Test that br tags are replaced with newlines in summary format."""
    test_data = DataItem(
        key="TEST_CODE",
        value="111552007 <br> 609561005 <br> 42954008",
        item_type="snomed_code"
    )
    
    interactive_session.add_data_item(test_session, test_data)
    summary_output = interactive_session.get_current_data_summary(test_session)
    
    assert "<br>" not in summary_output, "br tags should be removed from summary output"


@pytest.mark.parametrize("variant,description", [
    ("<br>", "Standard <br>"),
    ("<br/>", "Self-closing <br/>"),
    ("<br />", "Self-closing with space <br />")
])
def test_br_tag_variants(variant, description):
    """Test that different br tag variants are all cleaned."""
    test_value = f"code1 {variant} code2 {variant} code3"
    test_item = DataItem(key="VAR_TEST", value=test_value, item_type="test")
    
    # Create unique session for this test
    test_session = f"variant_test_{hash(variant)}"
    interactive_session.start_session(test_session)
    
    try:
        interactive_session.add_data_item(test_session, test_item)
        
        table = interactive_session.format_data_as_table(test_session)
        summary = interactive_session.get_current_data_summary(test_session)
        
        assert variant not in table, f"{description} should be cleaned from table"
        assert variant not in summary, f"{description} should be cleaned from summary"
    finally:
        interactive_session.clear_session(test_session)
