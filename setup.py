#!/usr/bin/env python3

from setuptools import setup, find_packages
import os

# Read README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
def read_requirements(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith("#") and not line.startswith("-r")
        ]

setup(
    name="offline-proxy",
    version="1.0.0",
    author="Zhou",
    author_email="",
    description="A multi-protocol offline proxy tool for caching and serving network resources",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yorelog/offline-proxy",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": read_requirements("requirements-dev.txt"),
    },
    entry_points={
        "console_scripts": [
            "offline-proxy=offline_proxy.cli.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "offline_proxy": [
            "config/*.yaml",
            "templates/*.html",
        ],
    },
    zip_safe=False,
)