PYTHON := python
PIP := pip
VENV ?= .venv

SRC := src
REQ := requirements.txt

REGION ?= eu-north-1
ACCOUNT ?= 436682557138
ECR_REPO ?= dragman/autogigification
IMAGE ?= $(ECR_REPO):latest
ECR_URI := $(ACCOUNT).dkr.ecr.$(REGION).amazonaws.com/$(ECR_REPO)

.PHONY: help venv deps clean login build tag push

help:
	@echo "make venv     - create virtualenv"
	@echo "make deps     - install dependencies into venv"
	@echo "make clean    - remove build artifacts"
	@echo "make docker-build - build Lambda container image"
	@echo "make docker-push  - push image to ECR"

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

venv: $(VENV)/bin/activate
	@echo "Virtualenv ready at $(VENV)"

deps: venv
	. $(VENV)/bin/activate && $(PIP) install --upgrade pip && $(PIP) install .

clean:
	rm -rf build $(REQ)

login:
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(ACCOUNT).dkr.ecr.$(REGION).amazonaws.com

build:
	docker buildx build --platform linux/amd64 -t $(IMAGE) .

tag: build
	docker tag $(IMAGE) $(ECR_URI):latest

push: login tag
	docker push $(ECR_URI):latest

run: build
	docker run --env-file .env -p 9000:8080 ${ECR_REPO}