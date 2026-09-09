# claude-statusbar — convenience wrapper around uv for Linux users.
# Windows and macOS:  uv sync  &&  uv run claude-statusbar --install

VENV := $(CURDIR)/.venv
PY   := $(VENV)/bin/python

.PHONY: install uninstall run xfce-plugin deps

install:
	@command -v uv >/dev/null || { echo "ERROR: uv not found -> https://docs.astral.sh/uv/"; exit 1; }
	@# The Xfce panel plugin embeds via XEmbed and therefore needs the system
	@# PyGObject; everything else comes from PyPI.  Hence a venv on the system
	@# interpreter with its site-packages visible.
	uv venv --python /usr/bin/python3 --system-site-packages --allow-existing $(VENV)
	@mkdir -p src/claude_statusbar/assets
	@cp logo.svg src/claude_statusbar/assets/logo.svg
	uv pip install --python $(PY) --quiet -e .
	@mkdir -p $(HOME)/.local/bin
	@printf '#!/bin/sh\nexec "%s" -m claude_statusbar "$$@"\n' "$(PY)" > $(HOME)/.local/bin/claude-statusbar
	@chmod +x $(HOME)/.local/bin/claude-statusbar
	@echo "installed $(HOME)/.local/bin/claude-statusbar"
	@echo
	@$(PY) -m claude_statusbar --install

uninstall:
	@[ -x "$(PY)" ] && $(PY) -m claude_statusbar --uninstall || true
	rm -f $(HOME)/.local/bin/claude-statusbar
	rm -rf $(VENV) $(HOME)/.cache/claude-statusbar
	@echo "removed the launcher, the venv and the desktop integration"
	@echo "settings kept — delete them by hand to purge"

run:
	@$(PY) -m claude_statusbar --tray

# Build dependencies for the native Xfce panel plugin (Debian/Ubuntu names).
deps:
	sudo apt-get install -y gcc pkg-config libgtk-3-dev libxfce4panel-2.0-dev librsvg2-common

# Compile and register the panel module; needs root for the two system files.
xfce-plugin:
	@$(PY) -m claude_statusbar --install-xfce-plugin
