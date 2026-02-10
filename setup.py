from setuptools import setup, find_packages

setup(
    name="ma2-forums-miner",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "httpx[http2]>=0.25.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
        "tqdm>=4.66.0",
        "orjson>=3.9.0",
        "python-slugify>=8.0.0",
    ],
    entry_points={},
    python_requires=">=3.8",
)
