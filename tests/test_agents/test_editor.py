import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.agents.editor import EditorAgent, AgentRole, Message
from src.utils.config import Config

@pytest.fixture
def config():
    return Config({
        "llm": {
            "model": "gpt-4",
            "api_key": "test-key"
        },
        "agents": {
            "editor": {
                "grammar_checker": "default",
                "style_guide": "technical"
            }
        }
    })

@pytest.fixture
def mock_grammar_checker():
    return Mock()

@pytest.fixture
def mock_style_checker():
    return Mock()

@pytest.fixture
def mock_content_analyzer():
    return Mock()

@pytest.fixture
def editor_agent(config, mock_grammar_checker, mock_style_checker, mock_content_analyzer):
    with patch('multiagent_content.agents.editor.GrammarChecker', return_value=mock_grammar_checker), \
         patch('multiagent_content.agents.editor.StyleChecker', return_value=mock_style_checker), \
         patch('multiagent_content.agents.editor.ContentAnalyzer', return_value=mock_content_analyzer):
        agent = EditorAgent(config)
        return agent

@pytest.fixture
def sample_article():
    return {
        "id": "test_article_123",
        "title": "Test Article",
        "introduction": "This is the introduction.",
        "sections": [
            {
                "title": "Section 1",
                "content": "This is section 1 content."
            },
            {
                "title": "Section 2",
                "content": "This is section 2 content."
            }
        ],
        "conclusion": "This is the conclusion.",
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "author": "Writer Agent"
        }
    }

@pytest.mark.asyncio
async def test_process_task_edit_article(editor_agent, sample_article):
    message = Message(
        sender=AgentRole.WRITER,
        receiver=AgentRole.EDITOR,
        content={
            "draft_article": sample_article,
            "research_data": {"key": "value"}
        }
    )
    
    # Mock edit_article method
    editor_agent.edit_article = Mock()
    editor_agent.edit_article.return_value = {
        **sample_article,
        "quality_score": 0.85,
        "edit_metadata": {
            "grammar_improvements": 2,
            "style_improvements": 1,
            "content_improvements": 1,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    response = await editor_agent._process_task(message)
    
    assert response.sender == AgentRole.EDITOR
    assert response.receiver == AgentRole.SEO
    assert "edited_article" in response.content
    assert "original_research" in response.content
    assert "editing_metadata" in response.content

@pytest.mark.asyncio
async def test_check_grammar(editor_agent, sample_article):
    editor_agent.grammar_checker.check_text.side_effect = [
        [{"type": "spelling", "message": "Error 1"}],  # For title
        [{"type": "grammar", "message": "Error 2"}],   # For introduction
        [{"type": "punctuation", "message": "Error 3"}],  # For section 1
        [],  # For section 2
        [{"type": "grammar", "message": "Error 4"}]    # For conclusion
    ]
    
    issues = await editor_agent._check_grammar(sample_article)
    
    assert len(issues) == 4
    assert any(issue["location"] == "title" for issue in issues)
    assert any(issue["location"] == "introduction" for issue in issues)
    assert editor_agent.grammar_checker.check_text.call_count == 5

@pytest.mark.asyncio
async def test_check_style(editor_agent, sample_article):
    editor_agent.style_checker.check_text.side_effect = [
        [{"type": "tone", "message": "Style Error 1"}],
        [{"type": "word_choice", "message": "Style Error 2"}]
    ]
    
    editor_agent.style_checker.check_tone_consistency.return_value = [
        {"type": "inconsistency", "message": "Tone varies"}
    ]
    
    issues = await editor_agent._check_style(sample_article)
    
    assert len(issues) > 0
    assert any(issue["type"] == "tone" for issue in issues)
    assert any(issue["type"] == "word_choice" for issue in issues)
    assert any(issue["type"] == "inconsistency" for issue in issues)

@pytest.mark.asyncio
async def test_analyze_content(editor_agent, sample_article):
    research_data = {
        "main_points": ["point1", "point2"],
        "statistics": ["stat1", "stat2"]
    }
    
    editor_agent._check_factual_accuracy.return_value = [
        {"type": "factual_accuracy", "description": "Fact needs verification"}
    ]
    
    editor_agent._check_content_flow.return_value = [
        {"type": "flow", "description": "Transition needed"}
    ]
    
    editor_agent._check_coverage.return_value = [
        {"type": "coverage", "description": "Missing key point"}
    ]
    
    issues = await editor_agent._analyze_content(sample_article, research_data)
    
    assert len(issues) == 3
    assert any(issue["type"] == "factual_accuracy" for issue in issues)
    assert any(issue["type"] == "flow" for issue in issues)
    assert any(issue["type"] == "coverage" for issue in issues)

@pytest.mark.asyncio
async def test_check_factual_accuracy(editor_agent, sample_article):
    research_data = {
        "main_points": [
            {"text": "Point 1", "confidence": 0.9},
            {"text": "Point 2", "confidence": 0.8}
        ]
    }
    
    editor_agent.content_analyzer.extract_facts.return_value = [
        {"text": "Fact 1", "location": "section_0"},
        {"text": "Fact 2", "location": "section_1"}
    ]
    
    issues = await editor_agent._check_factual_accuracy(sample_article, research_data)
    
    assert isinstance(issues, list)
    assert all("type" in issue for issue in issues)
    assert all("severity" in issue for issue in issues)
    assert all("description" in issue for issue in issues)

@pytest.mark.asyncio
async def test_fix_grammar(editor_agent, sample_article):
    grammar_issues = [
        {
            "location": "title",
            "description": "Spelling error",
            "severity": "high",
            "auto_fix": "Fixed Title"
        },
        {
            "location": "section_0",
            "description": "Grammar error",
            "severity": "medium",
            "auto_fix": "Fixed Section Content"
        }
    ]
    
    fixed_article = await editor_agent._fix_grammar(sample_article, grammar_issues)
    
    assert fixed_article["title"] == "Fixed Title"
    assert fixed_article["sections"][0]["content"] == "Fixed Section Content"
    assert fixed_article["sections"][1]["content"] == sample_article["sections"][1]["content"]

@pytest.mark.asyncio
async def test_fix_style(editor_agent, sample_article):
    style_issues = [
        {
            "location": "introduction",
            "description": "Tone inconsistency",
            "severity": "medium",
            "suggested_fix": "Fixed Introduction"
        }
    ]
    
    editor_agent.style_checker.apply_fix.return_value = "Fixed Introduction"
    
    fixed_article = await editor_agent._fix_style(sample_article, style_issues)
    
    assert fixed_article["introduction"] == "Fixed Introduction"
    assert fixed_article != sample_article

@pytest.mark.asyncio
async def test_improve_content(editor_agent, sample_article):
    content_issues = [
        {
            "type": "flow",
            "location": "section_0",
            "description": "Add transition",
            "suggestion": "With this in mind,"
        },
        {
            "type": "coverage",
            "location": "section_1",
            "description": "Expand point",
            "suggestion": "Additional content needed"
        }
    ]
    
    editor_agent._improve_section_content = Mock()
    editor_agent._improve_section_content.side_effect = [
        "Improved Section 1",
        "Improved Section 2"
    ]
    
    improved_article = await editor_agent._improve_content(sample_article, content_issues)
    
    assert improved_article != sample_article
    assert editor_agent._improve_section_content.call_count == 2

@pytest.mark.asyncio
async def test_assess_quality(editor_agent, sample_article):
    editor_agent.grammar_checker.get_score.return_value = 0.9
    editor_agent.style_checker.get_score.return_value = 0.85
    editor_agent.content_analyzer.get_score.return_value = 0.95
    
    quality_score = await editor_agent._assess_quality(sample_article)
    
    assert 0 <= quality_score <= 1
    assert editor_agent.grammar_checker.get_score.called
    assert editor_agent.style_checker.get_score.called
    assert editor_agent.content_analyzer.get_score.called

@pytest.mark.asyncio
async def test_error_handling(editor_agent):
    # Test with missing article
    message = Message(
        sender=AgentRole.WRITER,
        receiver=AgentRole.EDITOR,
        content={"research_data": {}}  # Missing draft_article
    )
    
    response = await editor_agent._process_task(message)
    assert response.message_type == "error"
    assert "No draft article provided" in response.content["error"]
    
    # Test with grammar checker error
    editor_agent.grammar_checker.check_text.side_effect = Exception("Grammar check failed")
    
    message.content["draft_article"] = sample_article()
    response = await editor_agent._process_task(message)
    assert response.message_type == "error"
    assert "Grammar check failed" in response.content["error"]

@pytest.mark.asyncio
async def test_edit_history(editor_agent, sample_article):
    # Perform first edit
    await editor_agent.edit_article(sample_article, {})
    assert len(editor_agent.edit_history) == 1
    
    # Perform second edit
    await editor_agent.edit_article(sample_article, {})
    assert len(editor_agent.edit_history) == 2
    
    # Check history entry
    latest_entry = editor_agent.edit_history[-1]
    assert "article_id" in latest_entry
    assert "timestamp" in latest_entry
    assert "improvements" in latest_entry
    assert "quality_score" in latest_entry

@pytest.mark.asyncio
async def test_formatting_issues(editor_agent):
    raw_issues = [
        {"message": "Error 1", "severity": "high"},
        {"message": "Error 2", "severity": "medium"}
    ]
    
    location = "section_0"
    formatted_issues = editor_agent._format_issues(location, raw_issues)
    
    assert len(formatted_issues) == len(raw_issues)
    assert all("location" in issue for issue in formatted_issues)
    assert all(issue["location"] == location for issue in formatted_issues)

@pytest.mark.asyncio
async def test_group_issues_by_section(editor_agent):
    issues = [
        {"location": "title", "message": "Error 1"},
        {"location": "section_0", "message": "Error 2"},
        {"location": "section_0", "message": "Error 3"},
        {"location": "conclusion", "message": "Error 4"}
    ]
    
    grouped = editor_agent._group_issues_by_section(issues)
    
    assert "title" in grouped
    assert "section_0" in grouped
    assert "conclusion" in grouped
    assert len(grouped["section_0"]) == 2

@pytest.mark.asyncio
async def test_create_editing_metadata(editor_agent):
    message = Message(
        sender=AgentRole.WRITER,
        receiver=AgentRole.EDITOR,
        content={
            "draft_article": {
                "id": "test_123",
                "title": "Test"
            }
        }
    )
    
    metadata = editor_agent._create_editing_metadata(message)
    
    assert "editor_version" in metadata
    assert "timestamp" in metadata
    assert "original_article_id" in metadata
    assert metadata["original_article_id"] == "test_123"
