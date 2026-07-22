from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="api-ghost-hunter",
    version="2.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A bug bounty tool for discovering, archiving, and hunting ghost API endpoints",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/api-ghost-hunter",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "pyyaml>=6.0",
        "beautifulsoup4>=4.11.0",
        "lxml>=4.9.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "api-ghost-hunter=api_ghost_hunter.cli:main",
            "agh=api_ghost_hunter.cli:main",
        ],
    },
)
