init:
	pip install . '.[lint]' '.[test]' '.[package]' --default-timeout=600 -i https://pypi.tuna.tsinghua.edu.cn/simple

lint:
	@pflake8 ./bot

fmt:
	@black ./src
	@isort --profile black ./src
	@pflake8 ./src

i18n:
	xgettext -d base -o src/locales/gitlab-bot.pot *.py
	msgfmt -o src/locales/en/LC_MESSAGES/gitlab-bot.mo src/locales/en/LC_MESSAGES/gitlab-bot.po
	msgfmt -o src/locales/zh/LC_MESSAGES/gitlab-bot.mo src/locales/zh/LC_MESSAGES/gitlab-bot.po

docker-build:
	export DOCKER_BUILDKIT=1
	docker build -t coolbeevip/gitlab-bot --cache-from coolbeevip/gitlab-bot --build-arg BUILDKIT_INLINE_CACHE=1 .