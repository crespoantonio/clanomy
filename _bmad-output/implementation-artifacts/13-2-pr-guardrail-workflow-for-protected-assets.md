---
story_id: "13.2"
epic_id: "13"
title: "PR Guardrail Workflow for Protected Assets"
status: "done"
priority: "high"
---

# Story 13.2: PR Guardrail Workflow for Protected Assets

## User Story
As a Project Maintainer,
I want sensitive monetization, configuration, and CI files guarded against unauthorized modification,
So that critical system boundaries cannot be silently altered.

## Acceptance Criteria
- [x] Configure `.github/workflows/pr-guardrail.yml` triggered on pull requests.
- [x] Define protected regex patterns:
  - `^README\.md$`
  - `^src/services/subscription_service\.py$`
  - `^src/core/subscription_config\.py$`
  - `^docs/monetization-and-subscription-strategy\.md$`
  - `^\.github/workflows/`
- [x] Block merge when protected files are modified by non-admin actors.
- [x] Document guardrail expectations in `CONTRIBUTING.md`.

## Tasks / Subtasks
- [x] **Workflow Definition** (AC: 1, 2, 3)
  - [x] Author `.github/workflows/pr-guardrail.yml`.
- [x] **Documentation** (AC: 4)
  - [x] Update `CONTRIBUTING.md` with PR guardrail rules.
