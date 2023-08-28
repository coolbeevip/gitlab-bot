init:
	pip install . '.[lint]' '.[test]' '.[package]' --default-timeout=600 -i https://pypi.tuna.tsinghua.edu.cn/simple

lint:
	@pflake8 ./bot

fmt:
	@black ./src
	@isort --profile black ./src
	@pflake8 ./src

i18n:
	xgettext -d base -o src/locales/bot.pot *.py
	msgfmt -o src/locales/en/LC_MESSAGES/bot.mo src/locales/en/LC_MESSAGES/bot.po
	msgfmt -o src/locales/zh/LC_MESSAGES/bot.mo src/locales/zh/LC_MESSAGES/bot.po

docker-build:
	export DOCKER_BUILDKIT=1
	docker build -t git-bot --cache-from git-bot --build-arg BUILDKIT_INLINE_CACHE=1 .