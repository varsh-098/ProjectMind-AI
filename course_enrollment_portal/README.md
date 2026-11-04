# Problem Statement 7: Online Course Enrollment Portal (Easy)

## Overview
A web-based academic course enrollment portal allowing students to register, explore course catalogs, manage enrollments without timetable clashes, and providing academic administrators with capacity and enrollment analytics.

---

## Core Deliverables & Features

### 1. Student Registration
- Secure student onboarding with email verification.
- Auto-generation of unique student academic IDs (`STU-YYYY-XXX`).
- Department/Major association and academic prerequisite tracking.

### 2. Course Listings & Catalog
- Searchable course offerings filtered by Department, Credit Hours, Instructor, and Term.
- Complete timetable metadata: Meeting days (Mon-Fri) and 24-hr time intervals (e.g. `09:00 - 10:30`).
- Real-time seat availability and room capacity tracking.

### 3. Enrollment Management & AI Conflict Detection
- **AI Scheduling Conflict Detector:** Evaluates interval overlap across course meeting slots (e.g. flags CS101 on Mon 09:00-10:30 colliding with MATH101 on Mon 10:00-11:30).
- **Prerequisite Validation:** Ensures introductory courses (e.g. CS101) are satisfied before advancing to CS201.
- **Credit Limit Policy:** Enforces maximum 18-credit load per semester.
- **Waitlisting:** Automatic waitlist placement when course capacity is reached.

### 4. Admin Dashboard
- Course authoring, instructor assignments, and room capacity overrides.
- Aggregate metrics: Total students, course enrollment occupancy rates, and conflict incident reports.

---

## AI Demonstration

### 1. Detect Scheduling Conflicts
The interval collision engine in `course_enrollment_portal/conflict_detector.py` compares start and end minutes:
$$\max(s_1, s_2) < \min(e_1, e_2)$$
If true on matching days, a `TIMETABLE_COLLISION` event is generated with clear explanations.

### 2. Development Roadmap
- **Phase 1 (Weeks 1-2):** Database Schema, Models, and Student Registration.
- **Phase 2 (Weeks 3-4):** Course Listings Catalog & Search Engine.
- **Phase 3 (Weeks 5-6):** Enrollment Management & AI Conflict Detection Engine.
- **Phase 4 (Weeks 7-8):** Admin Dashboard, Analytics, and Production Hardening.
