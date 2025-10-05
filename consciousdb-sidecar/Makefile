.PHONY: run test fmt lint docker

run:
	uvicorn api.main:app --reload --port 8080

test:
	pytest -q

fmt:
	python -m pip install ruff black
	ruff check --fix . || true
	black .

docker:
	docker build -t consciousdb-sidecar:dev -f ops/Dockerfile .

docker-build:
	docker build -t consciousdb-sidecar:dev -f ops/Dockerfile .

docker-build-extras:
	docker build --build-arg OPTIONAL_EXTRAS="$(EXTRAS)" -t consciousdb-sidecar:extras -f ops/Dockerfile .
