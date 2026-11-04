"""
backend/brain/memory.py
========================
Project Memory — persistent knowledge, facts, and architectural decisions.

WHY MEMORY MATTERS:
    RAG (Phase 12) retrieves raw code chunks from project files.
    Memory (Phase 13) stores distilled facts and decisions that persist
    across conversations, server restarts, and developer sessions.

    User: "What database do we use?"
    RAG: Searches entire codebase for "database" (might find imports, comments, etc.)
    Memory: Immediately answers: "PostgreSQL" (high signal, zero noise).

WHAT MEMORY STORES:
    1. Facts: Key-value facts categorized into architecture, tech_stack, conventions, etc.
    2. Decisions: Architecture Decision Records (ADRs) logging why choices were made.
    3. Preferences: Developer coding styles, formatting rules, and guardrails.

PERSISTENCE:
    Automatically saves to a JSON file (backend/brain/data/project_memory.json).
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.brain import embeddings


class ProjectMemoryManager:
    """Manages persistent project facts, decisions, and context blocks."""

    DEFAULT_CATEGORIES = {
        "architecture",
        "tech_stack",
        "conventions",
        "decisions",
        "general",
    }

    def __init__(self, storage_path: Optional[str | Path] = None):
        if storage_path is None:
            base_dir = Path(__file__).resolve().parent
            data_dir = base_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.storage_file = data_dir / "project_memory.json"
        else:
            self.storage_file = Path(storage_path).resolve()
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)

        self.facts: Dict[str, Dict[str, Any]] = {}
        self.decisions: List[Dict[str, Any]] = []

        self.load_from_disk()

        # Seed initial facts if memory file was just created
        if not self.facts:
            self._seed_default_facts()
            self.save_to_disk()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_from_disk(self) -> None:
        """Load stored facts and decisions from the JSON persistence file."""
        if not self.storage_file.exists():
            return

        try:
            content = self.storage_file.read_text(encoding="utf-8")
            data = json.loads(content)
            self.facts = data.get("facts", {})
            self.decisions = data.get("decisions", [])
        except Exception:
            # Fall back to empty memory on parse error
            self.facts = {}
            self.decisions = []

    def save_to_disk(self) -> None:
        """Serialize memory facts and decisions to disk."""
        data = {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "facts": self.facts,
            "decisions": self.decisions,
        }
        self.storage_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Fact Management
    # ------------------------------------------------------------------

    def add_fact(
        self,
        key: str,
        value: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Add or update a project fact.

        Args:
            key: Unique identifier for the fact (e.g. 'database_technology').
            value: The fact description (e.g. 'PostgreSQL 16 with asyncpg').
            category: One of 'architecture', 'tech_stack', 'conventions', 'general'.
            tags: Optional keywords for tagging and filtering.

        Returns:
            The stored fact record.
        """
        now = datetime.now(timezone.utc).isoformat()
        clean_key = key.strip().lower()

        fact_record = {
            "key": clean_key,
            "value": value.strip(),
            "category": category.strip().lower(),
            "tags": [t.strip().lower() for t in (tags or [])],
            "updated_at": now,
        }

        if clean_key not in self.facts:
            fact_record["created_at"] = now
        else:
            fact_record["created_at"] = self.facts[clean_key].get("created_at", now)

        self.facts[clean_key] = fact_record
        self.save_to_disk()
        return fact_record

    def get_fact(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific fact by key."""
        return self.facts.get(key.strip().lower())

    def list_facts(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all stored facts, optionally filtered by category or tag.
        """
        results = list(self.facts.values())

        if category:
            cat = category.strip().lower()
            results = [f for f in results if f.get("category") == cat]

        if tag:
            t = tag.strip().lower()
            results = [f for f in results if t in f.get("tags", [])]

        return sorted(results, key=lambda x: (x.get("category", ""), x.get("key", "")))

    def delete_fact(self, key: str) -> bool:
        """Remove a fact by key. Returns True if deleted, False if not found."""
        clean_key = key.strip().lower()
        if clean_key in self.facts:
            del self.facts[clean_key]
            self.save_to_disk()
            return True
        return False

    # ------------------------------------------------------------------
    # Architectural Decisions (ADR)
    # ------------------------------------------------------------------

    def record_decision(
        self,
        title: str,
        description: str,
        rationale: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Record a significant architectural decision.

        Args:
            title: Short summary of the decision (e.g. 'Use Factory Pattern for LLM layer').
            description: What was decided.
            rationale: Why this choice was made over alternatives.
            tags: Keywords for indexing.
        """
        next_id = len(self.decisions) + 1
        decision = {
            "id": next_id,
            "title": title.strip(),
            "description": description.strip(),
            "rationale": rationale.strip(),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "tags": [t.strip().lower() for t in (tags or [])],
        }

        self.decisions.append(decision)
        self.save_to_disk()
        return decision

    def list_decisions(self) -> List[Dict[str, Any]]:
        """Return all recorded architectural decisions."""
        return self.decisions

    # ------------------------------------------------------------------
    # Semantic Memory Search (Phase 11 Embeddings Integration)
    # ------------------------------------------------------------------

    def search_memory(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        Search both facts and decisions using vector embeddings and cosine similarity.
        """
        if not query or not query.strip():
            return []

        query_vec = embeddings.get_embedding(query)
        scored_items = []

        # 1. Search Facts
        for fact in self.facts.values():
            text_repr = f"[{fact['category']}] {fact['key']}: {fact['value']}"
            item_vec = embeddings.get_embedding(text_repr)
            score = embeddings.cosine_similarity(query_vec, item_vec)
            if score >= min_score:
                scored_items.append({
                    "type": "fact",
                    "key": fact["key"],
                    "category": fact["category"],
                    "content": fact["value"],
                    "score": round(score, 4),
                })

        # 2. Search Decisions
        for dec in self.decisions:
            text_repr = f"[decision] {dec['title']}: {dec['description']} {dec['rationale']}"
            item_vec = embeddings.get_embedding(text_repr)
            score = embeddings.cosine_similarity(query_vec, item_vec)
            if score >= min_score:
                scored_items.append({
                    "type": "decision",
                    "id": dec["id"],
                    "title": dec["title"],
                    "content": dec["description"],
                    "rationale": dec["rationale"],
                    "score": round(score, 4),
                })

        scored_items.sort(key=lambda x: x["score"], reverse=True)
        return scored_items[:top_k]

    # ------------------------------------------------------------------
    # Prompt Context Injection Block
    # ------------------------------------------------------------------

    def get_memory_context_block(
        self,
        max_chars: int = 2500,
        category: Optional[str] = None,
    ) -> str:
        """
        Build a concise, structured memory summary ready to inject into the LLM system prompt.
        """
        facts = self.list_facts(category=category)
        if not facts and not self.decisions:
            return ""

        lines = ["--- PROJECT MEMORY (Architecture, Tech Stack & Facts) ---"]

        # Group facts by category with prioritized category ordering
        by_category: Dict[str, List[str]] = {}
        for f in facts:
            cat = f.get("category", "general").upper()
            by_category.setdefault(cat, []).append(f"• {f['key']}: {f['value']}")

        category_order = ["TECH_STACK", "ARCHITECTURE", "CONVENTIONS", "GENERAL"]
        ordered_cats = [c for c in category_order if c in by_category] + [
            c for c in by_category if c not in category_order
        ]

        for cat in ordered_cats:
            lines.append(f"\n[{cat}]")
            lines.extend(by_category[cat])

        # Include recent decisions if space allows
        if self.decisions and (category is None or category == "decisions"):
            lines.append("\n[ARCHITECTURAL DECISIONS]")
            for dec in self.decisions[-5:]:
                lines.append(f"• ADR #{dec['id']} ({dec['date']}): {dec['title']} — {dec['description']}")

        lines.append("\n--- END OF PROJECT MEMORY ---")
        full_block = "\n".join(lines)

        if len(full_block) > max_chars:
            return full_block[:max_chars] + "\n... (memory truncated)"

        return full_block

    def stats(self) -> Dict[str, Any]:
        """Summary statistics of stored memory."""
        categories: Dict[str, int] = {}
        for f in self.facts.values():
            cat = f.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_facts": len(self.facts),
            "total_decisions": len(self.decisions),
            "storage_file": str(self.storage_file),
            "categories": categories,
        }

    # ------------------------------------------------------------------
    # Default Seed Facts for ProjectMind AI
    # ------------------------------------------------------------------

    def _seed_default_facts(self) -> None:
        """Populate baseline facts about ProjectMind AI."""
        defaults = [
            (
                "backend_framework",
                "FastAPI 0.115 on Python 3.12 with async route handlers and Uvicorn ASGI server.",
                "tech_stack",
                ["fastapi", "python", "backend"],
            ),
            (
                "llm_architecture",
                "Decoupled LLM abstraction using the Factory and Strategy patterns in backend/llm/factory.py.",
                "architecture",
                ["llm", "factory", "strategy"],
            ),
            (
                "supported_llm_providers",
                "Local Nemotron (via llama-server port 8081), Groq (qwen3.8-27b), and Google AI Studio Gemini (gemini-3.8-flash).",
                "tech_stack",
                ["nemotron", "groq", "gemini"],
            ),
            (
                "file_access_security",
                "ProjectFileManager enforces strict path traversal protection and automatically blocks sensitive files (.env) and binary files.",
                "architecture",
                ["security", "file_manager", "safety"],
            ),
            (
                "vector_embeddings",
                "256-dimensional SubwordSemanticEmbedder with L2 normalization and cosine similarity calculation.",
                "tech_stack",
                ["embeddings", "vectors", "nlp"],
            ),
            (
                "rag_pipeline",
                "In-memory ProjectRAGIndex with sliding window chunking (35 lines, 8 line overlap) injecting code chunks into prompts.",
                "architecture",
                ["rag", "retrieval", "prompt"],
            ),
        ]

        portal_defaults = [
            (
                "target_project",
                "Online Course Enrollment Portal — A web-based academic platform supporting student registration, searchable course listings, automated enrollment management, timetable conflict detection, and an administrative dashboard.",
                "architecture",
                ["course_portal", "overview", "problem_statement_7"],
            ),
            (
                "student_registration",
                "Student registration module: Manages secure student onboarding, student ID generation, major/degree program selection, contact details, and completed prerequisite tracking.",
                "architecture",
                ["student", "registration", "auth", "profile"],
            ),
            (
                "course_listings",
                "Course catalog & listings module: Displays course codes (e.g. CS101, MATH201, BIO105), titles, descriptions, assigned instructors, credit values (1-4 credits), capacity limits, and weekly meeting time slots (days and start/end times).",
                "architecture",
                ["courses", "catalog", "timetable", "schedule"],
            ),
            (
                "enrollment_management",
                "Enrollment management module: Handles course add/drop operations, validates prerequisite completion, enforces maximum 18-credit per semester limits, and automatically invokes the conflict detection engine before confirming registration.",
                "architecture",
                ["enrollment", "add_drop", "validation", "credits"],
            ),
            (
                "admin_dashboard",
                "Admin dashboard module: Comprehensive administrative portal for department chairs and registrars to create/update courses, assign faculty instructors, monitor room capacities, review enrollment stats, and override waitlists.",
                "architecture",
                ["admin", "dashboard", "analytics", "management"],
            ),
            (
                "conflict_detection_engine",
                "AI Scheduling Conflict Detector: Analyzes student timetable slots for overlapping days and time intervals (e.g. Course A on Mon/Wed 10:00-11:30 vs Course B on Mon/Wed 10:30-12:00), detects exam date clashes, and flags instructor double-booking.",
                "architecture",
                ["ai", "scheduling", "conflict_detection", "timetable"],
            ),
            (
                "development_roadmap",
                "Development Roadmap: Phase 1: Database Schema & Student Registration; Phase 2: Course Listings & Catalog Search; Phase 3: Enrollment Engine & Scheduling Conflict Detection; Phase 4: Admin Dashboard, Analytics & Deployment.",
                "architecture",
                ["roadmap", "milestones", "project_planning"],
            ),
            (
                "scheduling_rules",
                "Core scheduling policies: 1) Overlap Constraint: Courses with overlapping time intervals on the same weekday are disallowed. 2) Credit Limit: Maximum 18 credits per semester. 3) Capacity Limit: Enrollment cannot exceed maximum room capacity.",
                "conventions",
                ["rules", "scheduling", "constraints", "credits"],
            ),
        ]

        for key, val, cat, tags in defaults + portal_defaults:
            self.add_fact(key=key, value=val, category=cat, tags=tags)

        # Seed initial decisions
        self.record_decision(
            title="Adopt Strategy & Factory Patterns for Multi-LLM Support",
            description="All LLM integrations implement BaseLLMProvider so chat endpoints remain provider-agnostic.",
            rationale="Allows switching between local offline models (Nemotron) and cloud APIs (Groq, Gemini) with zero code changes.",
            tags=["llm", "design-pattern", "architecture"],
        )
        self.record_decision(
            title="Adopt Interval Collision Algorithm for Timetable Conflict Detection",
            description="Implemented deterministic interval overlap detection comparing start and end minutes on matching weekdays to prevent scheduling conflicts during course enrollment.",
            rationale="Prevents double-booking students and guarantees instantaneous conflict feedback before database commit.",
            tags=["scheduling", "conflict-detection", "algorithm", "course-portal"],
        )
        self.record_decision(
            title="Role-Based Access Control (RBAC) for Student vs Admin Portals",
            description="Partitioned the course portal into Student Views (catalog browsing, enrollment) and Admin Views (course authoring, capacity overrides, reports).",
            rationale="Ensures academic security and prevents unauthorized modification of course limits or grades.",
            tags=["security", "rbac", "student", "admin"],
        )
        self.record_decision(
            title="Four-Phase Agile Development Roadmap for Course Portal",
            description="Adopted a 4-phase milestone roadmap covering Auth/Schema (Sprint 1), Catalog Search (Sprint 2), Conflict Detection Engine (Sprint 3), and Admin Dashboard (Sprint 4).",
            rationale="Enables modular verification of the conflict detector before assembling the complete web interface.",
            tags=["roadmap", "agile", "project-planning"],
        )
