#!/usr/bin/env python3
"""Simple command-line to-do list app."""

import json
import sys
from pathlib import Path

TASKS_FILE = Path(__file__).parent / "tasks.json"


def load_tasks():
    if TASKS_FILE.exists():
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return []


def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def add_task(tasks, description):
    tasks.append({"description": description, "done": False})
    save_tasks(tasks)
    print(f"Added: {description}")


def list_tasks(tasks):
    if not tasks:
        print("No tasks yet.")
        return
    for i, task in enumerate(tasks, 1):
        status = "x" if task["done"] else " "
        print(f"[{status}] {i}. {task['description']}")


def complete_task(tasks, index):
    if 1 <= index <= len(tasks):
        tasks[index - 1]["done"] = True
        save_tasks(tasks)
        print(f"Completed: {tasks[index - 1]['description']}")
    else:
        print("Invalid task number.")


def delete_task(tasks, index):
    if 1 <= index <= len(tasks):
        removed = tasks.pop(index - 1)
        save_tasks(tasks)
        print(f"Deleted: {removed['description']}")
    else:
        print("Invalid task number.")


def print_usage():
    print("Usage:")
    print("  python todo.py add <description>")
    print("  python todo.py list")
    print("  python todo.py done <task number>")
    print("  python todo.py delete <task number>")


def main():
    args = sys.argv[1:]
    if not args:
        print_usage()
        return

    command = args[0]
    tasks = load_tasks()

    if command == "add" and len(args) > 1:
        add_task(tasks, " ".join(args[1:]))
    elif command == "list":
        list_tasks(tasks)
    elif command == "done" and len(args) > 1 and args[1].isdigit():
        complete_task(tasks, int(args[1]))
    elif command == "delete" and len(args) > 1 and args[1].isdigit():
        delete_task(tasks, int(args[1]))
    else:
        print_usage()


if __name__ == "__main__":
    main()
