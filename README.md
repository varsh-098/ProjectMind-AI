# ProjectMind AI

> A project-aware AI development workspace that understands an entire software
> project and dynamically uses specialized AI agents to assist developers.

## Overview

ProjectMind AI is an intelligent development assistant designed to understand
and maintain the context of a software project.

Unlike a normal chatbot that only sees the current prompt, ProjectMind can
work with:

- Source code
- Documentation
- Requirements
- Project architecture
- Database schemas
- Previous conversations
- Important project decisions

ProjectMind combines:

- LLMs
- RAG
- Project Memory
- Tool Calling
- AI Agents
- Agent Orchestration
- FastAPI
- Vector Search
- LLM abstraction

to provide context-aware assistance throughout the software development
lifecycle.

---

## Core Architecture

                    USER
                      |
                      v
               PROJECTMIND AI
                      |
                      v
                 SUPERVISOR
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       CODING      REVIEW      TESTING
        AGENT       AGENT       AGENT
          |           |           |
          +-----------+-----------+
                      |
                      v
              PROJECT CONTEXT
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
         RAG       MEMORY       TOOLS
          |           |           |
          +-----------+-----------+
                      |
                      v
             LLM ABSTRACTION
                      |
          +-----------+-----------+
          |                       |
          v                       v
     GPT-6 Astra              Nemotron
       (KIE API)          (NVIDIA / Local)


---

## Main Components

### 1. FastAPI Backend

Acts as the HTTP API layer between the frontend and ProjectMind.

Responsibilities:

- Receive user requests
- Manage projects
- Handle conversations
- Communicate with agents
- Return responses

---

### 2. LLM Layer

Provides a common interface for different LLM providers.

Initial model:

- GPT-6 Astra through KIE.ai

Future models:

- Nemotron
- Other cloud LLMs
- Local models

The application should not directly depend on one specific provider.

Example:

    ProjectMind
        |
        v
    LLM Interface
        |
        +---- KIE → GPT-6 Astra
        |
        +---- NVIDIA → Nemotron
        |
        +---- Local → llama-server


---

### 3. Project Knowledge / RAG

ProjectMind indexes project information so that relevant context can be
retrieved when a user asks a question.

Pipeline:

    Project Files
         |
         v
      Parsing
         |
         v
      Chunking
         |
         v
     Embeddings
         |
         v
     Vector DB
         |
         v
     Retrieval
         |
         v
       Rerank
         |
         v
        LLM


---

### 4. Project Memory

Stores important information that should persist across conversations.

Examples:

- Database technology
- Authentication mechanism
- Architecture decisions
- Important project requirements
- Developer preferences
- Previous decisions

Memory and RAG are separate concepts.

RAG retrieves project information.

Memory stores persistent project information.


---

### 5. Agents

ProjectMind initially contains three specialized agents.

#### Coding Agent

Responsible for:

- Understanding code
- Finding bugs
- Generating code
- Modifying code
- Implementing features

#### Review Agent

Responsible for:

- Code review
- Detecting problems
- Suggesting improvements
- Checking maintainability

#### Testing Agent

Responsible for:

- Creating tests
- Running tests
- Analyzing failures
- Suggesting fixes


---

### 6. Supervisor

The Supervisor analyzes the user's request and determines which specialized
agent should handle the task.

Example:

    User:
    "Fix the authentication bug and test the fix."

    Supervisor
         |
         v
    Coding Agent
         |
         v
    Testing Agent

Not every request requires an agent.

Example:

    User:
    "What database does this project use?"

This may only require:

    RAG + Memory + LLM


---

## Agent Architecture

An agent is not another LLM.

An agent is a system containing:

    Agent =
        Instructions
        + LLM
        + Tools
        + Context
        + State
        + Workflow


For example:

    Coding Agent
        |
        +-- Coding instructions
        +-- GPT-6 Astra
        +-- Project context
        +-- search_code()
        +-- read_file()
        +-- edit_file()
        +-- run_tests()


The LLM performs reasoning.

The agent provides the environment and capabilities in which the LLM operates.


---

## Example Workflow

User:

    "Fix the login bug and test it."

Step 1:

    FastAPI receives the request.

Step 2:

    Supervisor receives the task.

Step 3:

    GPT-6 Astra analyzes the task.

Step 4:

    Supervisor determines:

        Coding Agent → Testing Agent

Step 5:

    Coding Agent retrieves relevant project context.

Step 6:

    GPT-6 Astra analyzes the code.

Step 7:

    GPT-6 Astra requests a tool operation such as:

        search_code()

Step 8:

    The agent executes the tool and returns the result to GPT-6 Astra.

Step 9:

    GPT-6 Astra determines the required modification.

Step 10:

    Coding Agent executes:

        edit_file()

Step 11:

    Testing Agent runs:

        run_tests()

Step 12:

    GPT-6 Astra analyzes the test results.

Step 13:

    ProjectMind returns the final result to the user.


---

## Technology Stack

### Backend

- Python
- FastAPI
- Pydantic

### AI

- GPT-6 Astra
- KIE.ai API
- Nemotron
- llama.cpp / llama-server

### Knowledge

- Embeddings
- Vector Database
- RAG
- Hybrid Retrieval
- Reranking

### Agent System

- Custom agent architecture
- Supervisor
- Specialized agents
- Tool calling
- LangGraph (later)

### Database

- PostgreSQL

### Development

- Git
- GitHub
- Antigravity
- Claude Sonnet / Opus


---

## Development Roadmap

### Phase 1 — API Foundation

- Learn HTTP
- Build FastAPI server
- Create REST endpoints
- Test API

### Phase 2 — LLM Integration

- Integrate GPT-6 Astra
- Create LLM service
- Handle requests/responses
- Protect API keys

### Phase 3 — Project Context

- Read project files
- Parse files
- Chunk documents
- Generate embeddings
- Store vectors
- Implement retrieval

### Phase 4 — Memory

- Design project memory
- Store important project facts
- Retrieve memory during conversations

### Phase 5 — Tools

Implement tools such as:

- search_code()
- read_file()
- edit_file()
- create_file()
- run_tests()

### Phase 6 — Single Agent

Build one Coding Agent.

    User
      ↓
    Coding Agent
      ↓
    GPT-6 Astra
      ↓
    Tools
      ↓
    Result


### Phase 7 — Multiple Agents

Add:

- Review Agent
- Testing Agent

### Phase 8 — Supervisor

Implement dynamic agent routing.

    User
      ↓
    Supervisor
      ↓
    Select Agent(s)
      ↓
    Execute Workflow


### Phase 9 — LangGraph

Use LangGraph when the basic agent architecture is understood and working.

### Phase 10 — MCP

Add MCP for standardized tool/context integration.

### Phase 11 — LLM Abstraction

Support multiple providers:

    LLM Interface
       |
       +-- GPT-6 Astra
       +-- Nemotron
       +-- Other models


### Phase 12 — UI + Deployment

- Project dashboard
- Chat interface
- Agent status
- Project knowledge view
- Memory view
- Deployment


---

## Project Goal

The final system should allow a developer to provide a software project and
interact with an AI that understands the project's context.

The system should be capable of:

- Understanding project structure
- Answering project-specific questions
- Remembering important project information
- Retrieving relevant code and documentation
- Writing and modifying code
- Reviewing code
- Running tests
- Dynamically selecting appropriate AI agents
- Supporting multiple LLM providers


---

## Future Vision

ProjectMind AI aims to become an intelligent AI development workspace rather
than a simple coding chatbot.

The system should understand:

    Project
       |
       +-- Code
       +-- Documentation
       +-- Requirements
       +-- Architecture
       +-- Database
       +-- Memory
       +-- Conversations
       +-- Development Tasks

and use that understanding to coordinate AI assistance throughout the
development lifecycle.