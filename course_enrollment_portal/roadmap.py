"""
course_enrollment_portal/roadmap.py
===================================
Development Roadmap Generator for Problem Statement 7: Online Course Enrollment Portal.
Outlines milestone breakdown, architecture deliverables, risk mitigations, and timeline.
"""

from typing import List, Dict, Any


def get_development_roadmap() -> Dict[str, Any]:
    """
    Generate the structured 4-phase agile engineering roadmap
    for the Online Course Enrollment Portal.
    """
    return {
        "project": "Online Course Enrollment Portal",
        "objective": "Build a robust, conflict-free academic enrollment system with admin controls.",
        "architecture_pattern": "Layered Microservices / Modular Monolith with Relational DB",
        "estimated_duration_weeks": 8,
        "phases": [
            {
                "phase": 1,
                "name": "Database Modeling & Student Registration",
                "weeks": "Weeks 1-2",
                "objectives": [
                    "Design relational schema: Student, Course, TimeSlot, Enrollment, Waitlist",
                    "Implement student registration with email verification & student ID generator",
                    "Add Role-Based Access Control (RBAC): Student vs Admin roles",
                    "Implement password hashing & session management (JWT / secure cookies)",
                ],
                "deliverables": ["models.py", "auth_service.py", "schema.sql"],
                "status": "COMPLETED",
            },
            {
                "phase": 2,
                "name": "Course Listings & Catalog Search",
                "weeks": "Weeks 3-4",
                "objectives": [
                    "Implement course catalog API with pagination, filtering, and search",
                    "Filter courses by Department, Academic Credits, Instructor, and Term",
                    "Model weekly timetable slots (Monday-Friday, 24h start/end times)",
                    "Build responsive React course catalog interface",
                ],
                "deliverables": ["course_service.py", "catalog_api.py", "CourseCatalog.jsx"],
                "status": "COMPLETED",
            },
            {
                "phase": 3,
                "name": "Enrollment Engine & Scheduling Conflict Detection (AI Core)",
                "weeks": "Weeks 5-6",
                "objectives": [
                    "Build interval collision algorithm for timetable overlap detection",
                    "Implement prerequisite validation logic prior to course enrollment",
                    "Enforce 18-credit maximum limit per semester",
                    "Create automated waitlist management when course capacity is reached",
                    "Unit test suite for clash detection with 100% test coverage",
                ],
                "deliverables": ["conflict_detector.py", "enrollment_service.py", "test_portal.py"],
                "status": "COMPLETED",
            },
            {
                "phase": 4,
                "name": "Admin Dashboard, Analytics & Deployment",
                "weeks": "Weeks 7-8",
                "objectives": [
                    "Build administrative dashboard for department chairs and registrars",
                    "Provide faculty instructor assignment and classroom capacity overrides",
                    "Generate enrollment reports and conflict resolution statistics",
                    "Conduct end-to-end integration testing and production containerization",
                ],
                "deliverables": ["admin_dashboard.py", "reporting_service.py", "Dockerfile"],
                "status": "COMPLETED",
            },
        ],
        "risk_mitigations": [
            {
                "risk": "Concurrency race conditions during popular course registration spikes",
                "mitigation": "Optimistic locking and atomic transactions at the database layer",
            },
            {
                "risk": "Complex timetable overlaps spanning multiple days (e.g. Mon/Wed/Fri labs)",
                "mitigation": "Interval overlap checking comparing start/end minutes for matching weekdays",
            },
        ],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_development_roadmap(), indent=2))
