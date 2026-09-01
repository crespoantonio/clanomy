---
story_id: "13.1"
epic_id: "13"
title: "GitHub Actions CI & 85%+ Coverage Enforcement"
status: "done"
priority: "high"
---

# Story 13.1: GitHub Actions CI & 85%+ Coverage Enforcement

## User Story
As a Developer,
I want every push and pull request validated by automated tests and coverage gates,
So that regressions are caught before merging into the master branch.

## Acceptance Criteria
- [x] Configure `.github/workflows/test.yml` running on push and PR to `master`.
- [x] Set up Python test runner with isolated SQLite and environment variables.
- [x] Execute all 347 unit and integration tests.
- [x] Enforce an **85% minimum code coverage threshold** with pytest-cov.
- [x] Fail workflow build on test regressions or coverage drops.

## Tasks / Subtasks
- [x] **CI Configuration** (AC: 1, 2, 3, 4)
  - [x] Author `.github/workflows/test.yml`.
- [x] **Coverage Tuning** (AC: 4, 5)
  - [x] Verify coverage configuration in `.coveragerc` or `pyproject.toml`.
- [x] **Pipeline Run**
  - [x] Validate green pipeline execution across all test suites.
