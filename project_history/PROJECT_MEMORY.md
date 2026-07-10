# GENESIS OS - PROJECT MEMORY

This file stores permanent architectural knowledge for the project.

---

## Core Architecture

Architecture Style

Clean Architecture

Dependency Injection

Repository Pattern

Plugin Architecture

Kernel Isolation

Agent Isolation

Workflow Driven Execution

---

## Mandatory Rules

Kernel never depends on Runtime.

Runtime never depends on Storage implementation.

Everything is resolved through Dependency Injection.

Repository Pattern is mandatory.

Atomic Patch only.

Production Quality only.

No Placeholder code.

No Breaking API.

Every milestone must keep previous compatibility.

---

## Completed Integrations

Database Layer

Repository Layer

Dependency Injection Container

Knowledge Graph

Memory Service

Redis Short-Term Memory

Qdrant Vector Memory

---

## Development Workflow

Claude generates an Atomic Patch.

↓

Project Manager reviews architecture.

↓

Patch is applied with git am.

↓

Ruff

↓

mypy

↓

pytest

↓

Git Push

↓

Milestone Closed

No patch is merged without architectural approval.

---

## Current Validation

Tests:
228 Passed

Coverage:
96%

Ruff:
PASS

mypy:
PASS

---

## Current Stable Milestones

Milestone 6
Knowledge Graph Foundation

Milestone 7
Knowledge Memory Integration

Milestone 8
Production Memory Backends Integration

---

## Current Next Goal

Phase 6

Milestone 9

Memory Integration Validation