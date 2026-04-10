#!/bin/bash
uv sync --group test
pre-commit install
pre-commit install --hook-type commit-msg
