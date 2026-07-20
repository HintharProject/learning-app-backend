# Learning Management System API (LMS Backend)

This is the API-first backend repository for the Learning Management System (LMS) MVP, built using **Django**, **Django REST Framework (DRF)**, **PostgreSQL (Aiven for test, Neon for production)**, and authenticated via **Clerk**.

## Overview

The LMS MVP is designed to serve as the backend application handling user roles, courses, module-based progression, lessons, quiz attempts, study plans, and enrollment management.

For the detailed specifications, please refer to:
* [spec.md](spec.md) - The Master Blueprint containing the database schema, business rules, and API specifications.
* [agent.md](agent.md) - The Rules of Engagement defining coding standards, architectural constraints, and operational boundaries.

---

## Technical Stack
* **Framework**: Django & Django REST Framework (DRF)
* **Authentication**: Clerk Integration
* **Database**: PostgreSQL (Aiven for test, Neon Serverless for production)
* **Documentation**: OpenAPI 3.0 via `drf-spectacular` (Swagger UI & ReDoc)
* **Deployment Target**: Render

---

## Local Development Setup

### 1. Prerequisites
* Python 3.10+
* PostgreSQL client or local PostgreSQL instance (optional; SQLite is used for local dev, Aiven/Neon for deployed environments)

### 2. Installation
Clone the repository and set up a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows Powershell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the configuration template:
```bash
cp .env.example .env
```
Fill in the environment variables (Database URL, Secret Key, and Clerk API keys).

### 4. Database Setup & Migrations
```bash
python manage.py migrate
```

### 5. Running the Server
```bash
python manage.py runserver
```
The API will be available locally at `http://127.0.0.1:8000/api/v1/`.

### 6. Interactive API Documentation
* **Swagger UI**: `/api/v1/schema/swagger-ui/`
* **ReDoc**: `/api/v1/schema/redoc/`
