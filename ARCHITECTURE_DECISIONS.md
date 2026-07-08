# GENESIS OS

# Architecture Decisions

These decisions are FINAL.

Do not change them unless a new Architecture Decision Record explicitly replaces them.

---

## Runtime Language

Python 3.13

Status

LOCKED

---

## API

FastAPI

LOCKED

---

## CLI

Typer

LOCKED

---

## Architecture

Python-first

Plugin language independent

LOCKED

---

## Kernel

Kernel is orchestration only.

No business logic.

LOCKED

---

## Agent Runtime

Independent

DI only

LOCKED

---

## Workflow Runtime

Independent

LOCKED

---

## Storage

Repository Pattern

LOCKED

---

## Dependency Injection

Mandatory

No global singleton dependencies

LOCKED

---

## Database

Development

SQLite

Production

PostgreSQL

LOCKED

---

## Vector Store

Qdrant

LOCKED

---

## Cache

Redis

LOCKED

---

## Quality Gates

Every milestone requires

✓ Ruff

✓ Mypy

✓ Pytest

✓ Code Review

LOCKED

---

## Coding Rules

Production code only

No placeholders

No TODO

No mock architecture

LOCKED

---

## Branch Strategy

Main

Stable releases

phase-3

Current development

LOCKED