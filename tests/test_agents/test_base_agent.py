import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from src.agents.base import BaseAgent, AgentRole, Message
from src.utils.config import Config

@pytest.fixture
def config():
    return Config({
        "llm": {
            "model": "gpt-4",
            "api_key": "test-key"
        },
        "agents": {
            "researcher": {
                "search_apis": ["google"],
                "max_sources": 10,
                "tools": ["web_search", "academic_search"]
            },
            "writer": {
                "max_tokens": 1000,
                "temperature": 0.7,
                "style_guide": "technical",
                "tone": "professional",
                "tools": ["content_gen", "rewriter"]
            },
            "editor": {
                "grammar_checker": "default",
                "style_guide": "technical",
                "review_threshold": 0.8,
                "tools": ["grammar", "style_check"]
            },
            "seo": {
                "keywords_count": 5,
                "tools": ["keyword_research", "meta_tags"],
                "target_score": 80
            },
            "image": {
                "generation_model": "dall-e-3",
                "tools": ["image_gen", "image_edit"]
            },
            "publisher": {
                "platforms": ["wordpress"],
                "tools": ["cms_api", "scheduler"]
            }
        }
    })

@pytest.fixture
def mock_llm():
    return Mock()

@pytest.fixture
def base_agent(config, mock_llm):
    class TestAgent(BaseAgent):
        async def _process_task(self, message):
            return Message(
                sender=self.role,
                receiver=AgentRole.WRITER,
                content={"processed": True}
            )
    
    return TestAgent(AgentRole.RESEARCHER, config, mock_llm)

@pytest.mark.asyncio
async def test_agent_initialization(base_agent):
    assert base_agent.role == AgentRole.RESEARCHER
    assert isinstance(base_agent.message_queue, asyncio.Queue)
    assert base_agent.running is True

@pytest.mark.asyncio
async def test_process_message_task(base_agent):
    message = Message(
        sender=AgentRole.WRITER,
        receiver=AgentRole.RESEARCHER,
        content={"test": "data"},
        message_type="task"
    )
    
    response = await base_agent.process_message(message)
    assert response.sender == AgentRole.RESEARCHER
    assert response.receiver == AgentRole.WRITER
    assert response.content == {"processed": True}

@pytest.mark.asyncio
async def test_process_message_query(base_agent):
    message = Message(
        sender=AgentRole.WRITER,
        receiver=AgentRole.RESEARCHER,
        content={"query": "test"},
        message_type="query"
    )
    
    response = await base_agent.process_message(message)
    assert response is None

@pytest.mark.asyncio
async def test_process_message_control_shutdown(base_agent):
    message = Message(
        sender=None,
        receiver=AgentRole.RESEARCHER,
        content={"command": "shutdown"},
        message_type="control"
    )
    
    response = await base_agent.process_message(message)
    assert response is None
    assert base_agent.running is False

@pytest.mark.asyncio
async def test_send_message(base_agent):
    target_agent = Mock()
    base_agent.agent_registry = {AgentRole.WRITER: target_agent}
    
    message = Message(
        sender=AgentRole.RESEARCHER,
        receiver=AgentRole.WRITER,
        content={"test": "data"}
    )
    
    await base_agent.send_message(message)
    target_agent.message_queue.put.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_run_agent(base_agent):
    # Set up test messages
    messages = [
        Message(
            sender=AgentRole.WRITER,
            receiver=AgentRole.RESEARCHER,
            content={"test": "data1"}
        ),
        Message(
            sender=AgentRole.WRITER,
            receiver=AgentRole.RESEARCHER,
            content={"test": "data2"}
        )
    ]
    
    # Add messages to queue
    for message in messages:
        await base_agent.message_queue.put(message)
    
    # Mock send_message
    base_agent.send_message = Mock()
    
    # Run agent for a short time
    task = asyncio.create_task(base_agent.run())
    await asyncio.sleep(0.1)  # Let it process messages
    base_agent.running = False  # Stop the agent
    await task
    
    # Verify messages were processed
    assert base_agent.send_message.call_count == 2

@pytest.mark.asyncio
async def test_error_handling(base_agent):
    # Create a message that will cause an error
    error_message = Message(
        sender=AgentRole.WRITER,
        receiver=AgentRole.RESEARCHER,
        content=None  # This will cause an error in processing
    )
    
    response = await base_agent.process_message(error_message)
    assert response.message_type == "error"
    assert "error" in response.content

@pytest.mark.asyncio
async def test_message_to_dict(base_agent):
    message = Message(
        sender=AgentRole.WRITER,
        receiver=AgentRole.RESEARCHER,
        content={"test": "data"},
        message_type="task"
    )
    
    message_dict = message.to_dict()
    assert message_dict["sender"] == AgentRole.WRITER.value
    assert message_dict["receiver"] == AgentRole.RESEARCHER.value
    assert message_dict["content"] == {"test": "data"}
    assert message_dict["message_type"] == "task"
    assert "timestamp" in message_dict

@pytest.mark.asyncio
async def test_message_from_dict(base_agent):
    message_dict = {
        "sender": "writer",
        "receiver": "researcher",
        "content": {"test": "data"},
        "message_type": "task",
        "timestamp": datetime.now().isoformat()
    }
    
    message = Message.from_dict(message_dict)
    assert message.sender == AgentRole.WRITER
    assert message.receiver == AgentRole.RESEARCHER
    assert message.content == {"test": "data"}
    assert message.message_type == "task"

@pytest.mark.asyncio
async def test_agent_shutdown(base_agent):
    await base_agent.shutdown()
    assert base_agent.running is False
