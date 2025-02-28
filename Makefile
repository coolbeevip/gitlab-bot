init:
	@pip install -e .

lint:
	@poetry run ruff check

fmt:
	@poetry run ruff format

test: lint
	@poetry run pytest tests

i18n:
	xgettext -d base -o src/locales/gitlab-bot.pot *.py
	msgfmt -o src/locales/en/LC_MESSAGES/gitlab-bot.mo src/locales/en/LC_MESSAGES/gitlab-bot.po
	msgfmt -o src/locales/zh/LC_MESSAGES/gitlab-bot.mo src/locales/zh/LC_MESSAGES/gitlab-bot.po

docker:
	export DOCKER_BUILDKIT=1
	docker build -t coolbeevip/gitlab-bot --cache-from coolbeevip/gitlab-bot --build-arg BUILDKIT_INLINE_CACHE=1 .