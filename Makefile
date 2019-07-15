PYTHON = python3
RM = rm
PKG_NAME = rsp
ARCH_NAME = rsp

PRJ_DIR = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV ?= $(PRJ_DIR)venv
PKGVENV ?= $(PRJ_DIR)pkg_venv

install: $(VENV) setup.py
	$(VENV)/bin/python -m pip install -U .

$(VENV):
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -U wheel

uninstall: $(VENV)
	$(VENV)/bin/python -m pip uninstall -y $(PKG_NAME)

clean:
	$(RM) -rf $(VENV) $(PKGVENV) dist/ build/ $(PKG_NAME).egg-info/ .tox/ .coverage

$(PKGVENV):
	$(PYTHON) -m venv $(PKGVENV)
	$(PKGVENV)/bin/python -m pip install -U setuptools wheel twine

pkg: $(PKGVENV)
	$(PKGVENV)/bin/python setup.py sdist bdist_wheel

$(PKG_NAME).egg-info/PKG-INFO: $(PKGVENV)
	$(PKGVENV)/bin/python setup.py egg_info

version: $(PKG_NAME).egg-info/PKG-INFO
	@echo Evaluating pagkage version...
	$(eval PKG_VERSION := $(if $(PKG_VERSION),$(PKG_VERSION),$(shell grep -Po '(?<=^Version: ).*' $<)))
	@echo Version = $(PKG_VERSION)

upload: pkg version
	$(PKGVENV)/bin/python -m twine upload dist/$(PKG_NAME)-$(PKG_VERSION)*

testupload: pkg version
	$(PKGVENV)/bin/python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/$(PKG_NAME)-$(PKG_VERSION)*

archive: version
	git archive --prefix=$(ARCH_NAME)-$(PKG_VERSION)/ -o ../$(ARCH_NAME)-$(PKG_VERSION).tar.gz v$(PKG_VERSION)

.PHONY: install clean uninstall pkg version upload testupload archive
