# CODING_STANDARDS.md

# GENESIS OS

## Official Coding Standards

Version: 1.0

---

# Purpose

This document defines the mandatory coding standards for all GENESIS OS source code.

Every implementation must follow these rules.

---

# General Principles

* Write clean, readable code.
* Prefer simplicity over cleverness.
* Keep modules small and focused.
* Avoid duplicated logic.
* Every public component must be documented.
* Every feature must be testable.

---

# Architecture Rules

* Follow the architectural documents in the `/docs` directory.
* Do not modify the sealed Core Architecture.
* Runtime components extend functionality without changing the core.
* Use dependency injection where appropriate.
* Prefer composition over inheritance.

---

# Naming Conventions

## Files

Use snake_case.

Examples:

```
plugin_manager.py
runtime_engine.py
execution_queue.py
```

---

## Classes

Use PascalCase.

Examples:

```
PluginManager
RuntimeEngine
TaskScheduler
```

---

## Functions

Use snake_case.

Examples:

```
load_plugin()
execute_task()
validate_request()
```

---

## Variables

Use descriptive snake_case names.

Good:

```
plugin_registry
execution_context
runtime_configuration
```

Avoid:

```
x
tmp
data2
```

---

# Project Structure

```
src/
    core/
    runtime/
    plugins/
    plugin_sdk/
    api/
    cli/
    ui/
    config/
    database/
    services/
    utils/
    tests/
```

---

# File Size

Recommended:

* Maximum: 500 lines

Preferred:

* 150–300 lines

Split large files into multiple modules.

---

# Function Size

Recommended:

* 20–40 lines

Maximum:

* 80 lines

One function should perform one responsibility.

---

# Class Size

Recommended:

* One responsibility
* Cohesive behavior
* Minimal public interface

---

# Error Handling

Never ignore exceptions.

Always:

* log the error
* provide useful context
* return structured errors when appropriate

Avoid silent failures.

---

# Logging

Use structured logging.

Every log should include:

* timestamp
* severity
* module
* event
* message

Supported levels:

* DEBUG
* INFO
* WARNING
* ERROR
* CRITICAL

---

# Security

Always:

* validate inputs
* sanitize external data
* check permissions
* isolate plugins
* protect secrets

Never:

* hardcode passwords
* hardcode API keys
* expose internal stack traces
* trust external input

---

# Plugin Standards

Every plugin must provide:

* unique identifier
* semantic version
* metadata
* dependency list
* permission list
* configuration schema

Plugins must be sandboxed.

Plugins must never modify the Core Architecture.

---

# API Standards

* Use REST conventions.
* Return JSON responses.
* Use appropriate HTTP status codes.
* Version APIs.
* Validate every request.

Example:

```
GET /api/v1/plugins

POST /api/v1/tasks

DELETE /api/v1/plugins/{id}
```

---

# Testing Standards

Every module should include:

* Unit Tests
* Integration Tests (when applicable)

Target minimum coverage:

* 80%

Critical runtime modules:

* 95%+

---

# Documentation

Every public class, function, and module should include documentation.

Every major subsystem should include:

* purpose
* responsibilities
* inputs
* outputs
* limitations

---

# Git Standards

Branch examples:

```
feature/plugin-manager

feature/runtime-engine

bugfix/api-auth

release/v1.0.0
```

Commit message format:

```
feat:

fix:

docs:

refactor:

test:

perf:

build:

chore:
```

---

# Performance Guidelines

* Avoid unnecessary allocations.
* Prefer asynchronous I/O for network operations.
* Cache expensive computations when appropriate.
* Minimize startup time.
* Optimize only after measurement.

---

# Code Review Checklist

Before merging:

* Architecture respected
* Tests passing
* Documentation updated
* No duplicated logic
* Security reviewed
* Performance acceptable
* Linting passed
* Formatting passed

---

# Definition of Done

A feature is complete only if:

* Implementation finished
* Tests written and passing
* Documentation updated
* Code reviewed
* Build successful
* No known critical defects

---

# Final Principle

Every line of code should improve the maintainability, reliability, and extensibility of GENESIS OS.

Quality is mandatory.

---

END OF DOCUMENT
