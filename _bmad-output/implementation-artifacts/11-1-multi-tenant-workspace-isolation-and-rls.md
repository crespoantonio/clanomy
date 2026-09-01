---
story_id: "11.1"
epic_id: "11"
title: "Multi-Tenant Workspace Isolation & RLS"
status: "done"
priority: "high"
---

# Story 11.1: Multi-Tenant Workspace Isolation & RLS

## User Story
As a Security Officer,
I want strict workspace isolation when members leave a family group,
So that no orphaned data or external credentials are ever leaked across households.

## Acceptance Criteria
- [x] In `FamilyService.leave_family()`, remove orphaned family recycling queries.
- [x] Always instantiate a fresh `Family` record with clean Notion credentials (`notion_api_key=None`, `notion_database_id=None`).
- [x] Create Alembic migration `0004_enable_rls_security.py` enabling row-level security on PostgreSQL tables.
- [x] Add migration `0003_add_user_is_admin.py` to enforce admin scoping.
- [x] Verify complete isolation with dedicated audit tests in `tests/unit/test_security_audit_hardening.py` (`test_sec01_leave_family_tenant_isolation`).

## Tasks / Subtasks
- [x] **FamilyService Hardening** (AC: 1, 2)
  - [x] Update `leave_family()` in `src/services/family_service.py` (SEC-01 remediation).
- [x] **Database Migrations** (AC: 3, 4)
  - [x] Review `0003_add_user_is_admin.py` and `0004_enable_rls_security.py`.
- [x] **Security Testing** (AC: 5)
  - [x] Verify tenant isolation in unit tests.
