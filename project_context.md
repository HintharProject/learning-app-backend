# Project Context & Audit Summary

This document serves as a high-level context summary for any new AI agents joining the project. Reading this minimizes the need to scan all project files to understand the current state, recent architectural changes, and core decisions.

## 1. Project Stack & Core Specifications
- **Framework**: Django & Django REST Framework (DRF)
- **Database**: PostgreSQL (Neon Serverless for prod, SQLite for local dev). 
- **Auth Provider**: Clerk (JWT based).
- **Core Documentation**:
  - `spec.md`: The Master Blueprint (contains ERD, Business Rules, API endpoints).
  - `agent.md`: Constraints and coding standards for agents.

## 2. Authentication & User Model Refactor
- **Initial Flaw**: The system originally required a `clerk_id` to create a User, making it difficult to create Admin users purely via Django admin.
- **The Fix**: The `User` model was refactored to make `clerk_id` nullable, and `email` was set as the `USERNAME_FIELD`.
- **Lazy Syncing**: The `users/authentication.py` logic was updated. When a user authenticates via Clerk, the backend extracts the email from the JWT. If a local user exists with that email but lacks a `clerk_id`, the backend automatically binds the `clerk_id` to that user on their first login.

## 3. Quiz Architecture Optimization (JSON Refactor)
- **Initial Flaw**: Quizzes used a highly nested relational database (`Quiz` -> `Question` -> `Option` -> `StudentQuizAttempt` -> `StudentQuizAnswer`). This caused massive N+1 query performance issues and was extremely complex for frontend bulk submissions. Additionally, correct answers were leaking to students.
- **The Fix (Hybrid JSON approach)**:
  - **Deleted Models**: `Question`, `Option`, `StudentQuizAnswer` tables were completely wiped.
  - **Quiz Model**: A `questions` `JSONField` was added to store the entire array of questions and options. A `passing_percentage` field was added to govern future module unlocking logic.
  - **StudentQuizAttempt Model**: An `answers_submitted` `JSONField` was added.
- **API Simplification**: Students no longer make individual API calls per answer. Instead, they make a single `POST` to `/api/v1/quizzes/{quiz_id}/attempts/{id}/submit/` containing all answers. The backend grades it instantly and stores the raw `score` and `passed` boolean.
- **Security Patch**: The `QuizSerializer` was overridden so that if the requesting user has the `STUDENT` role, the backend automatically strips the `is_correct` key from the JSON payload, preventing students from cheating by inspecting the network tab.

## 4. Operational Boundaries
- **Immutability**: Historical learning records (`Enrollment`, `LessonProgress`, `StudentQuizAttempt`) must **never** be physically deleted. Soft-delete only.
- **Derived State**: Values like completion percentages, unlock availability, or module completion are derived dynamically on the fly; they are never persisted as static DB columns.
- **Ordering**: Entities that are manually ordered (e.g., Modules, Lessons) enforce deterministic ordering validations.

## 5. Next Steps / Current Status
- The database migrations for the User and Quiz refactors have been successfully applied.
- The local development server runs stably with no errors.
- The Admin panel is ready to register users and quizzes via the new schema.
- Agent instructions: Refer to `spec.md` for specific domain rules before making major architectural deviations.
