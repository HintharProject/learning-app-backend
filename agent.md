# Agent Guidelines: Rules of Engagement & Constraints

This document defines the coding standards, architectural constraints, and strict operational boundaries for any AI agent working on this codebase.

---

## 1. Architectural Stack & Constraints

* **Backend Framework**: Django & Django REST Framework (DRF).
* **Database**: PostgreSQL (Neon).
* **Authentication**: Clerk Authentication (sole authentication provider).
* **API Documentation**: OpenAPI 3.0 specification generated dynamically via `drf-spectacular`.
* **API Versioning**: Base path must be `/api/v1/`.
* **Hosting Target**: Designed for deployment on Render.

---

## 2. Authentication & User Syncing

* **Sole Authentication Provider**: Clerk.
* **Authentication Flow**:
  1. The frontend authenticates with Clerk and receives a JWT.
  2. The frontend sends this JWT in the `Authorization: Bearer <token>` header of API requests.
  3. The Django backend intercepts and validates the JWT.
* **Local User Model**:
  * Must store the `clerk_id` (used as the unique mapping identifier) and the application-level `role`.
  * Local user attributes (`email`, `full_name`, `avatar_url`) should be synced/populated based on Clerk identity data.
  * Role mapping matches: `ADMIN`, `CREATOR`, `STUDENT`.
  * Users cannot modify their own roles; only users with the `ADMIN` role are permitted to modify roles.

---

## 3. Data Integrity & Operational Boundaries

* **Immutable Historical Learning Records**:
  * Records representing progress and history (`Enrollment`, `LessonProgress`, `StudentQuizAttempt`, `StudentQuizAnswer`) must **never** be physically deleted.
  * Soft-delete state changes (using flags like `status_active = False` or state machines) must be used.
  * Database-level cascading deletes (`CASCADE`) are **strictly prohibited** for any model tied directly or indirectly to Historical Learning Records to prevent accidental data loss.
* **Derived State Principles**:
  * Derived values (e.g., Module unlock state, Module completion, Course completion, Quiz progress percentages) must be calculated dynamically on the fly rather than duplicated/persisted.
* **Course and Content Lifecycle**:
  * Follow state machine transitions strictly: `DRAFT` &rarr; `PENDING_APPROVAL` &rarr; `PUBLISHED` &rarr; `ARCHIVED`.
  * When a Course is in `PUBLISHED` state, creators may add *new* Modules and Lessons, but editing of existing structures (titles, video URLs, quiz questions/options) is blocked.

---

## 4. Coding & DRF Design Standards

* **Standard API Error format**: Use native Django REST Framework (DRF) JSON schemas for validation errors.
* **API-First Architecture**: Ensure all endpoints are designed with clear input validation and serialization logic. 
* **Ordering Restraints**: Enforce continuous, unique, and deterministic ordering validations for models using manual ordering (e.g., Modules, Lessons, Questions).
* **Testing**: Write comprehensive unit/integration tests targeting the serializer validations, state transitions, and custom authorization permissions.
