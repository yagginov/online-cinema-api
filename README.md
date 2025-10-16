# 🎬 Online Cinema API

A RESTful API for an online cinema platform built with FastAPI, featuring payment processing, content management, and user-centric functionality.

## 📋 Table of Contents

- [Features](#features)
- [Technologies](#technologies)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Development Team](#development-team)

## ✨ Features

- **Movie Management**: Browse movie catalog with filtering and pagination
- **Authentication System**: JWT-based authentication with access/refresh tokens
- **User Profiles**: User profile management
- **Shopping Cart**: Add movies to cart
- **Favorites**: Favorite movies list
- **Order System**: Create and manage orders
- **Stripe Payments**: Stripe payment gateway integration
- **Email Notifications**: Asynchronous email sending via Celery
- **File Storage**: Image and media file storage via MinIO
- **Background Tasks**: Asynchronous task processing via Celery + Redis

## 🛠 Technologies

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **Python 3.12** - Programming language
- **SQLAlchemy** - ORM for database operations
- **Alembic** - Database migrations
- **Pydantic** - Data validation

### Database
- **PostgreSQL** - Primary database
- **Redis** - Caching and task queues

### Infrastructure
- **Docker & Docker Compose** - Containerization
- **Celery** - Asynchronous tasks
- **Gunicorn** - WSGI HTTP server
- **MinIO** - S3-compatible object storage (optional)

### Integrations
- **Stripe** - Payment gateway
- **MailHog** - Email testing (development)
- **pgAdmin** - PostgreSQL administration

### Testing and Code Quality
- **Pytest** - Testing framework
- **Black** - Code formatting
- **isort** - Import sorting
- **MyPy** - Static type checking

## 📦 Requirements

- Docker >= 20.10
- Docker Compose >= 2.0
- PostgreSQL >= 14 (if running without Docker)
- Redis >= 7.0 (if running without Docker)
- Python 3.12
- Poetry for dependency management

**Note:** This project is designed to run with Docker. All services (PostgreSQL, Redis, Celery, MailHog) are containerized.

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/online-cinema-api.git
cd online-cinema-api
```

### 2. Environment configuration

Create a `.env` file based on `.env.sample`:

```bash
cp .env.sample .env
```

Edit the `.env` file and set the required values. Here are the main environment variables:

```env
# PostgreSQL
POSTGRES_DB=movies_db
POSTGRES_DB_PORT=5432
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=postgres_cinema

# pgAdmin
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=your_pgadmin_password

# Redis
REDIS_HOST=redis_cinema
REDIS_PORT=6379
REDIS_DB=0

# Celery
CELERY_BROKER_URL=redis://redis_cinema:6379/0
CELERY_RESULT_BACKEND=redis://redis_cinema:6379/0

# Stripe (get your keys at https://stripe.com)
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Payment redirect URLs
PAYMENT_SUCCESS_URL=http://localhost:8000/api/v1/payments/success?session_id={CHECKOUT_SESSION_ID}
PAYMENT_CANCEL_URL=http://localhost:8000/api/v1/payments/cancel

# JWT
SECRET_KEY_ACCESS=your_secret_access_key_min_32_chars
SECRET_KEY_REFRESH=your_secret_refresh_key_min_32_chars
JWT_SIGNING_ALGORITHM=HS256

# MailHog (for email testing in development)
MAILHOG_USER=admin
MAILHOG_PASSWORD=your_mailhog_password

# Email settings
EMAIL_HOST=mailhog_cinema
EMAIL_PORT=1025
EMAIL_HOST_USER=testuser
EMAIL_HOST_PASSWORD=test_password
EMAIL_USE_TLS=False

# MinIO (Optional - for file storage)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=your_minio_password
MINIO_HOST=minio-cinema
MINIO_PORT=9000
MINIO_STORAGE=cinema-storage
```

**Important:** Change all default passwords and secret keys before deploying to production!

## 🏃 Running the Project

### Development Environment

```bash
# Start all services in development mode
docker-compose up -d

# Or use the local development configuration
docker-compose -f docker-compose-local.yml up -d

# View logs
docker-compose logs -f

# View logs for a specific service
docker-compose logs -f web

# Stop services
docker-compose down

# Stop services and remove volumes (clean slate)
docker-compose down -v
```

After starting, the following services are available:
- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc
- **pgAdmin**: http://localhost:3333
- **MailHog UI**: http://localhost:8025

### Useful Commands

```bash
# Rebuild containers after dependency changes
docker-compose up -d --build

# Execute commands inside the web container
docker-compose exec web bash

# Run database migrations
docker-compose exec web alembic upgrade head

# Create a new migration
docker-compose exec web alembic revision --autogenerate -m "your_migration_message"

# View Celery worker logs
docker-compose logs -f celery_worker

# Restart a specific service
docker-compose restart web
```

## 📚 API Documentation

### Interactive API Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs - Interactive API testing interface
- **ReDoc**: http://localhost:8000/redoc - Clean, readable API documentation

Both documentation interfaces are automatically generated from the code and stay in sync with your API.

### Main endpoints

#### Authentication (`/api/v1/accounts`)
```
POST   /api/v1/accounts/register                    - User registration
GET    /api/v1/accounts/activate                    - Activate user account
POST   /api/v1/accounts/password-reset/request      - Request password reset token
POST   /api/v1/accounts/reset-password/complete     - Complete password reset
POST   /api/v1/accounts/login                       - User login
POST   /api/v1/accounts/refresh                     - Refresh access token
POST   /api/v1/accounts/logout                      - User logout
```

#### Profiles (`/api/v1/profiles`)
```
POST   /api/v1/profiles/users/{user_id}/profile     - Create user profile
```

#### Movies (`/api/v1/cinema`)
```
GET    /api/v1/cinema/movies/                       - List movies (with filters)
GET    /api/v1/cinema/movies/search/                - Search movies
GET    /api/v1/cinema/movies/{movie_id}             - Get movie details
POST   /api/v1/cinema/movies/                       - Create movie (admin)
PATCH  /api/v1/cinema/movies/{movie_id}             - Update movie (admin)
DELETE /api/v1/cinema/movies/{movie_id}             - Delete movie (admin)
```

#### Shopping Cart
```
GET    /api/v1/users/{user_id}/shopping-cart/                      - Get shopping cart
POST   /api/v1/users/{user_id}/shopping-cart/add/{movie_id}       - Add movie to cart
DELETE /api/v1/users/{user_id}/shopping-cart/remove/{movie_id}    - Remove movie from cart
DELETE /api/v1/users/{user_id}/shopping-cart/delete               - Clear shopping cart
```

#### Favorites
```
GET    /api/v1/favorites/                           - List user's favorite movies
POST   /api/v1/favorites/{movie_id}                 - Add movie to favorites
DELETE /api/v1/favorites/{movie_id}                 - Remove movie from favorites
```

#### Orders
```
POST   /api/v1/orders/                              - Create order
GET    /api/v1/orders/                              - List user's orders
GET    /api/v1/orders/{order_id}                    - Get order details
DELETE /api/v1/orders/{order_id}                    - Cancel order
```

#### Payments
```
POST   /api/v1/payments/                            - Create payment (get Stripe checkout URL)
POST   /api/v1/payments/webhook                     - Stripe webhook handler
GET    /api/v1/payments/success                     - Payment success redirect
GET    /api/v1/payments/cancel                      - Payment cancel redirect
GET    /api/v1/payments/                            - List user's payments
GET    /api/v1/admin/payments/                      - Admin: list all payments
```

## 📁 Project Structure

```
online-cinema-api/
├── src/
│   ├── celery_background/     # Celery tasks and configurations
│   ├── config/                # Application configuration files
│   ├── database/              # Database layer
│   │   ├── models/            # SQLAlchemy models
│   │   ├── migrations/        # Alembic migrations
│   │   ├── seed_data/         # Database seed files
│   │   ├── validators/        # Database validators
│   │   ├── session_postgresql.py
│   │   └── session_sqlite.py
│   ├── enums/                 # Enumerations
│   ├── exceptions/            # Custom exceptions
│   ├── filters/               # Query filters for endpoints
│   ├── notifications/         # Email notification handlers
│   ├── repositories/          # Database repositories (Data Access Layer)
│   ├── routes/                # API route handlers
│   │   ├── accounts.py        # Authentication endpoints
│   │   ├── movies.py          # Movie management endpoints
│   │   ├── cart.py            # Shopping cart endpoints
│   │   ├── favorites.py       # Favorites endpoints
│   │   ├── orders.py          # Order management endpoints
│   │   ├── payments.py        # Payment processing endpoints
│   │   └── profiles.py        # User profile endpoints
│   ├── schemas/               # Pydantic schemas for validation
│   │   ├── accounts/          # Account-related schemas
│   │   ├── favorites/         # Favorites schemas
│   │   ├── movies/            # Movie schemas
│   │   ├── orders/            # Order schemas
│   │   └── profiles/          # Profile schemas
│   ├── security/              # JWT authentication and security
│   ├── services/              # Business logic layer
│   ├── storages/              # MinIO/S3 file storage integration
│   ├── tests/                 # Unit and integration tests
│   ├── validation/            # Custom validators
│   └── main.py                # FastAPI application entry point
├── commands/                  # Shell scripts for deployment
│   ├── run_web_server_dev.sh
│   ├── run_web_server_prod.sh
│   ├── run_celery_worker.sh
│   ├── run_celery_beat.sh
│   ├── run_migration.sh
│   ├── setup_mailhog_auth.sh
│   ├── setup_minio.sh
│   └── deploy.sh
├── docker/                    # Docker-related configurations
│   └── mailhog/              # MailHog Dockerfile
├── .env.sample                # Environment variables template
├── .env                       # Environment variables (not in git)
├── .gitignore                 # Git ignore rules
├── docker-compose.yml         # Main Docker Compose configuration
├── docker-compose-local.yml   # Local development configuration
├── docker-compose-prod.yml    # Production configuration
├── Dockerfile                 # Main application Dockerfile
├── pyproject.toml             # Poetry dependencies
├── poetry.lock                # Locked dependencies
├── alembic.ini                # Alembic migrations configuration
├── alembic-docker.ini         # Alembic config for Docker
├── init.sql                   # Initial database setup script
└── README.md                  # Project documentation
```

## 🧪 Testing

### Running tests

```bash
# Run all tests
pytest

# Run with code coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest src/tests/test_movies.py
```

### Linters and formatting

```bash
# Format code
black src/

# Sort imports
isort src/

# Type checking
mypy src/
```

## 🔒 Security

- JWT tokens for authentication
- Password hashing with bcrypt
- CORS middleware configured
- SQL injection protection via SQLAlchemy ORM
- Input data validation via Pydantic

## 🚢 Deployment

### Docker Compose Configurations

The project includes multiple Docker Compose configurations:

- **docker-compose.yml** - Base configuration for development
- **docker-compose-local.yml** - Local development with hot reload
- **docker-compose-prod.yml** - Production-ready configuration

### Production Deployment

```bash
# Use production docker-compose configuration
docker-compose -f docker-compose-prod.yml up -d --build

# View production logs
docker-compose -f docker-compose-prod.yml logs -f
```

### Pre-deployment Checklist

Make sure you:
- ✅ Changed all default passwords and secret keys in `.env`
- ✅ Set strong `SECRET_KEY_ACCESS` and `SECRET_KEY_REFRESH` (minimum 32 characters)
- ✅ Configured production database credentials
- ✅ Set up Stripe production keys (not test keys)
- ✅ Configured real SMTP server (replace MailHog)
- ✅ Set up SSL/TLS certificates (use nginx or similar)
- ✅ Configured proper CORS settings
- ✅ Set up monitoring and logging
- ✅ Configured database backups
- ✅ Set appropriate resource limits in Docker Compose
- ✅ Reviewed and secured all exposed ports

## 🤝 Contributing

1. Fork the project
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 👥 Development Team

- **Oleksandr Popov** - [GitHub](https://github.com/Orixara)
- **Andrii Bielyi** - [GitHub](https://github.com/SensibleN00B)
- **Bohdan Marchenko** - [GitHub](https://github.com/yagginov) 
- **Serhii Basok** - [GitHub](https://github.com/SerhiiBasok)
- **Liliia Kyrylyshena** - [GitHub](https://github.com/MorsImmortalis05)