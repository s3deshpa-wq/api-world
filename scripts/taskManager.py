import json
import logging
import anthropic
from pydantic import BaseModel

logging.basicConfig(
    filename="../venv/taskManager.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.debug("Detailed info, useful only when debugging")
logging.info("Something normal happened")
logging.warning("Something unexpected, but not broken")
logging.error("Something failed")
logging.critical("Something failed badly, system may be unusable")

from dotenv import load_dotenv
task_list=[]

#********************************************************************************
# ** Defining tool functionality **

def add_task(title: str, priority:str) -> str:
        global task_list
        """Returns task name after adding it to the task list."""
#        task_list.append(Task(title, priority, "pending"))

        new_task = (Task(title=title, priority=priority, status="pending"))
        task_list.append(new_task)
        save_task()
        return f"Task added -> {new_task.title}"

def list_tasks() -> str:
        """Return list of tasks."""
        pending_tasks = [t for t in task_list if t.status == "pending"]
        if not pending_tasks:
            return "No pending tasks."
        return "\n".join(f"- {t.title} (priority: {t.priority})" for t in pending_tasks)

def complete_tasks(title: str) -> str:
        """Mark task status as completed."""
        for task in task_list:
            if task.title == title:
                task.status = "completed"
                save_task()
                return f"{task.title} marked as {task.status}"
        return f"Task '{title}' not found"
def get_task_count() -> str:
        """send the number of pending tasks """
        pending_count = 0
        for task in task_list:
            if task.status == "pending":
                pending_count += 1
        return f"You have {pending_count} pending tasks"
def save_task():
 try:
    with open("../venv/data.json", "w") as file:
        json.dump([t.to_dict() for t in task_list], file, indent=2)
 except Exception as e:
    print(e)

def load_tasks():
 try:
    with open("../venv/data.json", "r") as file:
         raw_data=json.load(file)
    return[Task(title=d["title"], priority=d["priority"], status=d["status"]) for d in raw_data]
     #   task_list = [Task(*line.strip().split("-")) for line in file]
 except FileNotFoundError:
     return []
 except Exception as e:
     print(e)
     return []
class AddTaskArgs(BaseModel):
    title: str
    priority: str

    @staticmethod
    def add_task_validated(**kwargs):
        args = AddTaskArgs(**kwargs)
        return add_task(args.title, args.priority)

tools = {
        "add_task": AddTaskArgs.add_task_validated,
        "list_tasks": list_tasks,
        "complete_tasks": complete_tasks,
        "get_task_count": get_task_count
    }
class Task(BaseModel):
    title: str
    priority: str
    status: str = "pending"

    def __repr__(self):
        return f"{self.title} (priority: {self.priority}, status: {self.status})"

    def to_dict(self):
        return {"title": self.title, "priority": self.priority, "status": self.status}
class TaskManager:
      def __init__(self, name:str, tools, system_prompt:str):
        self.name = name
        self.tools = tools
        self.history = []
        self.system_prompt=system_prompt
      #def ask_claude(self, user_question:str):
      def ask_claude(self, user_question):
              self.history.append({"role": "user", "content": user_question})
              while True:
                try:
                  resp = client.messages.create(
                      model="claude-sonnet-5", max_tokens=1024,
                      tools=tool_schema, messages=self.history,
                      system=self.system_prompt
                  )
                  self.history.append({"role": "assistant", "content": resp.content})
                  if resp.stop_reason != "tool_use":
                      print("".join(b.text for b in resp.content if b.type == "text"))
                      return
                  results = [
                      {"type": "tool_result", "tool_use_id": b.id,
                       "content": str(self.call_tool(b.name, **b.input))}
                      for b in resp.content if b.type == "tool_use"
                  ]
                  self.history.append({"role": "user", "content": results})
                except Exception as e:
                    logging.error(f"Error calling tool: {e}")
                    return f"Error calling tool: {e}"
#Calling the appropriate tool

      def call_tool(self, tool_name, **kwargs):
        logging.info(f"Calling tool: {tool_name} with args: {kwargs}")
        if tool_name not in self.tools:
            logging.error(f"Unknown tool: {tool_name}")
            return f"Error: unknown tool '{tool_name}'"
        try:
            result = self.tools[tool_name](**kwargs)
            return result
        except Exception as e:
            logging.error(f"Error calling tool {tool_name}: {e}")
            return f"Error calling {tool_name}: {e}"

 #    def run(self, plan):
 #       plan: list of dicts like {'tool': 'get_weather', 'args': {'city': 'Mumbai'}}
 #       for step in plan:
 #           result = self.call_tool(step["tool"], **step["args"])
 #           print(f"[{self.name}] {step['tool']}({step['args']}) -> {result}")
#********************************************************
#** Defining tool registry


tool_schema = [
    {
        "name": "add_task",
        "description": "Adds a task to the task list",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the task"},
                "priority": {"type": "string", "description": "Priority of the task"},
                "status": {"type": "string", "description": "Status of the task"},
            },
            "required": ["title","priority"]
        }
    },
    {
        "name": "list_tasks",
        "description": "Send list of pending tasks",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_list": {"type": "array", "description": "Task list"},
            },
        }
    },
    {
        "name": "complete_tasks",
        "description": "Mark task as completed",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "priority": {"type": "string", "description": "Priority of the task"},
                "status": {"type": "string", "description": "Status of the task"},
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_task_count",
        "description": "Return no of pending tasks ",
        "input_schema": {
            "type": "object",
            "properties": {
                "pending_count": {"type": "number", "description": "count of pending tasks"},
            },
        }
    },
]




#********************************************************************************
#** Loading API key and creation of Anthropic Client **
load_dotenv()

client=anthropic.Anthropic()

taskmanager=TaskManager("Jarvis", tools, system_prompt="You are a terse, efficient task management assistant. Always confirm actions concisely.")

task_list=load_tasks()
while True:
    user_question=input("Enter a message....")
    if user_question=="quit":
        break
    else:
        taskmanager.ask_claude(user_question)



