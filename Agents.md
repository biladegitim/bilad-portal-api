# Bilad Portal - Project Context

## Project Overview

Bilad Portal is an internal institution management system.

Main features:

* QR attendance system
* Leave request management
* Role based access control
* Mobile responsive portal
* Staff management
* Notification system

## Tech Stack

### Frontend

* Next.js App Router
* TypeScript
* TailwindCSS

### Backend

* FastAPI
* PostgreSQL
* SQLAlchemy
* JWT Authentication

## Roles

* super_admin
* admin
* employee

## Role Rules

### super_admin

Can access everything.

### admin

Can:

* view subordinate attendance
* manage subordinate leave requests
* cannot access global users list
* cannot access super admin features

### employee

Can:

* scan QR
* create leave requests
* view own attendance
* view own leaves

## QR System

* Dynamic QR attendance system
* QR scan creates check-in/check-out
* Device based validation exists
* Mobile camera scanning is heavily used

## Current Architecture

Frontend and backend run separately.

Frontend:

* localhost:3000
* mobile access through local IP

Backend:

* localhost:8000
* FastAPI API server

## Important Notes

* Do not break responsive mobile layout
* Preserve current design language
* Sidebar role filtering is important
* Attendance and leave hierarchy must remain correct
* Existing APIs should be reused when possible

## Current Focus

* Production deployment
* Notification system
* Flutter mobile app
* PWA support
* Live notifications
* Admin hierarchy improvements

## Development Commands

### Frontend

npm run dev -- --hostname 0.0.0.0

### Backend

uvicorn main:app --reload --host 0.0.0.0 --port 8000

## Environment Variables

Frontend:
NEXT_PUBLIC_API_URL
NEXT_PUBLIC_FRONTEND_URL

## Coding Style

* Keep files modular
* Prefer clean responsive UI
* Avoid unnecessary rewrites
* Preserve working business logic
* Mobile-first approach
