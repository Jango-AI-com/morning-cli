"""morning-cli — setup.

Built with the cli-anything 7-phase methodology; published under the
``morning-cli`` name for the Israeli dev community.

Two console scripts are registered:
  * ``morning-cli`` — primary user-facing command
  * ``cli-anything-greeninvoice`` — preserved alias for cli-anything methodology compat

Python package layout follows PEP 420 namespace packages under
``cli_anything/greeninvoice`` so multiple ``cli-anything-<software>``
packages can coexist in the same environment.
"""
from pathlib import Path

from setuptools import find_namespace_packages, setup

setup(
    name="morning-cli",
    version="0.1.2",
    description=(
        "Agent-native CLI for the morning invoicing REST API — "
        "66 endpoints, JSON envelopes, sandbox-first, built by JangoAI."
    ),
    long_description=Path("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="JangoAI",
    author_email="hello@jango-ai.com",
    url="https://github.com/jango-ai-com/morning-cli",
    project_urls={
        "Homepage": "https://jango-ai.com",
        "Source": "https://github.com/jango-ai-com/morning-cli",
        "Tracker": "https://github.com/jango-ai-com/morning-cli/issues",
        "morning API docs": "https://www.greeninvoice.co.il/api-docs",
    },
    license="MIT",
    python_requires=">=3.10",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    package_data={
        "cli_anything.greeninvoice": [
            "skills/*.md",
            "README.md",
        ],
    },
    install_requires=[
        "click>=8.1",
        "httpx>=0.27",
        "prompt-toolkit>=3.0",
        "rich>=13.0",
    ],
    extras_require={
        "test": ["pytest>=7"],
    },
    entry_points={
        "console_scripts": [
            # Primary command — this is what the community sees.
            "morning-cli=cli_anything.greeninvoice.greeninvoice_cli:cli",
            # Alias preserved so cli-anything methodology tooling (agent
            # discovery, skill registries) can still find the harness under
            # the conventional cli-anything-<software> name.
            "cli-anything-greeninvoice=cli_anything.greeninvoice.greeninvoice_cli:cli",
        ],
    },
    keywords=[
        "morning",
        "green-invoice",
        "greeninvoice",
        "invoicing",
        "israel",
        "rest-api",
        "cli",
        "agent",
        "cli-anything",
        "jangoai",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: Hebrew",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Office/Business :: Financial :: Accounting",
    ],
)
