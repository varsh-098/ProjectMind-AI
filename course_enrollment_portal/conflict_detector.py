"""
course_enrollment_portal/conflict_detector.py
=============================================
Core Conflict Detection & Academic Validation Engine.
Problem Statement 7 AI Demonstration:
  - Detects scheduling collisions across weekly time slots
  - Validates 18-credit semester caps
  - Verifies completed prerequisites
  - Enforces classroom capacity
"""

from typing import List, Dict, Any, Optional
from course_enrollment_portal.models import Student, Course, TimeSlot


class SchedulingConflictError(Exception):
    """Raised when course times clash."""
    pass


class SchedulingConflictDetector:
    """
    Intelligent Timetable Conflict Detection Engine for the Course Enrollment Portal.
    """

    MAX_SEMESTER_CREDITS = 18

    @staticmethod
    def find_time_slot_conflicts(
        new_course: Course,
        enrolled_courses: List[Course],
    ) -> List[Dict[str, Any]]:
        """
        Compare all time slots of new_course against currently enrolled courses.
        Returns a list of conflict diagnostics.
        """
        conflicts = []

        for new_slot in new_course.time_slots:
            for enrolled in enrolled_courses:
                for enrolled_slot in enrolled.time_slots:
                    if new_slot.overlaps_with(enrolled_slot):
                        conflicts.append({
                            "type": "TIMETABLE_COLLISION",
                            "day": new_slot.day,
                            "requested_course": new_course.course_code,
                            "requested_time": f"{new_slot.start_time} - {new_slot.end_time}",
                            "conflicting_course": enrolled.course_code,
                            "conflicting_time": f"{enrolled_slot.start_time} - {enrolled_slot.end_time}",
                            "explanation": (
                                f"Schedule clash on {new_slot.day}: '{new_course.title}' "
                                f"({new_slot.start_time}-{new_slot.end_time}) conflicts with already enrolled "
                                f"course '{enrolled.title}' ({enrolled_slot.start_time}-{enrolled_slot.end_time})."
                            )
                        })

        return conflicts

    @classmethod
    def validate_enrollment_request(
        cls,
        student: Student,
        target_course: Course,
        current_courses: List[Course],
    ) -> Dict[str, Any]:
        """
        Comprehensive pre-enrollment validation rule pipeline.
        Returns validation status, errors, and warnings.
        """
        # 1. Check if already enrolled
        if target_course.course_code in student.enrolled_courses:
            return {
                "allowed": False,
                "reason": f"Student is already enrolled in {target_course.course_code}.",
                "error_code": "ALREADY_ENROLLED",
            }

        # 2. Check Prerequisites
        missing_prereqs = [
            req for req in target_course.prerequisites
            if req not in student.completed_courses
        ]
        if missing_prereqs:
            return {
                "allowed": False,
                "reason": f"Missing prerequisite(s): {', '.join(missing_prereqs)}.",
                "error_code": "PREREQUISITE_NOT_MET",
                "missing_prerequisites": missing_prereqs,
            }

        # 3. Check Credit Cap Limit (Max 18 credits)
        current_credits = sum(c.credits for c in current_courses)
        if current_credits + target_course.credits > cls.MAX_SEMESTER_CREDITS:
            return {
                "allowed": False,
                "reason": (
                    f"Credit limit exceeded. Current: {current_credits} credits. "
                    f"Adding {target_course.credits} exceeds the maximum limit of {cls.MAX_SEMESTER_CREDITS} credits."
                ),
                "error_code": "CREDIT_LIMIT_EXCEEDED",
                "current_credits": current_credits,
                "requested_credits": target_course.credits,
            }

        # 4. Check Scheduling Time Conflicts
        time_conflicts = cls.find_time_slot_conflicts(target_course, current_courses)
        if time_conflicts:
            return {
                "allowed": False,
                "reason": f"Timetable collision detected with {len(time_conflicts)} course slot(s).",
                "error_code": "TIMETABLE_CONFLICT",
                "conflicts": time_conflicts,
            }

        # 5. Check Room / Course Capacity
        if target_course.is_full:
            return {
                "allowed": False,
                "reason": f"Course {target_course.course_code} is at maximum capacity ({target_course.max_capacity}/{target_course.max_capacity}).",
                "error_code": "COURSE_FULL_WAITLIST",
                "can_waitlist": True,
            }

        # All checks passed!
        return {
            "allowed": True,
            "reason": "Enrollment approved. No scheduling conflicts or policy violations.",
            "enrolled_course": target_course.course_code,
            "new_total_credits": current_credits + target_course.credits,
        }
