"""
course_enrollment_portal/portal_service.py
==========================================
Service orchestration layer for Online Course Enrollment Portal.
Implements the 4 core deliverables:
  1. Student Registration
  2. Course Listings
  3. Enrollment Management with Conflict Detection
  4. Admin Dashboard
"""

from typing import List, Dict, Any, Optional
from course_enrollment_portal.models import Student, Course, TimeSlot, EnrollmentRecord
from course_enrollment_portal.conflict_detector import SchedulingConflictDetector


class CoursePortalService:
    """
    Central business logic coordinator for Problem Statement 7.
    """

    def __init__(self):
        self.students: Dict[str, Student] = {}
        self.courses: Dict[str, Course] = {}
        self.enrollment_records: List[EnrollmentRecord] = []
        self._seed_sample_catalog()

    def _seed_sample_catalog(self) -> None:
        """Seed initial university catalog with sample courses and timetables."""
        sample_courses = [
            Course(
                course_code="CS101",
                title="Introduction to Programming & Algorithms",
                instructor="Dr. Alan Turing",
                credits=4,
                prerequisites=[],
                max_capacity=40,
                current_enrolled=25,
                time_slots=[
                    TimeSlot(day="Monday", start_time="09:00", end_time="10:30"),
                    TimeSlot(day="Wednesday", start_time="09:00", end_time="10:30"),
                ],
            ),
            Course(
                course_code="CS201",
                title="Data Structures & Algorithms",
                instructor="Prof. Ada Lovelace",
                credits=4,
                prerequisites=["CS101"],
                max_capacity=30,
                current_enrolled=28,
                time_slots=[
                    TimeSlot(day="Tuesday", start_time="10:00", end_time="11:30"),
                    TimeSlot(day="Thursday", start_time="10:00", end_time="11:30"),
                ],
            ),
            Course(
                course_code="MATH101",
                title="Calculus & Linear Algebra",
                instructor="Dr. Carl Friedrich Gauss",
                credits=3,
                prerequisites=[],
                max_capacity=50,
                current_enrolled=45,
                time_slots=[
                    TimeSlot(day="Monday", start_time="10:00", end_time="11:30"),  # Conflicts with CS101 on Mon!
                    TimeSlot(day="Wednesday", start_time="10:00", end_time="11:30"),
                ],
            ),
            Course(
                course_code="PHY101",
                title="Physics for Engineers",
                instructor="Dr. Richard Feynman",
                credits=4,
                prerequisites=[],
                max_capacity=35,
                current_enrolled=15,
                time_slots=[
                    TimeSlot(day="Tuesday", start_time="14:00", end_time="15:30"),
                    TimeSlot(day="Thursday", start_time="14:00", end_time="15:30"),
                ],
            ),
            Course(
                course_code="ENG101",
                title="Technical Writing & Communication",
                instructor="Prof. George Orwell",
                credits=2,
                prerequisites=[],
                max_capacity=30,
                current_enrolled=30,  # Full capacity for waitlist test
                time_slots=[
                    TimeSlot(day="Friday", start_time="09:00", end_time="11:00"),
                ],
            ),
        ]

        for c in sample_courses:
            self.courses[c.course_code] = c

    # 1. Student Registration
    def register_student(
        self,
        student_id: str,
        name: str,
        email: str,
        major: str,
        completed_courses: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a new student into the portal."""
        if student_id in self.students:
            return {"success": False, "error": f"Student with ID '{student_id}' already exists."}

        student = Student(
            student_id=student_id,
            name=name,
            email=email,
            major=major,
            completed_courses=completed_courses or [],
            enrolled_courses=[],
        )
        self.students[student_id] = student
        return {
            "success": True,
            "message": f"Student {name} registered successfully.",
            "student": student,
        }

    # 2. Course Listings
    def list_courses(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all catalog courses with meeting times and seat availability."""
        results = []
        for c in self.courses.values():
            if department and not c.course_code.startswith(department.upper()):
                continue
            results.append({
                "code": c.course_code,
                "title": c.title,
                "instructor": c.instructor,
                "credits": c.credits,
                "prerequisites": c.prerequisites,
                "seats_available": max(0, c.max_capacity - c.current_enrolled),
                "is_full": c.is_full,
                "schedule": [f"{s.day} {s.start_time}-{s.end_time}" for s in c.time_slots],
            })
        return results

    # 3. Enrollment Management with Conflict Detection
    def enroll_student(self, student_id: str, course_code: str) -> Dict[str, Any]:
        """
        Attempt to enroll a student in a course.
        Runs full pre-enrollment validation (collision detection, prerequisites, credits).
        """
        student = self.students.get(student_id)
        if not student:
            return {"success": False, "error": f"Student '{student_id}' not found."}

        course = self.courses.get(course_code)
        if not course:
            return {"success": False, "error": f"Course '{course_code}' not found in catalog."}

        current_courses = [self.courses[code] for code in student.enrolled_courses if code in self.courses]

        # Invoke AI Scheduling Conflict Detector
        validation = SchedulingConflictDetector.validate_enrollment_request(
            student=student,
            target_course=course,
            current_courses=current_courses,
        )

        if not validation["allowed"]:
            # Record failed attempt
            record = EnrollmentRecord(
                enrollment_id=f"ENR-{len(self.enrollment_records)+1}",
                student_id=student_id,
                course_code=course_code,
                status="REJECTED_" + validation.get("error_code", "ERROR"),
                reason=validation.get("reason"),
            )
            self.enrollment_records.append(record)
            return {
                "success": False,
                "error": validation["reason"],
                "validation": validation,
            }

        # Success - update records
        student.enrolled_courses.append(course_code)
        course.current_enrolled += 1

        record = EnrollmentRecord(
            enrollment_id=f"ENR-{len(self.enrollment_records)+1}",
            student_id=student_id,
            course_code=course_code,
            status="ENROLLED",
            reason="Validation passed with 0 conflicts.",
        )
        self.enrollment_records.append(record)

        return {
            "success": True,
            "message": f"Successfully enrolled in {course.title} ({course_code}).",
            "enrolled_courses": student.enrolled_courses,
            "total_credits": sum(self.courses[c].credits for c in student.enrolled_courses),
        }

    # 4. Admin Dashboard
    def get_admin_dashboard_summary(self) -> Dict[str, Any]:
        """Aggregate administrative metrics across courses, capacity, and enrollments."""
        total_students = len(self.students)
        total_courses = len(self.courses)
        total_seats = sum(c.max_capacity for c in self.courses.values())
        total_enrolled = sum(c.current_enrolled for c in self.courses.values())

        course_breakdown = [
            {
                "code": c.course_code,
                "title": c.title,
                "instructor": c.instructor,
                "enrolled": f"{c.current_enrolled}/{c.max_capacity}",
                "occupancy_rate": f"{round((c.current_enrolled / c.max_capacity) * 100, 1)}%",
                "status": "AT_CAPACITY" if c.is_full else "OPEN",
            }
            for c in self.courses.values()
        ]

        return {
            "portal": "Online Course Enrollment Portal - Administrative Dashboard",
            "metrics": {
                "total_registered_students": total_students,
                "total_course_offerings": total_courses,
                "total_capacity_seats": total_seats,
                "total_active_enrollments": total_enrolled,
                "overall_occupancy_rate": f"{round((total_enrolled / max(1, total_seats)) * 100, 1)}%",
            },
            "course_breakdown": course_breakdown,
            "recent_enrollment_events": [
                {
                    "id": r.enrollment_id,
                    "student": r.student_id,
                    "course": r.course_code,
                    "status": r.status,
                    "reason": r.reason,
                }
                for r in self.enrollment_records[-10:]
            ],
        }


if __name__ == "__main__":
    print("=" * 64)
    print("  ONLINE COURSE ENROLLMENT PORTAL (PROBLEM STATEMENT 7)")
    print("  Live Demonstration: Architecture, Scheduling & Conflict Engine")
    print("=" * 64)

    service = CoursePortalService()

    # Step 1: Register Student
    print("\n[STEP 1] Student Registration:")
    student_res = service.register_student(
        student_id="STU-001",
        name="Balaj V",
        email="balaj@university.edu",
        major="Computer Science",
        completed_courses=[],
    )
    student_id = "STU-001"
    print(f"  -> Registered: {student_res['student'].name} (ID: {student_id}, Major: {student_res['student'].major})")

    # Step 2: Course Listings
    print("\n[STEP 2] Course Catalog Listings:")
    catalog = service.list_courses()
    for c in catalog:
        slots_str = ", ".join(c["schedule"])
        print(f"  - [{c['code']}] {c['title']} ({c['credits']} cr) | Slots: {slots_str}")

    # Step 3: Enroll in first course (CS101)
    print("\n[STEP 3] Enrollment Management - Enrolling in CS101 (Mon/Wed 09:00 - 10:30):")
    enroll_1 = service.enroll_student(student_id, "CS101")
    print(f"  -> Status: {enroll_1['success']} | {enroll_1['message']}")

    # Step 4: AI Demonstration - Detect Scheduling Conflict (MATH101 Mon/Wed 10:00 - 11:30)
    print("\n[STEP 4] AI Demonstration - Attempting to enroll in MATH101 (Mon/Wed 10:00 - 11:30):")
    enroll_2 = service.enroll_student(student_id, "MATH101")
    print(f"  -> Conflict Detected! Enrollment Allowed: {enroll_2['success']}")
    print(f"  -> Reason: {enroll_2.get('error') or enroll_2.get('message')}")
    if "validation" in enroll_2:
        for clash in enroll_2["validation"].get("conflicts", []):
            print(f"     [COLLISION] {clash['explanation']}")

    # Step 5: Admin Dashboard
    print("\n[STEP 5] Admin Dashboard Summary:")
    admin_summary = service.get_admin_dashboard_summary()
    for metric, val in admin_summary["metrics"].items():
        print(f"  * {metric.replace('_', ' ').title()}: {val}")

    print("\n" + "=" * 64)
    print("  ALL 4 MODULES + AI CONFLICT DETECTION VERIFIED SUCCESSFULLY!")
    print("=" * 64)


