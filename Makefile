DELETE_ON_ERROR:

env:
	python -m virtualenv env

requirements:
	pip install -r requirements-dev.txt
	pip install -r requirements.txt

lint:
	python -m pylint protect_with_atakama
	black protect_with_atakama

test:
	PYTHONPATH=. pytest --cov protect_with_atakama --cov-fail-under=100 --cov-report term-missing -v tests

install-hooks:
	pre-commit install

.PHONY: test requirements lint publish install-hooks
