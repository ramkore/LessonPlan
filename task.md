# Task Checklist: Academic Management System

- [ ] **1. Project Initialization & Architecture Design**
  - [ ] Define system architecture and database schema in documentation
  - [ ] Create folder structure (`/frontend`, `/backend`, `/database`, `/docker`)

- [ ] **2. Backend Development (FastAPI)**
  - [ ] Setup FastAPI project with dependencies
  - [ ] Configure PostgreSQL, Redis, and Celery connections
  - [ ] Create database models (Users, AcademicCalendar, Holidays, Timetable, Subjects, Faculty)
  - [ ] Build `/auth/login` endpoint with JWT
  - [ ] Build `/calendar` endpoints with auto working-day calculation
  - [ ] Build `/holidays` endpoints with bulk insert
  - [ ] Build `/timetable` endpoints with clash detection logic
  - [ ] Integrate API caching (Redis) for frequent read endpoints

- [ ] **3. Frontend Development (Next.js)**
  - [ ] Setup Next.js App Router project with Tailwind, ShadCN, React Hook Form
  - [ ] Create authentication context and login page
  - [ ] Build Dashboard with summary cards
  - [ ] Build Academic Calendar module (form-based)
  - [ ] Build Holiday Management module (dynamic row-based form)
  - [ ] Build Individual Timetable module (grid-based interactive UI)

- [ ] **4. Infrastructure & Deployment**
  - [ ] Create `Dockerfile` for backend and celery worker
  - [ ] Create `Dockerfile` for frontend
  - [ ] Create NGINX configuration
  - [ ] Create `docker-compose.yml` integrating all services (web, backend, db, redis, celery, nginx)

- [ ] **5. Verification & Testing**
  - [ ] Validate Docker stack builds successfully
  - [ ] Verify backend endpoints functionality
  - [ ] Verify frontend functionality (Forms, Tables, Auth)
