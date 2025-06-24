#!/bin/bash

# Добавляем корень проекта в PYTHONPATH
export PYTHONPATH="$PYTHONPATH:$(pwd)"

# Остальные команды без изменений
python -m venv venv
source venv/bin/activate
pip install -r requirements/dev.txt
