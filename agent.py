from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain.prompts import PromptTemplate
from langchain_community.llms import LlamaCpp
from typing import Dict, List, Optional
import json

class JobApplicationAgent:
    def __init__(self, model_path: str):
        self.llm = self._load_model(model_path)
        self.tools = self._initialize_tools()
        self.agent = self._create_agent()
        
    def _load_model(self, model_path: str):
        return LlamaCpp(
            model_path=model_path,
            n_ctx=4096,
            n_threads=8,
            n_gpu_layers=35,
            temperature=0.1,
            max_tokens=512,
            top_p=0.95,
            verbose=False
        )
    
    def _initialize_tools(self) -> List[Tool]:
        tools = [
            Tool(
                name="job_search",
                func=self.search_jobs,
                description="Search for jobs based on criteria. Input: JSON with title, location, experience"
            ),
            Tool(
                name="job_matcher",
                func=self.match_job_to_resume,
                description="Match a job posting to resume. Input: job_id and resume_text"
            ),
            Tool(
                name="form_filler",
                func=self.fill_application_form,
                description="Fill job application form. Input: JSON with form_data and user_profile"
            ),
            Tool(
                name="application_submitter",
                func=self.submit_application,
                description="Submit the filled application. Input: application_id"
            ),
            Tool(
                name="status_updater",
                func=self.update_status,
                description="Update application status in database. Input: JSON with job_id and status"
            )
        ]
        return tools
    
    def _create_agent(self):
        template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""
        
        prompt = PromptTemplate.from_template(template)
        agent = create_react_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True, max_iterations=5)
    
    def search_jobs(self, criteria: str) -> str:
        return json.dumps({"status": "searching", "criteria": criteria})
    
    def match_job_to_resume(self, input_data: str) -> str:
        return json.dumps({"match_score": 0.85, "matched": True})
    
    def fill_application_form(self, form_data: str) -> str:
        return json.dumps({"status": "filled", "form_id": "form_001"})
    
    def submit_application(self, application_id: str) -> str:
        return json.dumps({"status": "submitted", "application_id": application_id})
    
    def update_status(self, status_data: str) -> str:
        return json.dumps({"status": "updated", "data": status_data})
    
    def run(self, resume_data: Dict, job_preferences: Dict) -> Dict:
        task = f"Search and apply to jobs matching: {json.dumps(job_preferences)} using resume data"
        result = self.agent.invoke({"input": task})
        return result