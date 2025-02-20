from app.requests.schemas import ExtractFieldsResponse
import pytest
from unittest.mock import MagicMock, Mock, patch
from app.processing.process_queue import (
    handle_exceptions,
    extract_process,
    update_process_step_status,
    find_best_match_for_short_reference,
    vectorize_extraction_process_step,
)
from app.exceptions import CreditLimitExceededException
from app.models import ProcessStepStatus

@pytest.fixture
def mock_logger():
    with patch('app.processing.process_queue.logger') as mock:
        yield mock

def test_handle_exceptions_decorator(mock_logger):
    @handle_exceptions
    def test_function():
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        test_function()

    mock_logger.error.assert_called()

def test_handle_exceptions_decorator_credit_limit(mock_logger):
    @handle_exceptions
    def test_function():
        raise CreditLimitExceededException("Credit limit exceeded")

    with pytest.raises(CreditLimitExceededException):
        test_function()

    mock_logger.error.assert_called_with("Credit limit exceeded")

@patch('app.processing.process_queue.extract_data')
@patch('app.processing.process_queue.ChromaDB')
def test_extract_process(mock_chroma, mock_extract_data):
    mock_chroma_instance = Mock()
    mock_chroma.return_value = mock_chroma_instance
    mock_chroma_instance.get_relevant_docs.return_value = {
        "metadatas": [[{
            "page_number": 1,
            "previous_sentence_id": -1,
            "next_sentence_id": -1
        }]],
        "documents": [["Test document"]]
    }
    mock_extract_data.return_value = ExtractFieldsResponse(fields=[{"field1": "value1"}],
        references=[[{
        "name": "ESG_Reporting_Assurance",
        "sources": [
          "Assurance"
        ]
      }]]
        )

    process = Mock(id=1, project_id=1, details={"fields": [{"key": "field1"}]})
    process_step = Mock(id=1, asset=Mock(id=1))
    asset_content = Mock(content={"word_count": 1000, "content": ["Test content"]})

    result = extract_process("api_key", process, process_step, asset_content)

    assert "fields" in result
    assert "context" in result
    assert result["fields"] == [{"field1": "value1"}]
    assert result["context"] == [[{'name': 'ESG_Reporting_Assurance', 'sources': ['Assurance'], 'page_numbers': None}]]
    mock_extract_data.assert_called_once()

def test_update_process_step_status():
    mock_db = Mock()
    mock_process_step = Mock()
    mock_status = ProcessStepStatus.COMPLETED
    mock_output = {"test": "output"}
    mock_output_references = {"test": "references"}

    with patch('app.processing.process_queue.process_repository.update_process_step_status') as mock_update:
        update_process_step_status(mock_db, mock_process_step, mock_status, mock_output, mock_output_references)

    mock_update.assert_called_once_with(
        mock_db,
        mock_process_step,
        mock_status,
        output=mock_output,
        output_references=mock_output_references
    )

@patch('app.processing.process_queue.re.findall')
def test_find_best_match_for_short_reference(mock_findall):
    mock_findall.side_effect = [
        ['ai', 'and', 'machine', 'learning'],
        ['this', 'is', 'a', 'long', 'document', 'about', 'ai', 'and', 'machine', 'learning'],  # For the document text
        ['quantum', 'computing'],
        ['this', 'is', 'a', 'long', 'document', 'about', 'ai', 'and', 'machine', 'learning'],  # For the document text again
        ['another', 'document', 'talking', 'about', 'natural', 'language', 'processing'],  # For the second document
        [],
        ['this', 'is', 'a', 'long', 'document', 'about', 'ai', 'and', 'machine', 'learning']  # For the document text one more time
    ]
    all_relevant_docs = [
        {
            "documents": [["This is a long document about AI and machine learning."]],
            "metadatas": [[{"asset_id": 1, "project_id": 1, "page_number": 1}]]
        },
        {
            "documents": [["Another document talking about natural language processing."]],
            "metadatas": [[{"asset_id": 1, "project_id": 1, "page_number": 2}]]
        }
    ]

    # Test with a good match
    result = find_best_match_for_short_reference("AI and machine learning", all_relevant_docs, 1, 1)
    assert result is not None
    assert "text" in result
    assert "page_number" in result
    assert "AI" in result["text"] and "machine learning" in result["text"]

    # Test with a poor match
    result = find_best_match_for_short_reference("Quantum computing", all_relevant_docs, 1, 1)
    assert result is None

    assert mock_findall.call_count == 6

@pytest.mark.parametrize("short_reference, expected_result", [
    ("AI and machine learning", True),
    ("Quantum computing", False),
])
@patch('app.processing.process_queue.re.findall')
def test_find_best_match_for_short_reference_parametrized(mock_findall, short_reference, expected_result):
    mock_findall.side_effect = [
        short_reference.lower().split(),
        ['this', 'is', 'a', 'long', 'document', 'about', 'ai', 'and', 'machine', 'learning'],  # For the first document
        ['another', 'document', 'talking', 'about', 'natural', 'language', 'processing'],  # For the second document
    ]

    all_relevant_docs = [
        {
            "documents": [["This is a long document about AI and machine learning."]],
            "metadatas": [[{"asset_id": 1, "project_id": 1, "page_number": 1}]]
        },
        {
            "documents": [["Another document talking about natural language processing."]],
            "metadatas": [[{"asset_id": 1, "project_id": 1, "page_number": 2}]]
        }
    ]

    result = find_best_match_for_short_reference(short_reference, all_relevant_docs, 1, 1)

    if expected_result:
        assert result is not None
        assert "text" in result
        assert "page_number" in result
        assert short_reference.lower() in result["text"].lower()
    else:
        assert result is None

    assert mock_findall.call_count == 3

@patch('app.processing.process_queue.ChromaDB')
@patch('app.processing.process_queue.extract_data')
def test_chroma_db_initialization(mock_extract_data, mock_chroma):
    mock_chroma_instance = Mock()
    mock_chroma.return_value = mock_chroma_instance
    mock_extract_data.return_value = ExtractFieldsResponse(fields=[{"field1": "value1"}],
        references=[[{
        "name": "ESG_Reporting_Assurance",
        "sources": [
          "Assurance"
        ]
      }]]
        )

    process = Mock(id=1, project_id=1, details={"fields": [{"key": "field1"}]})
    process_step = Mock(id=1, asset=Mock(id=1))
    asset_content = Mock(content={"word_count": 100, "content": ["Short content"]})

    extract_process("api_key", process, process_step, asset_content)

    mock_chroma.assert_called_with(f"panda-etl-{process.project_id}", similarity_threshold=3)
    assert mock_chroma.call_count >= 1

@patch('app.processing.process_queue.ChromaDB')
def test_vectorize_extraction_process_step_single_reference(mock_chroma_db):
    # Mock ChromaDB instance
    mock_vectorstore = MagicMock()
    mock_chroma_db.return_value = mock_vectorstore

    # Inputs
    project_id = 123
    process_step_id = 1
    filename = "sample_file"
    references = [
        [
            {"name": "field1", "sources": ["source1", "source2"]}
        ]
    ]

    # Call function
    vectorize_extraction_process_step(project_id, process_step_id, filename, references)

    # Expected docs and metadata to add to ChromaDB
    expected_docs = ["sample_file field1"]
    expected_metadatas = [
        {
            "project_id": project_id,
            "process_step_id": process_step_id,
            "filename": filename,
            "reference": "source1\nsource2"
        }
    ]

    # Assertions
    mock_vectorstore.add_docs.assert_called_once_with(
        docs=expected_docs,
        metadatas=expected_metadatas,
        batch_size=5
    )

@patch('app.processing.process_queue.ChromaDB')
def test_vectorize_extraction_process_step_multiple_references_concatenation(mock_chroma_db):
    # Mock ChromaDB instance
    mock_vectorstore = MagicMock()
    mock_chroma_db.return_value = mock_vectorstore

    # Inputs
    project_id = 456
    process_step_id = 2
    filename = "test_file"
    references = [
        [
            {"name": "field1", "sources": ["source1", "source2"]},
            {"name": "field1", "sources": ["source3"]}
        ],
        [
            {"name": "field2", "sources": ["source4"]}
        ]
    ]

    # Call function
    vectorize_extraction_process_step(project_id, process_step_id, filename, references)

    # Expected docs and metadata to add to ChromaDB
    expected_docs = ["test_file field1", "test_file field2"]
    expected_metadatas = [
        {
            "project_id": project_id,
            "process_step_id": process_step_id,
            "filename": filename,
            "reference": "source1\nsource2\nsource3"
        },
        {
            "project_id": project_id,
            "process_step_id": process_step_id,
            "filename": filename,
            "reference": "source4"
        }
    ]

    # Assertions
    mock_vectorstore.add_docs.assert_called_once_with(
        docs=expected_docs,
        metadatas=expected_metadatas,
        batch_size=5
    )

@patch('app.processing.process_queue.ChromaDB')  # Replace with the correct module path
def test_vectorize_extraction_process_step_empty_sources(mock_chroma_db):
    # Mock ChromaDB instance
    mock_vectorstore = MagicMock()
    mock_chroma_db.return_value = mock_vectorstore

    # Inputs
    project_id = 789
    process_step_id = 3
    filename = "empty_sources_file"
    references = [
        [
            {"name": "field1", "sources": []}
        ]
    ]

    # Call function
    vectorize_extraction_process_step(project_id, process_step_id, filename, references)

    # Expected no calls to add_docs due to empty sources
    mock_vectorstore.add_docs.assert_not_called()
