# Contributing to GramDB

First off, thank you for considering contributing to GramDB! It's people like you that make GramDB such a great tool.

## 📜 Standards and Rules

To maintain a high-quality codebase, we follow a set of strict rules for all contributions:

### 1. Code Standards
- **Python Version**: All code must be compatible with Python 3.10+.
- **Style**: Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/). Use `black` or `ruff` for formatting.
- **Async/Await**: GramDB is an asynchronous library. Ensure all I/O operations are non-blocking.
- **Documentation**: 
    - Every file MUST have a header comment explaining its purpose.
    - Every class and public method MUST have a docstring.
    - Use clear, descriptive variable and function names.

### 2. Pull Request Process
1. **Fork the Repository**: Create a fork and a new branch for your feature or bugfix.
2. **Write Code**: Implement your changes following the standards above.
3. **Tests**: Ensure existing tests pass and add new tests for your changes.
4. **Submit PR**: Provide a clear title and description of what your PR does.
5. **Review**: Wait for maintainers to review your PR. Address any feedback promptly.

### 3. Commit Message Guidelines
- Use the imperative mood ("Add feature" not "Added feature").
- Keep the subject line short (under 50 characters).
- Mention related issues if applicable.

## 🛠 Development Setup

1. Clone your fork.
2. Create a virtual environment: `python -m venv venv`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run tests: `python test.py`.

## 🤝 Questions?

If you have any questions, feel free to open an issue for discussion.

---

Happy Coding! 🚀
