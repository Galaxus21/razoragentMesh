"""Setup script for razoragent_buyer_sdk."""

from setuptools import find_packages, setup

setup(
    name="razoragent_buyer_sdk",
    version="2.0.0",
    description="Autonomous AI Buyer Agent SDK for RazorAgent Mesh v2.0 (AP2 + x402 + Ed25519)",
    author="RazorAgent Mesh Team",
    packages=find_packages(include=["razoragent_buyer_sdk", "razoragent_buyer_sdk.*"]),
    python_requires=">=3.10",
    install_requires=[
        "pynacl>=1.5.0",
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "respx>=0.21.0",
        ],
    },
)
