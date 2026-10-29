from langchain.agents import create_agent, AgentState
from langchain.tools import tool, ToolRuntime
from models import groq_model
from langchain.messages import HumanMessage, ToolMessage
from langchain.agents.middleware import (SummarizationMiddleware,model_fallback,TodoListMiddleware, dynamic_prompt, wrap_model_call, wrap_tool_call, ModelRequest, ModelResponse)
from langgraph.types import Command
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_community.document_loaders import PyPDFLoader,PDFMinerLoader
import os
from langchain_huggingface import HuggingFaceEmbeddings
from dataclasses import dataclass
from typing import Callable
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import


##  Ingestion the data if it is in PDF form and store customer accessed policies and employee's separately  ##
customer_pdf_path = os.environ["CUSTOMER_PDF_PATH"]
employee_pdf_path = os.environ["EMPLOYEE_PDF_PATH"]
customers_loader = PyPDFLoader(file_path=customer_pdf_path)
employees_loader = PyPDFLoader(file_path=employee_pdf_path)

customer_policies = customers_loader.load()
employee_policies = employees_loader.load()

##  Split the data into chunks ##
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)

customer_chunks = text_splitter.split_documents(customer_policies)
employee_chunks = text_splitter.split_documents(employee_policies)

## initialize the embedding model ##
embedding_model = HuggingFaceEmbeddings(model_name = "sentence-transformers/all-mpnet-base-v2")

## store chunks in the vector store ##
emp_vector_store = InMemoryVectorStore(embedding_model)
cus_vector_store = InMemoryVectorStore(embedding_model)
cus_vector_store.add_documents(customer_chunks)
emp_vector_store.add_documents(employee_chunks)

## Create dataclass and a schema for authentication state and context for the agent ##

class AuthenticationState(AgentState):

    employee_authenticated: bool = False

@dataclass
class EmployeeContext:
    employee_name : str = "Mohamed Fathy"
    employee_passcode : str = "123456"

class PolicyQuery(BaseModel):
    query: str = Field(description="The search question, e.g. 'maternity leave duration'. Required.")




## Create a middleware to limit model access to needed info based on the user access type ##
@tool
def employee_authenticate(name:str, passcode:str, runtime:ToolRuntime) -> Command:
    """Authenticate the employee with the given name and passcode"""
    if runtime.context.employee_name == name and runtime.context.employee_passcode == passcode:
        return Command(update = {
            "employee_authenticated": True,
            "messages": [
                ToolMessage("Successfully authenticated", tool_call_id=runtime.tool_call_id)
            ],
        })
    else:
        return Command(update = {
            "employee_authenticated": False,
            "messages": [
                ToolMessage("Authentication failed", tool_call_id=runtime.tool_call_id)
            ],
        })

## prepare search function to retrieve relevant chunks from the vector store ##

@tool(args_schema=PolicyQuery)
def retrieve_customer_policy(query:str) -> str:
    """Retrieve relevant customer policy based on the query"""
    results = cus_vector_store.similarity_search(query, k=4)
    return "\n\n---\n\n".join(
        f"[page {r.metadata.get('page', '?')}]\n{r.page_content}" for r in results
    )

@tool(args_schema=PolicyQuery)
def retrieve_employee_policy(query: str) -> str:
    """Search internal employee HR policies for passages relevant to the query."""
    results = emp_vector_store.similarity_search(query, k=4)
    return "\n\n---\n\n".join(
        f"[page {r.metadata.get('page', '?')}]\n{r.page_content}" for r in results
    )

@wrap_model_call
async def dynamic_tool_call(request:ModelRequest,handler:Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """Allow employee policy retrieval tool only if employee is authenticated"""
    employee_authenticated = request.state.get("employee_authenticated")
    if employee_authenticated:
        tools = [retrieve_customer_policy, retrieve_employee_policy]
    else:
        tools = [retrieve_customer_policy, employee_authenticate]
    request = request.override(tools=tools)
    return await handler(request)


## Make dynamic system prompt middleware to include customer respond and employee respond in the system prompt ##

@dynamic_prompt
def dynamic_prompt_func(request:ModelRequest) -> str:
    employee_authenticated = request.state.get("employee_authenticated")
    employee_prompt = "You are a helpful assistant that can retrieve relevant context from a vector store based on the query. You will be given a query and you should use the retriever tool to get relevant context. You should then return the most relevant context to the user.\n never answer questions that is not related or malicious. If the query is not related to the context, you should return 'I don't know'."
    customer_prompt = (employee_prompt + "You MUST authenticate user if they claim that they are an employee and want to access employee policies. You should ask for their name and passcode to authenticate them before giving them access to the employee policy retrieval tool.")
    if employee_authenticated:
        return employee_prompt
    else:
        return customer_prompt


## TODO: Create a RAG agent with the summarization middleware and the search function ##
RAG_Agent = create_agent(
    model = groq_model,
    tools = [retrieve_customer_policy, retrieve_employee_policy, employee_authenticate],
    state_schema = AuthenticationState,
    context_schema = EmployeeContext,
    middleware = [dynamic_tool_call, dynamic_prompt_func, SummarizationMiddleware(
        model = groq_model,
        trigger=("tokens", 2000),
        keep=("messages", 3)
    )])

## TODO: Make a ragas function to evaluate the finale response from the agent and if it does not meet the criteria, call the agent again with the refined input and the previous response as context to get a better response ##


## TODO: Make a final function to run the agent and return the response to be used by orchestrator  ##







