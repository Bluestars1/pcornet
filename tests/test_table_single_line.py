"""
Test to ensure table values stay on single line
"""

import os
import pytest

os.environ['PYTHONWARNINGS'] = 'ignore'

from modules.interactive_session import interactive_session, DataItem


@pytest.fixture
def test_session():
    """Create a test session and clean up after."""
    session_id = "line_test"
    interactive_session.start_session(session_id)
    yield session_id
    interactive_session.clear_session(session_id)


def test_table_has_correct_number_of_lines(test_session):
    """Ensure table has correct number of lines (no line breaks in cells)."""
    test_data = DataItem(
        key="CODE123",
        value="111552007 <br> 609561005 <br> 42954008",
        item_type="snomed"
    )
    
    interactive_session.add_data_item(test_session, test_data)
    table_output = interactive_session.format_data_as_table(test_session)
    
    lines = table_output.split('\n')
    # Expected: 3 lines (header, separator, data row)
    assert len(lines) == 3, f"Table should have 3 lines, but has {len(lines)}"


def test_single_data_row_not_split(test_session):
    """Check that data row is not split across lines."""
    test_data = DataItem(
        key="CODE123",
        value="111552007 <br> 609561005 <br> 42954008",
        item_type="snomed"
    )
    
    interactive_session.add_data_item(test_session, test_data)
    table_output = interactive_session.format_data_as_table(test_session)
    
    lines = table_output.split('\n')
    data_lines = [l for l in lines if l.startswith('| snomed')]
    
    assert len(data_lines) == 1, f"Should have 1 data row, found {len(data_lines)}"
