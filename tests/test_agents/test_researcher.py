import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from ...src.agents.researcher import ResearchAgent
from ...src.agents.base import AgentRole, Message
from ...src.utils.config import Config

@pytest.fixture
def config():
    return Config({
        "llm": {
            "model": "gpt-4",
            "api_key": "test-key"
        },
        "agents": {
            "researcher": {
                "search_apis": ["google", "scopus"],
                "max_sources": 10,
                "cache_ttl_hours": 24
            }
        }
    })

@pytest.fixture
def mock_search_api():
    return Mock()

@pytest.fixture
def mock_content_analyzer():
    return Mock()

@pytest.fixture
def mock_source_validator():
    return Mock()

@pytest.fixture
def researcher_agent(config, mock_search_api, mock_content_analyzer, mock_source_validator):
    with patch('multiagent_content.agents.researcher.SearchAPI', return_value=mock_search_api), \
         patch('multiagent_content.agents.researcher.ContentAnalyzer', return_value=mock_content_analyzer), \
         patch('multiagent_content.agents.researcher.SourceValidator', return_value=mock_source_validator):
        agent = ResearchAgent(config)
        return agent

@pytest.mark.asyncio
async def test_process_task_research_topic(researcher_agent):
    message = Message(
        sender=None,
        receiver=AgentRole.RESEARCHER,
        content={"research_topic": "AI in Healthcare"}
    )
    
    # Mock research methods
    researcher_agent.gather_research = Mock()
    researcher_agent.gather_research.return_value = {
        "main_points": ["point1", "point2"],
        "sources": ["source1", "source2"],
        "statistics": ["stat1", "stat2"],
        "trends": ["trend1", "trend2"]
    }
    
    response = await researcher_agent._process_task(message)
    
    assert response.sender == AgentRole.RESEARCHER
    assert response.receiver == AgentRole.WRITER
    assert "research_data" in response.content
    assert response.content["topic"] == "AI in Healthcare"
    researcher_agent.gather_research.assert_called_once_with("AI in Healthcare")

@pytest.mark.asyncio
async def test_gather_research(researcher_agent, mock_search_api):
    # Setup mock responses
    mock_search_api.search.return_value = [
        {"url": "url1", "title": "title1"},
        {"url": "url2", "title": "title2"}
    ]
    
    mock_search_api.fetch_content.side_effect = ["content1", "content2"]
    
    researcher_agent.source_validator.is_reliable.return_value = True
    researcher_agent.content_analyzer.extract_key_points.return_value = ["point1", "point2"]
    
    research_data = await researcher_agent.gather_research("test topic")
    
    assert "main_points" in research_data
    assert "sources" in research_data
    assert "statistics" in research_data
    assert "trends" in research_data
    assert "metadata" in research_data
    assert research_data["metadata"]["topic"] == "test topic"

@pytest.mark.asyncio
async def test_extract_key_points(researcher_agent, mock_search_api):
    mock_search_api.search.return_value = [
        {"url": "url1", "title": "title1"}
    ]
    mock_search_api.fetch_content.return_value = "test content"
    researcher_agent.source_validator.is_reliable.return_value = True
    researcher_agent.content_analyzer.extract_key_points.return_value = ["point1", "point2"]
    
    key_points = await researcher_agent.extract_key_points("test topic")
    
    assert len(key_points) == 2
    assert key_points == ["point1", "point2"]
    mock_search_api.search.assert_called_once()
    mock_search_api.fetch_content.assert_called_once_with("url1")

@pytest.mark.asyncio
async def test_find_reliable_sources(researcher_agent, mock_search_api):
    mock_search_api.search_academic.return_value = [
        {
            "url": "url1",
            "title": "title1",
            "author": "author1",
            "published_date": "2024-01-01",
            "citation_count": 10
        }
    ]
    researcher_agent.source_validator.is_reliable.return_value = True
    
    sources = await researcher_agent.find_reliable_sources("test topic")
    
    assert len(sources) == 1
    assert sources[0]["url"] == "url1"
    assert sources[0]["title"] == "title1"
    assert sources[0]["citation_count"] == 10
    mock_search_api.search_academic.assert_called_once()

@pytest.mark.asyncio
async def test_gather_statistics(researcher_agent, mock_search_api):
    mock_search_api.search_statistics.return_value = [
        {
            "value": 42,
            "metric": "test_metric",
            "source": "test_source",
            "year": 2024,
            "confidence": 0.9
        }
    ]
    researcher_agent.source_validator.verify_statistic.return_value = True
    
    stats = await researcher_agent.gather_statistics("test topic")
    
    assert len(stats) == 1
    assert stats[0]["value"] == 42
    assert stats[0]["metric"] == "test_metric"
    mock_search_api.search_statistics.assert_called_once()

@pytest.mark.asyncio
async def test_cache_functionality(researcher_agent):
    # First request - should perform full research
    researcher_agent.search_api.search.return_value = [{"url": "url1"}]
    researcher_agent.source_validator.is_reliable.return_value = True
    researcher_agent.content_analyzer.extract_key_points.return_value = ["point1"]
    
    await researcher_agent.gather_research("test topic")
    assert researcher_agent.search_api.search.call_count == 1
    
    # Second request - should use cache
    researcher_agent.search_api.search.reset_mock()
    await researcher_agent.gather_research("test topic")
    assert researcher_agent.search_api.search.call_count == 0
    
    # Simulate cache expiration
    cache_key = researcher_agent._generate_cache_key("test topic")
    researcher_agent.research_cache[cache_key]["timestamp"] = \
        datetime.now() - timedelta(hours=25)
    
    # Third request - should perform new research
    await researcher_agent.gather_research("test topic")
    assert researcher_agent.search_api.search.call_count == 1

@pytest.mark.asyncio
async def test_error_handling(researcher_agent):
    # Test with invalid topic
    message = Message(
        sender=None,
        receiver=AgentRole.RESEARCHER,
        content={}  # Missing research_topic
    )
    
    response = await researcher_agent._process_task(message)
    assert response.message_type == "error"
    assert "No research topic provided" in response.content["error"]
    
    # Test with API error
    researcher_agent.search_api.search.side_effect = Exception("API Error")
    message.content = {"research_topic": "test topic"}
    
    response = await researcher_agent._process_task(message)
    assert response.message_type == "error"
    assert "API Error" in response.content["error"]

@pytest.mark.asyncio
async def test_deduplication(researcher_agent):
    # Create duplicate key points
    points = [
        {"category": "cat1", "content": "point1"},
        {"category": "cat1", "content": "point1"},  # Duplicate
        {"category": "cat2", "content": "point2"}
    ]
    
    unique_points = researcher_agent._deduplicate_points(points)
    assert len(unique_points) == 2
    assert unique_points[0]["content"] == "point1"
    assert unique_points[1]["content"] == "point2"
