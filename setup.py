from setuptools import setup, find_packages

setup(
    name="ma2-forums-miner",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "aiohttp>=3.13.3",
        "aiofiles>=23.2.1",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "sentence-transformers>=2.2.0",
        "hdbscan>=0.8.33",
        "numpy>=1.24.0",
        "scikit-learn>=1.3.0",
        "tqdm>=4.66.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "ma2-miner=ma2_miner.cli:main",
        ],
    },
    python_requires=">=3.8",
)
