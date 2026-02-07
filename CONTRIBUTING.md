# Contributing to MA2 Forums Miner

Thank you for your interest in contributing to MA2 Forums Miner! This document provides guidelines and instructions for contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/ma2-forums-miner.git
   cd ma2-forums-miner
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

## Development Setup

### Dependencies

Install development dependencies:
```bash
pip install pylint pytest black isort
```

### Running Tests

Run the example script to verify functionality:
```bash
python examples.py
```

Test the CLI commands:
```bash
ma2-miner --help
ma2-miner scrape --help
ma2-miner cluster --help
ma2-miner stats --help
```

## Code Style

- Follow PEP 8 Python style guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and modular

### Linting

Run pylint before committing:
```bash
pylint src/ma2_miner
```

## Making Changes

1. **Create a branch** for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines

3. **Test your changes** thoroughly

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request** on GitHub

## Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Ensure all tests pass
- Update documentation if needed
- Keep changes focused and atomic

## Areas for Contribution

### High Priority
- Add unit tests for core modules
- Improve error handling and logging
- Add rate limiting and retry logic
- Support for multiple forum sections
- Export to different formats (CSV, SQLite)

### Medium Priority
- Web UI for viewing scraped data
- More clustering algorithms
- Thread content analysis
- Attachment metadata extraction

### Nice to Have
- Docker support
- API for accessing scraped data
- Real-time monitoring dashboard
- Integration with other forums

## Reporting Issues

When reporting issues, please include:
- Python version
- Operating system
- Full error message and stack trace
- Steps to reproduce
- Expected vs actual behavior

## Questions?

Feel free to open an issue for:
- Bug reports
- Feature requests
- Questions about the code
- General discussions

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Keep discussions on topic

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
