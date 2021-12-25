#!/bin/bash
pip install -r requirements_test.txt
pre-commit install
pre-commit install --hook-type commit-msg
