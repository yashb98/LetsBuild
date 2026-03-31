---
name: task-manager
display_name: "Task Management API"
category: backend
difficulty: 6
requirements:
  - "CRUD endpoints for projects and tasks"
  - "Tasks belong to projects, support labels and due dates"
  - "Priority sorting (urgent, high, medium, low)"
  - "Filter tasks by status, label, due date, and assignee"
  - "Bulk operations (mark complete, move to project, delete)"
  - "Pagination with cursor-based navigation"
bonus_features:
  - "Task dependencies and blocking relationships"
  - "Activity timeline per task"
  - "Recurring task templates"
time_limits:
  research: 1800
  architecture: 900
  build: 5400
  cross_review: 900
  fix_sprint: 900
judging_weights:
  functionality: 0.30
  code_quality: 0.20
  test_coverage: 0.15
  ux_design: 0.15
  architecture: 0.10
  innovation: 0.10
constraints:
  stack: "Python+FastAPI or Node+Express"
  auth: false
  must_run: "docker-compose up or python main.py"
hidden_test_path: "tests/arena/hidden/task_manager_tests.py"
---

# Task Management API

Build a complete task management API with projects, tasks, labels, due dates, and priority sorting.

The API should follow REST conventions with proper HTTP status codes, validation errors, and pagination. Data persistence should use SQLite for simplicity.

Pay attention to data integrity: deleting a project should handle its tasks, changing a task's project should be atomic, and concurrent updates should be safe.
