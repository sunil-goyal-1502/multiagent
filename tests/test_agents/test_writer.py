import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from multiagent_content.agents import WriterAgent, AgentRole, Message
from multiagent_content.utils.config import Config

@pytest.fixture
def config():
    return Config({
        "llm": {
            "model": "gpt-4",
            "api_key": "test-key"
        },
        "agents": {
            "writer": {
                "style_guide": "technical",
                "tone": "professional",
                "min_word_count": 1000
            }
        }
    })

@pytest.fixture
def mock_content_generator():
    return Mock()

@pytest.fixture
def mock_style_guide():
    return Mock()

@pytest.fixture
def mock_template_manager():
    return Mock()

@pytest.fixture
def writer_agent(config, mock_content_generator, mock_style_guide, mock_template_manager):
    with patch('multiagent_content.agents.writer.ContentGenerator', return_value=mock_content_generator), \
         patch('multiagent_content.agents.writer.StyleGuide', return_value=mock_style_guide), \
         patch('multiagent_content.agents.writer.TemplateManager', return_value=mock_template_manager):
        agent = WriterAgent(config)
        return agent

@pytest.fixture
def sample_research_data():
    return {
        "main_points": [
            {"category": "overview", "content": "Point 1"},
            {"category": "details", "content": "Point 2"}
        ],
        "sources": [
            {"url": "url1", "title": "Source 1", "author": "Author 1"},
            {"url": "url2", "title": "Source 2", "author": "Author 2"}
        ],
        "statistics": [
            {"value": 42, "metric": "Metric 1", "confidence": 0.9},
            {"value": 73, "metric": "Metric 2", "confidence": 0.85}
        ],
        "trends": {
            "historical_data": ["trend1", "trend2"],
            "current_trends": ["current1", "current2"],
            "predictions": ["prediction1", "prediction2"]
        },
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "topic": "Test Topic"
        }
    }

@pytest.mark.asyncio
async def test_process_task_write_article(writer_agent, sample_research_data):
    message = Message(
        sender=AgentRole.RESEARCHER,
        receiver=AgentRole.WRITER,
        content={
            "research_data": sample_research_data,
            "topic": "Test Topic"
        }
    )
    
    # Mock article generation
    writer_agent.write_article = Mock()
    writer_agent.write_article.return_value = {
        "id": "test_article_123",
        "title": "Test Article",
        "introduction": "Intro text",
        "sections": [{"title": "Section 1", "content": "Content 1"}],
        "conclusion": "Conclusion text",
        "metadata": {"timestamp": datetime.now().isoformat()}
    }
    
    response = await writer_agent._process_task(message)
    
    assert response.sender == AgentRole.WRITER
    assert response.receiver == AgentRole.EDITOR
    assert "draft_article" in response.content
    assert "research_data" in response.content
    assert "metadata" in response.content

@pytest.mark.asyncio
async def test_write_article(writer_agent, sample_research_data):
    # Mock necessary methods
    writer_agent._create_outline = Mock()
    writer_agent._write_section = Mock()
    writer_agent._assemble_article = Mock()
    writer_agent.style_guide.apply = Mock()
    
    writer_agent._create_outline.return_value = [
        {"title": "Section 1", "type": "overview"},
        {"title": "Section 2", "type": "details"}
    ]
    
    writer_agent._write_section.return_value = {
        "title": "Section Title",
        "content": "Section Content",
        "type": "overview",
        "sources": []
    }
    
    writer_agent._assemble_article.return_value = {
        "id": "test_article_123",
        "title": "Test Article",
        "introduction": "Intro text",
        "sections": [{"title": "Section 1", "content": "Content 1"}],
        "conclusion": "Conclusion text",
        "metadata": {"timestamp": datetime.now().isoformat()}
    }
    
    article = await writer_agent.write_article(sample_research_data, "Test Topic")
    
    assert article["id"].startswith("article_")
    assert "title" in article
    assert "introduction" in article
    assert "sections" in article
    assert "conclusion" in article
    assert "metadata" in article
    
    writer_agent._create_outline.assert_called_once()
    assert writer_agent._write_section.call_count == 2
    writer_agent._assemble_article.assert_called_once()
    writer_agent.style_guide.apply.assert_called_once()

@pytest.mark.asyncio
async def test_create_outline(writer_agent, sample_research_data):
    writer_agent.template_manager.get_template.return_value = "outline_template"
    writer_agent.llm.generate.return_value = """
    [
        {"title": "Introduction", "type": "overview"},
        {"title": "Current State", "type": "analysis"},
        {"title": "Future Trends", "type": "prediction"}
    ]
    """
    writer_agent.content_generator.parse_outline.return_value = [
        {"title": "Introduction", "type": "overview"},
        {"title": "Current State", "type": "analysis"},
        {"title": "Future Trends", "type": "prediction"}
    ]
    
    outline = await writer_agent._create_outline(sample_research_data, "Test Topic")
    
    assert len(outline) == 3
    assert outline[0]["title"] == "Introduction"
    assert outline[1]["type"] == "analysis"
    writer_agent.template_manager.get_template.assert_called_once_with("outline")
    writer_agent.llm.generate.assert_called_once()

@pytest.mark.asyncio
async def test_write_section(writer_agent):
    section = {
        "title": "Test Section",
        "type": "overview",
        "keywords": ["key1", "key2"]
    }
    research_data = sample_research_data()
    outline = [section]
    
    writer_agent.template_manager.get_template.return_value = "section_template"
    writer_agent.llm.generate.return_value = "Generated section content"
    
    result = await writer_agent._write_section(section, research_data, outline)
    
    assert result["title"] == "Test Section"
    assert result["content"] == "Generated section content"
    assert result["type"] == "overview"
    assert "sources" in result

@pytest.mark.asyncio
async def test_get_section_data(writer_agent, sample_research_data):
    section = {
        "title": "Test Section",
        "type": "overview",
        "keywords": ["trend", "analysis"]
    }
    
    section_data = writer_agent._get_section_data(section, sample_research_data)
    
    assert "key_points" in section_data
    assert "statistics" in section_data
    assert "sources" in section_data

@pytest.mark.asyncio
async def test_error_handling(writer_agent):
    # Test with missing research data
    message = Message(
        sender=AgentRole.RESEARCHER,
        receiver=AgentRole.WRITER,
        content={"topic": "Test Topic"}  # Missing research_data
    )
    
    response = await writer_agent._process_task(message)
    assert response.message_type == "error"
    assert "No research data provided" in response.content["error"]
    
    # Test with LLM generation error
    writer_agent.llm.generate.side_effect = Exception("LLM Error")
    message.content["research_data"] = sample_research_data()
    
    response = await writer_agent._process_task(message)
    assert response.message_type == "error"
    assert "LLM Error" in response.content["error"]

@pytest.mark.asyncio
async def test_writing_history(writer_agent, sample_research_data):
    # Write first article
    await writer_agent.write_article(sample_research_data, "Topic 1")
    assert len(writer_agent.writing_history) == 1
    
    # Write second article
    await writer_agent.write_article(sample_research_data, "Topic 2")
    assert len(writer_agent.writing_history) == 2
    
    # Check history entry
    latest_entry = writer_agent.writing_history[-1]
    assert "topic" in latest_entry
    assert "timestamp" in latest_entry
    assert "outline" in latest_entry
    assert "article_id" in latest_entry

@pytest.mark.asyncio
async def test_metadata_creation(writer_agent):
    message = Message(
        sender=AgentRole.RESEARCHER,
        receiver=AgentRole.WRITER,
        content={
            "topic": "Test Topic",
            "research_data": sample_research_data()
        }
    )
    
    metadata = writer_agent._create_metadata(message)
    
    assert "original_topic" in metadata
    assert "research_timestamp" in metadata
    assert "writing_timestamp" in metadata
    assert "agent_version" in metadata
