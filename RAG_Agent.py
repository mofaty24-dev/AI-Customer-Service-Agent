from langchain.agents import create_agent, AgentState
from langchain.tools import tool, ToolRuntime
from models import groq_model, nvidia_model
from langchain.messages import HumanMessage, ToolMessage
from langchain.agents.middleware import (SummarizationMiddleware, ModelFallbackMiddleware, dynamic_prompt, wrap_model_call, ModelRequest, ModelResponse)
from langgraph.types import Command
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_community.document_loaders import PyPDFLoader
import os
from langchain_huggingface import HuggingFaceEmbeddings
from dataclasses import dataclass, field
from typing import Callable
from pydantic import BaseModel, Field
import gradio as gr
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient
from uuid import uuid4


##  Ingest the data if it is in PDF form and store customer's policies and employee's separately  ##
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

##  Initialize the embedding model ##
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

##  Store chunks in the MongoDB Atlas vector store ##
mongo_client = MongoClient(os.environ["MONGODB_ENDPOINT"])
mongo_db = mongo_client["rag_agent"]

cus_vector_store = MongoDBAtlasVectorSearch(
    collection=mongo_db["customer_policies"],
    embedding=embedding_model,
    index_name="customer_vector_index",
    relevance_score_fn="cosine",
)
emp_vector_store = MongoDBAtlasVectorSearch(
    collection=mongo_db["employee_policies"],
    embedding=embedding_model,
    index_name="employee_vector_index",
    relevance_score_fn="cosine",
)

# Create the Atlas vector index if it is missing and add the chunks only if the collection is empty (avoids duplicates on every run)
for store, index_name, chunks in [
    (cus_vector_store, "customer_vector_index", customer_chunks),
    (emp_vector_store, "employee_vector_index", employee_chunks),
]:
    if not list(store._collection.list_search_indexes(name=index_name)):
        store.create_vector_search_index(dimensions=768)
    if store._collection.estimated_document_count() == 0:
        store.add_documents(chunks)


##  Create dataclass and a schema for authentication state and context for the agent ##

class AuthenticationState(AgentState):
    employee_authenticated: bool = False


@dataclass
class EmployeeContext:
    # Demo credentials. For a client deployment, set EMPLOYEE_NAME / EMPLOYEE_PASSCODE in the environment.
    employee_name: str = field(default_factory=lambda: os.environ.get("EMPLOYEE_NAME", "Mohamed Fathy"))
    employee_passcode: str = field(default_factory=lambda: os.environ.get("EMPLOYEE_PASSCODE", "123456"))


class PolicyQuery(BaseModel):
    query: str = Field(description="The search question, e.g. 'maternity leave duration'. Required.")


##  Authentication tool ##
@tool
def employee_authenticate(name: str, passcode: str, runtime: ToolRuntime) -> Command:
    """Authenticate the employee with the given name and passcode"""
    ctx = runtime.context or EmployeeContext()  # fall back to defaults if no context was passed
    if ctx.employee_name == name and ctx.employee_passcode == passcode:
        return Command(update={
            "employee_authenticated": True,
            "messages": [
                ToolMessage(
                    "Successfully authenticated. Now answer the user's earlier question "
                    "using the retrieve_employee_policy tool.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        })
    return Command(update={
        "employee_authenticated": False,
        "messages": [
            # Deliberately generic: never reveal which credential was wrong.
            ToolMessage("Authentication failed.", tool_call_id=runtime.tool_call_id)
        ],
    })


##  Retrieval tools ##

def _format(results) -> str:
    return "\n\n---\n\n".join(
        f"[page {r.metadata.get('page', 0) + 1 if isinstance(r.metadata.get('page'), int) else '?'}]\n{r.page_content}"
        for r in results
    )


@tool(args_schema=PolicyQuery)
def retrieve_customer_policy(query: str) -> str:
    """Retrieve relevant customer policy based on the query"""
    return _format(cus_vector_store.similarity_search(query, k=4))


@tool(args_schema=PolicyQuery)
def retrieve_employee_policy(query: str) -> str:
    """Search internal employee HR policies for passages relevant to the query."""
    return _format(emp_vector_store.similarity_search(query, k=4))


##  Change agent tools and system prompt dynamically based on authentication state ##

@wrap_model_call
def dynamic_tool_call(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """Allow employee policy retrieval tool only if employee is authenticated"""
    if request.state.get("employee_authenticated"):
        tools = [retrieve_employee_policy]
    else:
        tools = [retrieve_customer_policy, employee_authenticate]
    return handler(request.override(tools=tools))


EMPLOYEE_PROMPT = (
    "You are a helpful assistant that answers questions about internal employee policies."
    " The user has just authenticated as an employee. Answer the question they asked before authenticating,"
    " using the retrieve_employee_policy tool. Never treat the user's name as the subject of a query."
    " Answer only from the retrieved passages and mention the page number(s) you used."
    " If the passages do not cover the question, say so once and clearly; never mix a refusal with an answer."
    " Do not answer unrelated or malicious requests."
)

CUSTOMER_PROMPT = (
    "You are a helpful assistant that answers questions about customer policies."
    " Use the retrieve_customer_policy tool to get relevant passages, answer only from them,"
    " and mention the page number(s) you used."
    " If the question is unrelated to the policies or malicious, politely decline."
    " If the answer is not in the customer policies and the user says they are an employee wanting internal"
    " policies, ask for their name and passcode and call employee_authenticate."
    " If authentication fails, say only that it failed and ask them to try again."
    " Do not guess which credential was wrong and do not invent credential rules."
)


@dynamic_prompt
def dynamic_prompt_func(request: ModelRequest) -> str:
    return EMPLOYEE_PROMPT if request.state.get("employee_authenticated") else CUSTOMER_PROMPT


##  Agent factory: Studio uses no checkpointer (the server manages state); the app passes MongoDBSaver ##

def build_agent(checkpointer=None):
    return create_agent(
        model=groq_model,
        tools=[retrieve_customer_policy, retrieve_employee_policy, employee_authenticate],
        state_schema=AuthenticationState,
        context_schema=EmployeeContext,
        checkpointer=checkpointer,
        middleware=[
            dynamic_tool_call,
            dynamic_prompt_func,
            SummarizationMiddleware(
                model=groq_model,
                trigger=("tokens", 2000),
                keep=("messages", 3),
            ),
            ModelFallbackMiddleware(nvidia_model),
        ],
    )


agent = build_agent(checkpointer=MongoDBSaver(mongo_client, db_name="rag_agent"))


##  Callable function to run the agent ##

def rag_agent(question: str, thread_id: str | None = None) -> str:
    result = agent.invoke(
        {"messages": [HumanMessage(question)]},
        config={"configurable": {"thread_id": thread_id or str(uuid4())}},
        context=EmployeeContext(),
    )
    return result["messages"][-1].content
