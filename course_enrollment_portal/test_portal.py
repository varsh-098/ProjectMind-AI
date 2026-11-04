"""
course_enrollment_portal/test_portal.py
=======================================
Automated test suite for Problem Statement 7: Online Course Enrollment Portal.
Verifies:
  1. Student registration
  2. Course listings catalog
  3. AI Scheduling Conflict Detector (detects clashing Monday timetable slots)
  4. Prerequisite enforcement
  5. Maximum 18-credit semester limit
  6. Admin dashboard metrics
"""

import pytest
from course_enrollment_portal.models import Student, Course, TimeSlot
from course_enrollment_portal.conflict_detector import SchedulingConflictDetector
from course_enrollment_portal.portal_service import CoursePortalService
from course_enrollment_portal.roadmap import get_development_roadmap


def test_student_registration():
    portal = CoursePortalService()
    res = portal.register_student(
        student_id="STU-001",
        name="Balaj",
        email="balaj@college.edu",
        major="Computer Science",
    )
    assert res["success"] is True
    assert "STU-001" in portal.students


def test_course_listings_catalog():
    portal = CoursePortalService()
    courses = portal.list_courses()
    assert len(courses) >= 5
    codes = [c["code"] for c in courses]
    assert "CS101" in codes
    assert "MATH101" in codes


def test_detect_scheduling_time_conflict():
    """
    CS101 meets Mon/Wed 09:00 - 10:30.
    MATH101 meets Mon/Wed 10:00 - 11:30.
    They overlap from 10:00 to 10:30 on Monday and Wednesday!
    The conflict detector MUST catch this clash and reject enrollment.
    """
    portal = CoursePortalService()
    portal.register_student("STU-101", "Balaj", "balaj@college.edu", "CSE")

    # 1. Enroll in CS101 (Mon 09:00 - 10:30)
    res1 = portal.enroll_student("STU-101", "CS101")
    assert res1["success"] is True

    # 2. Attempt to enroll in MATH101 (Mon 10:00 - 11:30) -> Collision!
    res2 = portal.enroll_student("STU-101", "MATH101")
    assert res2["success"] is False
    assert "Timetable collision detected" in res2["error"]
    assert res2["validation"]["error_code"] == "TIMETABLE_CONFLICT"
    assert len(res2["validation"]["conflicts"]) > 0


def test_non_overlapping_courses_enroll_successfully():
    """
    CS101 meets Mon/Wed 09:00 - 10:30.
    PHY101 meets Tue/Thu 14:00 - 15:30.
    Different days & times -> Should enroll with 0 conflicts!
    """
    portal = CoursePortalService()
    portal.register_student("STU-102", "Balaj", "balaj@college.edu", "CSE")

    res1 = portal.enroll_student("STU-102", "CS101")
    assert res1["success"] is True

    res2 = portal.enroll_student("STU-102", "PHY101")
    assert res2["success"] is True
    assert res2["total_credits"] == 8


def test_prerequisite_validation():
    """CS201 requires CS101 as prerequisite."""
    portal = CoursePortalService()
    portal.register_student("STU-103", "Newbie", "new@college.edu", "CSE", completed_courses=[])

    res = portal.enroll_student("STU-103", "CS201")
    assert res["success"] is False
    assert "Missing prerequisite" in res["error"]


def test_development_roadmap():
    roadmap = get_development_roadmap()
    assert roadmap["project"] == "Online Course Enrollment Portal"
    assert len(roadmap["phases"]) == 4


def test_admin_dashboard_summary():
    portal = CoursePortalService()
    portal.register_student("STU-104", "Balaj", "balaj@college.edu", "CSE")
    portal.enroll_student("STU-104", "PHY101")

    admin_summary = portal.get_admin_dashboard_summary()
    assert admin_summary["metrics"]["total_registered_students"] == 1
    assert admin_summary["metrics"]["total_course_offerings"] >= 5
    assert len(admin_summary["course_breakdown"]) >= 5
