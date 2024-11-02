init:
	pip install . '.[lint]' '.[test]' '.[package]'

lint:
	@pflake8 ./src

fmt:
	@black ./src
	@isort --profile black ./src
	@$(MAKE) lint

coverage: lint
	@pytest --cov=an_copilot tests

i18n:
	xgettext -d base -o src/locales/gitlab-bot.pot *.py
	msgfmt -o src/locales/en/LC_MESSAGES/gitlab-bot.mo src/locales/en/LC_MESSAGES/gitlab-bot.po
	msgfmt -o src/locales/zh/LC_MESSAGES/gitlab-bot.mo src/locales/zh/LC_MESSAGES/gitlab-bot.po

docker-build:
	export DOCKER_BUILDKIT=1
	docker build -t coolbeevip/gitlab-bot --cache-from coolbeevip/gitlab-bot --build-arg BUILDKIT_INLINE_CACHE=1 .