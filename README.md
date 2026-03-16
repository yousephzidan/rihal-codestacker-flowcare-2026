## rihal-codestacker-flowcare-2026

# FlowCare - Queue & Appointment Booking System

[Full API Documentation](https://flowcare-rihal.tech/docs)

A FastAPI-based backend system for managing queue and appointment bookings at service branches across Oman.

## Overview

FlowCare is designed to handle high daily traffic at government-style counters, clinics, customer care desks, and internal support services. The system prevents overlapping bookings, provides clear audit trails, and gives branch managers control over their schedules while maintaining system-wide visibility for administrators.

## Features

- Role-based access control (Admin, Branch Manager, Staff, Customer)
- HTTP Basic Authentication
- Appointment booking, cancellation, and rescheduling
- Slot management with soft delete functionality
- Comprehensive audit logging
- File storage for customer ID images and appointment attachments
- Pagination and search on listing endpoints
- Soft delete with configurable retention period

## Technology Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Authentication**: HTTP Basic Auth with bcrypt
- **Validation**: Pydantic

## Project Structure

```
rihal-codestacker-flowcare-2026/
├── app/
│   ├── api/                    # API route handlers
│   │   ├── public.py           # Public endpoints
│   │   ├── auth.py             # Authentication
│   │   ├── customers.py        # Customer operations
│   │   ├── management.py       # Staff/Manager operations
│   │   └── files.py            # File retrieval
│   ├── core/                   # Core functionality
│   │   ├── config.py           # Configuration
│   │   ├── database.py         # Database connection
│   │   └── auth.py             # Authentication/Authorization
│   ├── models/                 # SQLAlchemy models
│   │   └── models.py
│   ├── schemas/                # Pydantic schemas
│   │   └── schemas.py
│   ├── services/               # Business logic
│   │   ├── audit_service.py
│   │   ├── file_service.py
│   │   └── seed_service.py
│   └── main.py                 # Application entry point
├── requirements.txt
└── .env
```

## Database Schema

### Entities

1. **Branch** - Service branch locations with city, address, timezone
2. **ServiceType** - Types of services offered per branch
3. **User** - Staff, managers, customers with roles
4. **StaffServiceType** - Assignment of staff to service types
5. **Slot** - Available time slots (supports soft delete)
6. **Appointment** - Customer appointments
7. **AuditLog** - Activity tracking
8. **SystemConfig** - System configuration values

### Relationships

- Branch has many ServiceTypes, Users (staff), Slots, Appointments
- ServiceType has many Slots, Appointments
- User can be customer or staff with appointments
- Slot belongs to Branch, ServiceType, optionally Staff
- Appointment belongs to Customer, Branch, ServiceType, Slot, optionally Staff

## Setup Instructions

### Prerequisites

- Python 3.11
- PostgreSQL database

### Installation

1. Clone the repository and navigate to the project directory:


```bash
git clone https://github.com/yousephzidan/rihal-codestacker-flowcare-2026
cd rihal-codestacker-flowcare-2026
```

2. Create and activate a virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a PostgreSQL database:

```bash
psql -U postgres
CREATE DATABASE flowcare_db;
CREATE USER flowcare WITH PASSWORD 'flowcare';
GRANT ALL PRIVILEGES ON DATABASE flowcare_db TO flowcare;
```

5. Configure environment variables by editing the `.env` file or using defaults:

```bash
# Database connection
DATABASE_URL=postgresql://flowcare:flowcare@localhost:5432/flowcare_db

# Application settings
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=5
SOFT_DELETE_RETENTION_DAYS=30
```

### Running the Application

Start the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation (Swagger UI) is at `http://localhost:8000/docs`

## Seed Data

The application automatically seeds the database on startup with:

- 2 branches (Muscat, Suhar)
- Service types per branch (Customer Support, Document Verification, General Inquiry)
- Staff users (2 per branch)
- Branch managers (1 per branch)
- Time slots for the next 7 days
- Sample appointments
- Sample audit logs

Seeding is idempotent - running multiple times will not duplicate data.

## Roles and Permissions

### Admin (System-wide)
- Manage all branches, service types, staff, and customers
- View and manage all appointments in all branches
- Create/update slots across branches
- View full audit log
- Export audit logs as CSV
- Configure soft delete retention period

### Branch Manager (Branch-scoped)
- Manage only their assigned branch
- Create/update slots for their branch
- Assign staff to service types in their branch
- List and view customers in their branch
- View/manage appointments in their branch
- View audit logs for their branch

### Staff (Branch-scoped)
- View their schedule and assigned appointments
- Update appointment status (checked-in, no-show, completed)
- Add internal notes to appointments

### Customer
- Register with ID image
- View available service types and slots
- Book appointments
- Cancel own appointments
- Reschedule own appointments
- View own appointment history

## API Endpoints

### Public (No Authentication Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/branches` | List all active branches |
| GET | `/branches/{branch_id}/services` | List services by branch |
| GET | `/branches/{branch_id}/slots` | List available slots |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new customer with ID image |
| GET | `/auth/me` | Get current user info |

### Customer (Authenticated)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/customers/appointments` | Book new appointment |
| GET | `/customers/appointments` | List my appointments |
| GET | `/customers/appointments/{id}` | Get appointment details |
| DELETE | `/customers/appointments/{id}` | Cancel appointment |
| POST | `/customers/appointments/{id}/reschedule` | Reschedule appointment |

### Management (Staff/Manager/Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/management/appointments` | List appointments (role-based) |
| PATCH | `/management/appointments/{id}` | Update appointment status |
| POST | `/management/slots` | Create time slot |
| PATCH | `/management/slots/{id}` | Update slot |
| DELETE | `/management/slots/{id}` | Soft-delete slot |
| GET | `/management/staff` | List staff (Admin→all, Manager→branch) |
| POST | `/management/staff-service-types` | Assign staff to service |
| GET | `/management/customers` | List customers |
| GET | `/management/customers/{id}` | Get customer details |
| GET | `/management/audit-logs` | View audit logs |
| GET | `/management/audit-logs/export` | Export audit logs as CSV |
| GET | `/management/config/retention-period` | Get retention period |
| PUT | `/management/config/retention-period` | Update retention period |
| DELETE | `/management/slots/cleanup` | Cleanup expired slots |

### File Retrieval

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/files/customer/{id}/id-image` | Get customer ID image (Admin only) |
| GET | `/files/appointments/{id}/attachment` | Get appointment attachment |

## Example API Usage

### Using curl

#### List branches (public):
```bash
curl http://localhost:8000/branches
```

#### Register a customer:
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "Password123",
    "full_name": "John Doe",
    "email": "john@example.com",
    "phone": "+96812345678",
    "id_image": "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
  }'
```

#### Book an appointment (Basic Auth):
```bash
curl -X POST http://localhost:8000/customers/appointments \
  -u john_doe:Password123 \
  -H "Content-Type: application/json" \
  -d '{
    "branch_id": "br_muscat",
    "service_type_id": "svc_support",
    "slot_id": "slot_001"
  }'
```

#### List my appointments:
```bash
curl http://localhost:8000/customers/appointments \
  -u john_doe:Password123
```

#### Cancel appointment:
```bash
curl -X DELETE http://localhost:8000/customers/appointments/appt_123 \
  -u john_doe:Password123
```

#### Update appointment status (Staff):
```bash
curl -X PATCH http://localhost:8000/management/appointments/appt_123 \
  -u staff1:Staff123! \
  -H "Content-Type: application/json" \
  -d '{"status": "CHECKED_IN"}'
```

#### View audit logs (Admin):
```bash
curl http://localhost:8000/management/audit-logs \
  -u admin:Admin@123
```

## Testing Credentials

The seed data includes the following users:

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | Admin@123 |
| Branch Manager (Muscat) | mgr_muscat | Manager@123 |
| Branch Manager (Suhar) | mgr_suhar | Manager@123 |
| Staff (Muscat) | staff_muscat_1 | Staff@123 |
| Staff (Muscat) | staff_muscat_2 | Staff@123 |
| Staff (Suhar) | staff_suhar_1 | Staff@123 |
| Customer | cust_ahmed | Customer@123 |
| Customer | cust_fatima | Customer@123 |
| Customer | cust_khalid | Customer@123 |
| Customer | customer2 | Customer123! |

## Soft Delete

Slots are soft-deleted rather than permanently removed. When a slot is deleted:

- The `deleted_at` timestamp is set
- The slot no longer appears in available slot listings
- An audit log entry is created

Soft-deleted slots can be permanently removed (hard-deleted) after a retention period has passed. The retention period defaults to 30 days and can be configured by admins.

## Audit Logging

All sensitive actions are logged with:

- Action type (appointment booked, cancelled, rescheduled, slot created/updated/deleted, etc.)
- Actor (user ID and role at the time of action)
- Target entity type and ID
- Timestamp
- Additional metadata (JSON)

## File Storage

### Customer ID Images
- Required during registration
- Valid types: JPEG, PNG
- Maximum size: 5MB
- Stored in: `uploads/customer_ids/`

### Appointment Attachments
- Optional during booking
- Valid types: JPEG, PNG, PDF
- Maximum size: 5MB
- Stored in: `uploads/attachments/`

## Pagination and Search

All listing endpoints support:

### Pagination
```bash
GET /management/appointments?page=1&size=10
```

Response:
```json
{
  "results": [...],
  "total": 125,
  "page": 1,
  "size": 10
}
```

### Search
```bash
GET /management/appointments?search=john
```

Search applies to relevant fields and is case-insensitive.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | postgresql://flowcare:flowcare@localhost:5432/flowcare_db |
| SECRET_KEY | Application secret key | your-secret-key-change-in-production |
| DEBUG | Enable debug mode | False |
| UPLOAD_DIR | Directory for file uploads | ./uploads |
| MAX_FILE_SIZE_MB | Maximum file size in MB | 5 |
| ALLOWED_IMAGE_TYPES | Allowed image MIME types | ["image/jpeg", "image/png"] |
| ALLOWED_DOCUMENT_TYPES | Allowed document MIME types | ["application/pdf"] |
| SOFT_DELETE_RETENTION_DAYS | Days to retain soft-deleted records | 30 |

## Frontend Tester

A web-based API tester is included at `app/index.html`. After starting the server, open this file in a browser to test all endpoints interactively.

## Live Deployment

The application is deployed at: **https://flowcare-rihal.tech**

### Deployment Instructions (Docker)

1. **Server Setup** (DigitalOcean Droplet):
   ```bash
   # Install Docker and Docker Compose
   sudo apt update
   sudo apt install docker.io docker-compose nginx certbot python3-certbot-nginx
   sudo systemctl start docker
   ```

2. **Deploy with Docker Compose**:
   ```bash
   # Clone the repository
   git clone https://github.com/yousephzidan/rihal-codestacker-flowcare-2026
   cd rihal-codestacker-flowcare-2026

   # Start the application (database + API)
   docker-compose up -d
   ```

3. **Configure Nginx**:
   ```bash
   sudo vim /etc/nginx/sites-available/flowcare
   ```
   
   Add the following configuration:
   ```nginx
   server {
       server_name flowcare-rihal.tech www.flowcare-rihal.tech;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }

       listen 80;
   }
   ```

4. **Enable SSL with Certbot**:
   ```bash
   sudo certbot --nginx -d flowcare-rihal.tech
   ```

The API will be available at **https://flowcare-rihal.tech**

## License

This project is built for the Rihal Codestacker 2026 challenge.
