# Check that the version of make is 4.0 or later.
# Awk is more common than expr, skipping check if awk not found.
MIN_VERSION := 4.0
ifeq ($(shell which awk 2>&1 > /dev/null && echo true || echo false),true)
ifeq ($(shell awk -v n=$(MAKE_VERSION) -v m=$(MIN_VERSION) 'BEGIN {if (n < m) {exit 1} else {exit 0}}' && echo true || echo false),false)
$(error Your make version $(MAKE_VERSION) is too old. Please update to version $(MIN_VERSION) or later.)
endif
endif

# Function to ensure a tool is available from list of possible names.
# Aborts with error if none of the tools are found.
#
#   Arguments:
#
#     1: Variable name to store the tool binary path.
#
#     2: Space separated preference list of possible tool names.
#        If the variable is already set, the list is ignored.
#
#   Example:
#      $(call require_tool,CONTAINER_TOOL,podman docker)
#      $(shell $(CONTAINER_TOOL) system info)
#
#   Note: this function cannot be used to find Awk for Make version check,
#         because the function relies on newer Make features itself.
define require_tool
$(eval $(1) ?= $(2))
$(eval require_tool_ORIG := $($(1)))
$(eval $(1) := $(firstword $(foreach BIN,$($(1)),$(shell which $(BIN) 2> /dev/null))))
$(if $($(1)),,$(error None of ($(reqire_tool_ORIG)) found. Please install one of them before running make.))
endef

$(call require_tool,CONTAINER_TOOL,docker podman)
$(call require_tool,POETRY,poetry)
# $(call require_tool,FUSE_OVERLAYFS,fuse-overlayfs)

BASE_DIR ?= $(dir $(lastword $(MAKEFILE_LIST)))
BASE_DIR := $(abspath $(BASE_DIR))
POETRY_NO_INTERACTION ?= 1
POETRY_VIRTUALENVS_IN_PROJECT ?= 1
POETRY_VIRTUALENVS_CREATE ?= 1
POETRY_CACHE_DIR ?= /tmp/poetry_cache

PROJECT_NAME ?= $(shell $(POETRY) version | awk '{print $$1}')
PROJECT_VERSION ?= $(shell $(POETRY) version -s)

CONTAINER_IMAGE_TAG ?= $(PROJECT_NAME)/$(PROJECT_VERSION)
CONTAINER_WORKDIR ?= /home/app/workdir

.PHONY: test image

default: test

test: image
	$(CONTAINER_TOOL) run --rm -it $(CONTAINER_IMAGE_TAG)

image: Dockerfile
	$(CONTAINER_TOOL) build -t $(CONTAINER_IMAGE_TAG) .
