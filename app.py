from langchain_community.tools import TavilySearchResults
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from typing import TypedDict
from typing import Annotated
import operator
from langchain.output_parsers import PydanticOutputParser
from langgraph.constants import Send
from langgraph.graph import END, StateGraph, START
from langgraph.graph.state import CompiledStateGraph
from fastapi import FastAPI
import os 
from dotenv import load_dotenv
import uvicorn
from fastapi.responses import JSONResponse

# Loading the environment variables
load_dotenv()
# Initializing the app
app = FastAPI(title = "SearchSage")

# Getting the ENVs
gemini_api_key = os.getenv('GOOGLE_API_KEY')
tavily_api_key = os.getenv('TAVILY_API_KEY')
# Initializing the LLM
llm: ChatGoogleGenerativeAI = ChatGoogleGenerativeAI(model = "gemini-1.5-flash" , api_key=gemini_api_key , temperature=0)

# Searching Tool
search_engine = TavilySearchResults(max_results=1,
    search_depth="advanced",
    include_answer=True,)
res = search_engine.invoke('What are the top family vacation spots in Europe, and the best hotels under $200?')

# System Prompts

Queries_prompt: str = """
You are a smart assistant that breaks a query into subqueries. You must return the subqueries in valid JSON format, with a key `"subQueries"` and the value as a list of three queries that are taken place by breaking the main query.

Each query is well divided and will carry a meaning. The output should be formatted like this:
{{
  "subQueries": ["subQuery1", "subQuery2", "subQuery3"]
}}

Here are some examples:

Example 1:
Query: "What are the top family vacation spots in Europe, and the best hotels under $200?"
Response: {{
  "subQueries": ["Top family vacation spots in Europe", " Hotels under $200 at each location"]
}}

Example 2:
Query : "Find the best gaming laptops under $1,500 and where to buy them."
"
Response: {{
  "subQueries": ["top gaming laptops under $1,500", "Online stores with available stock"]
}}

Example 3:
Query: "What are the latest developments in renewable energy since 2018?"
Response: {{
  "subjects": ["advancements in renewable energy.", "Renewable Energy  after 2018"]
}}

Now, generate a list of 3 subQueries from this query:
Query: "{query}"

Return the output as valid JSON, exactly like the examples above, with the key `"subQueries"` and the value as a list of strings.
"""
result_prompt = """ You are a smart assistant in compiling the results and answering the 
question against that data , you have given a set of search results and you have to answer the 
question by using the given search results as a context and the only source of truth . 
Your answer should not be very long just answer the question but keep in mind it will not be very short that you will miss out the important details.
Here are some examples , you can look to
query : "What are the top family vacation spots in Europe, and the best hotels under $200?"
search_results : (search results will be provided to you for now lets suppose you have given a long paragraph of search results)
Combined_results = 1. Paris: Hotel Eiffel ($180); 2. Venice: Casa Bella ($150); 3. Prague: Royal Inn ($190)

query: "Find the best gaming laptops under $1,500 and where to buy them."
Combined_results='1. Razer Blade 15 ($1,499 on Amazon); 2. Alienware m15 ($1,450 on Best Buy)."

query: "What are the latest developments in renewable energy since 2018?"
Combined_results = "Solar efficiency has increased by 25%. Wind turbines are now 30% cheaper due to new materials."
Be Clear and Concise and keep them to the point , here is the question {query}, you have to answer and here are 
 the search_results:
{search_results}
Don't say according to the refrence or according to the text , don't give the impression that 
you are helped by some means , and relate the answer with your questions such as if you are asked
about a number of things you should have to answer them all and act as a assistant that provides accurate
details according to the question
 """


class Queries(BaseModel):
  subQueries: list[str]

class State(TypedDict):
  query : str
  subQueries : list[str]
  Results: Annotated[list, operator.add]
  Final_Result : str


# Initialize PydanticOutputParser
parser = PydanticOutputParser(pydantic_object=Queries)
response = llm.invoke(Queries_prompt.format(query="Top  Hotels in karachi under $100 near Burns Road"))

# Parse the response generated above
parsed_response = parser.parse(response.content)



def Decomposer(state:State):
  print('--------------GENERATING SEARCH QUERIES-----------------')
  query = state['query']
  prompt = Queries_prompt.format(query=query)
  response = llm.invoke(prompt)
  parsed_response = parser.parse(response.content)
  return {"subQueries": parsed_response.subQueries}


def Sender(state: State):
  print('----------MAPPING QUERIES-----------')
  return [Send("Engine", {"Query": s}) for s in state["subQueries"]]

class subQuery(TypedDict):
  Query: str
class result_query(BaseModel):
  result : str
def Engine(query : subQuery)->list[result_query]:
  print('----------SEARCHING-----------')
  print(query)
  tavily_response = search_engine.invoke(query['Query'])
  return {'Results': [tavily_response[0]['content']]}
  # return {'Results':tavily_response[0]['content']}



class Answer (BaseModel):
  answer :str

answer_llm = llm.with_structured_output(Answer)
def Synthesizer(state:State):
  print('--------------SUMMARIZING RESULTS-----------------')
  results = "\n\n".join(state["Results"])
  query = state['query']
  prompt = result_prompt.format(search_results=results , query = query)
  response = answer_llm.invoke(prompt)
  return {'Final_Result':response.answer}



workflow = StateGraph(State)
workflow.add_node("Decomposer", Decomposer)
workflow.add_node("Engine", Engine)
workflow.add_node("Synthesizer", Synthesizer)

workflow.add_edge(START, "Decomposer")
workflow.add_conditional_edges("Decomposer", Sender, ["Engine"])
workflow.add_edge("Engine", "Synthesizer")
workflow.add_edge("Synthesizer", END)

# Compile the graph
graph: CompiledStateGraph = workflow.compile()

# Defining the Request State from the Client
class RequestState(BaseModel):
  message : str

# Definong the Endpoint
@app.post("/query")
def query(request: RequestState):
  query = request.message
  response = graph.invoke({"query": query})
  final_response = response.get('Final_Result' , 'Oops ! No result Found...')
  return JSONResponse(content={"Final_result": final_response})

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000)