UV ?= uv
UV_REQUIRED_VERSION := 0.10.11

.PHONY: check-uv init lint fmt test i18n docker

check-uv:
	@command -v $(UV) >/dev/null 2>&1 || { echo "uv is required. Install uv $(UV_REQUIRED_VERSION) before continuing."; exit 1; }
	@actual_version="$$( $(UV) --version 2>/dev/null | awk '{print $$2}' )"; \
		if [ "$$actual_version" != "$(UV_REQUIRED_VERSION)" ]; then \
			echo "uv $(UV_REQUIRED_VERSION) is required (found $$actual_version)."; \
			exit 1; \
		fi

init: check-uv
	@$(UV) sync --frozen

lint: check-uv
	@$(UV) run ruff check

fmt: check-uv
	@$(UV) run ruff format

test: lint
	@$(UV) run pytest tests

i18n:
	xgettext -d base -o src/locales/gitlab-bot.pot *.py
	msgfmt -o src/locales/en/LC_MESSAGES/gitlab-bot.mo src/locales/en/LC_MESSAGES/gitlab-bot.po
	msgfmt -o src/locales/zh/LC_MESSAGES/gitlab-bot.mo src/locales/zh/LC_MESSAGES/gitlab-bot.po

docker:
	export DOCKER_BUILDKIT=1
	docker build -t coolbeevip/gitlab-bot --cache-from coolbeevip/gitlab-bot --build-arg BUILDKIT_INLINE_CACHE=1 .
