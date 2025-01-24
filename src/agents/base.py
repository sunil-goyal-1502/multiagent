from typing import Any, Optional, Dict
from datetime import datetime
import asyncio
from enum import Enum
import logging
from abc import ABC, abstractmethod

from src.utils.memory import AgentMemory
from src.utils.llm import LLMInterface
from src.utils.config import Config

logger = logging.getLogger(__name__)

class AgentRole(Enum):
    RESEARCHER = "researcher"
    WRITER = "writer"
    EDITOR = "editor"
    SEO = "seo"
    IMAGE = "image"
    PUBLISHER = "publisher"

class Message:
    def __init__(
        self,
        sender: Optional[AgentRole],
        receiver: AgentRole,
        content: Any,
        message_type: str = "task"
    ):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.message_type = message_type
        self.timestamp = datetime.now()
        self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique message ID."""
        return f"{self.timestamp.timestamp()}-{self.sender}-{self.receiver}"

    def to_dict(self) -> Dict:
        """Convert message to dictionary for storage."""
        return {
            "id": self.id,
            "sender": self.sender.value if self.sender else None,
            "receiver": self.receiver.value,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Message":
        """Create message from dictionary."""
        return cls(
            sender=AgentRole(data["sender"]) if data["sender"] else None,
            receiver=AgentRole(data["receiver"]),
            content=data["content"],
            message_type=data["message_type"]
        )

class BaseAgent(ABC):
    def __init__(
        self,
        role: AgentRole,
        config: Config,
        llm: Optional[LLMInterface] = None
    ):
        self.role = role
        self.config = config
        self.llm = llm or LLMInterface(config)
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.memory = AgentMemory(role, config)
        self.running = True
        self.agent_registry = {}
        
        logger.info(f"Initialized {role.value} agent")

    async def process_message(self, message: Message) -> Optional[Message]:
        """Process incoming message and generate response."""
        try:
            # Store message in memory
            await self.memory.store_interaction(message)
            
            # Process based on message type
            if message.message_type == "task":
                return await self._process_task(message)
            elif message.message_type == "query":
                return await self._process_query(message)
            elif message.message_type == "control":
                return await self._process_control(message)
            else:
                logger.warning(f"Unknown message type: {message.message_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return self._create_error_message(message, str(e))

    @abstractmethod
    async def _process_task(self, message: Message) -> Optional[Message]:
        """Process task-type messages."""
        pass

    async def _process_query(self, message: Message) -> Optional[Message]:
        """Process query-type messages."""
        return None

    async def _process_control(self, message: Message) -> Optional[Message]:
        """Process control-type messages."""
        if message.content.get("command") == "shutdown":
            self.running = False
            return None
        return None

    def _create_error_message(self, original_message: Message, error: str) -> Message:
        """Create error response message."""
        return Message(
            sender=self.role,
            receiver=original_message.sender,
            content={
                "error": error,
                "original_message_id": original_message.id
            },
            message_type="error"
        )

    async def run(self):
        """Main agent loop."""
        logger.info(f"Starting {self.role.value} agent")
        while self.running:
            try:
                message = await self.message_queue.get()
                response = await self.process_message(message)
                if response:
                    await self.send_message(response)
                self.message_queue.task_done()
            except Exception as e:
                logger.error(f"Error in agent loop: {e}")
                continue

    async def send_message(self, message: Message):
        """Send message to target agent."""
        target_agent = self.agent_registry.get(message.receiver)
        if target_agent:
            await target_agent.message_queue.put(message)
        else:
            logger.error(f"Target agent {message.receiver} not found")

    async def shutdown(self):
        """Shutdown the agent."""
        self.running = False
        await self.memory.save()
        logger.info(f"Shutdown {self.role.value} agent")
