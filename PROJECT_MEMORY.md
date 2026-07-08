# GENESIS OS

# PROJECT_MEMORY

**Version:** 1.0

**Purpose**

This document is the long-term memory of the project.

It records architectural reasoning, important historical decisions, lessons learned, rejected approaches, and project evolution.

This file must survive all future milestones.

---

# Project Vision

GENESIS OS is an open-source AI Development Operating System.

The objective is not to build another AI assistant.

The objective is to build a complete execution platform capable of planning, orchestrating, executing, validating and improving complex software projects through multiple cooperating AI agents.

---

# Core Principles

These principles must never be violated.

* Simplicity over complexity.
* Clean architecture.
* Production quality only.
* Test before merge.
* Dependency Injection everywhere.
* Strong module isolation.
* Stable public interfaces.
* Small incremental milestones.

---

# Architectural History

## Initial Design

Early concepts considered multiple implementation languages.

Decision:

Python became the core runtime language.

Reason:

Highest ecosystem maturity for AI systems.

Status:

Permanent.

---

## Runtime

Decision:

Agent Runtime and Workflow Runtime remain independent.

Reason:

Loose coupling.

Future extensibility.

Independent testing.

Status:

Permanent.

---

## Kernel

Decision:

Kernel is orchestration only.

Kernel never contains business logic.

Reason:

Kernel stability.

Low maintenance.

Predictable lifecycle.

Status:

Permanent.

---

## Storage

Decision:

Repository Pattern everywhere.

Reason:

Database independence.

Simple testing.

Replaceable persistence layer.

Status:

Permanent.

---

## Plugin System

Decision:

Python-first.

Plugin-language independent.

Reason:

Maximum flexibility.

Future SDK support.

Status:

Permanent.

---

# Lessons Learned

## Small Milestones

Large patches increase review cost.

Future work should remain incremental.

---

## Every Milestone Must Finish Clean

Required:

* Ruff
* Mypy
* Pytest

before merge.

---

## Never Skip Tests

Passing tests are mandatory before every commit.

---

## No Temporary Architecture

Avoid temporary implementations.

Avoid placeholders.

Avoid unfinished abstractions.

---

# Rejected Ideas

## Fat Kernel

Rejected.

Reason:

Creates tight coupling.

---

## Global State

Rejected.

Reason:

Breaks testing.

---

## Hidden Dependencies

Rejected.

Reason:

Breaks maintainability.

---

## Business Logic Inside Infrastructure

Rejected.

Reason:

Violates architecture boundaries.

---

# Project Roles

## Project Manager

ChatGPT

Responsibilities:

* Architecture
* Technical decisions
* Quality review
* Roadmap
* Scope control

---

## Implementation

Claude Code

Responsibilities:

* Produce code
* Refactor
* Generate tests
* Maintain style

---

## Executive Manager

Artin

Responsibilities:

* Execute terminal commands
* Apply patches
* Validate outputs
* Git operations
* Report execution results
* Coordinate development workflow

---

# Current State

Current Phase

Phase 6

Latest Completed Milestone

GEN-0025

Repository Status

Healthy

Tests

Passing

Architecture

Stable

---

# Future Direction

Knowledge Graph

↓

Semantic Memory

↓

Context Engine

↓

Reasoning Layer

↓

Planning Improvements

↓

Self-Improving Development System

---

# Rules For Future AI Systems

Any future AI working on GENESIS OS must:

* Read PROJECT_STATE.md first.
* Read ARCHITECTURE_DECISIONS.md second.
* Read PROJECT_MEMORY.md third.
* Read PM_HANDOFF.md before making any changes.
* Never redesign stable architecture without an explicit Architecture Decision Record (ADR).
* Preserve backward compatibility unless an approved breaking-change plan exists.
* Keep milestones small, reviewable, and fully tested.

---

# Update Policy

PROJECT_MEMORY.md is updated only when one of the following occurs:

* A major architectural decision is finalized.
* A significant lesson is learned.
* A design approach is permanently rejected.
* Project roles or governance change.
* A milestone fundamentally changes the direction of the system.

Minor implementation details should not be recorded here.
