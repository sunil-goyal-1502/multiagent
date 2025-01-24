# multiagent
Multiagent AI system

# Multi-Agent AI Content Creation System

A sophisticated multi-agent system that automates end-to-end content creation using specialized AI agents.

## Overview

This system uses multiple AI agents working together to automate the content creation pipeline:
- Research gathering and analysis
- Content writing
- Editing and proofreading
- SEO optimization
- Image creation
- Publishing

Each agent is specialized in its task and communicates with others through a message queue system.

## Architecture

![Screenshot 2025-01-24 115655](https://github.com/user-attachments/assets/03bd1a6f-6ce9-40b2-8ae8-af027efc5aa8)

The system consists of:
- Multiple specialized AI agents
- Shared memory system
- Message queue for communication
- External system integrations
- Conflict resolution system

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/multiagent-content-system.git

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example config
cp config.example.yml config.yml

# Update config.yml with your API keys and settings
```

## Configuration

Update `config.yml` with your settings:

```yaml
llm:
  model: gpt-4
  api_key: your_openai_api_key

agents:
  researcher:
    search_apis:
      - google
      - scopus
    max_sources: 10
  
  writer:
    style_guide: default
    tone: professional
  
  editor:
    grammar_checker: grammarly
    style_guide: chicago

  seo:
    tools:
      - semrush
      - ahrefs
    
  image:
    generator: dall-e
    style: modern

  publisher:
    platforms:
      - wordpress
      - medium

memory:
  short_term_size: 100
  storage_path: ./data/memory
```

## Usage

Basic usage:

```python
from multiagent_content.pipeline import ContentPipeline

async def main():
    # Initialize the pipeline
    pipeline = ContentPipeline()
    
    # Start content creation
    await pipeline.start_pipeline(
        topic="AI in Healthcare",
        style_guide="technical",
        target_length=2000
    )

if __name__ == "__main__":
    asyncio.run(main())
```

See the [documentation](docs/README.md) for advanced usage and customization.

## Project Structure

```
├── docs/                      # Documentation
├── examples/                  # Example usage
├── src/        # Main package
│   ├── agents/               # Agent implementations
│   ├── memory/               # Memory management
│   ├── pipeline/             # Orchestration
│   └── utils/                # Utilities
├── tests/                    # Test cases
├── config.example.yml        # Example configuration
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

## Development

Setting up for development:

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linting
flake8 multiagent_content tests
```

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- OpenAI for GPT-4 API
- Various research papers on multi-agent systems
- Open source community

## Citation

If you use this system in your research, please cite:

```bibtex
@software{multiagent_content_system,
  author = {Sunil Goyal},
  title = {Multi-Agent AI Content Creation System},
  year = {2025},
  url = {https://github.com/sunil-goyal-1502/multiagent-content-system}
}
```
