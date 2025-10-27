#!/usr/bin/env python3

"""
What it does

This code is a chat-based conversational AI system that uses natural language processing and
machine learning to answer questions. It appears to be designed for knowledge graph-based
questioning, where the AI generates follow-up questions based on previous queries.

The system has two main components:

1. A question generator that asks the user a prompt (e.g., "Give a question about {your_name}.") and
then uses the provided context to generate a new question.
2. An answer generator that takes in a user's query or generated question, processes it
through a machine learning model (in this case, an Ollama Chat Model), and returns an answer.

Inputs

- User input: The system accepts user input via a prompt, which can be one of the following:
        - A specific question
        - "Random" to generate a random question
        - "Introspective" to generate a light-hearted introspective question
        - An empty string to repeat the previous question
- Context data: The system uses pre-existing knowledge graph data (stored in a Neo4j database)
    and document embeddings (stored in Qdrant) to provide context for generated questions.

Outputs

- Generated question: When the user inputs "Random" or "Introspective", the system generates
    a new question based on the provided context.
- Answer: The system processes the user's input query through the Ollama Chat Model and
    returns an answer in plain text format.
"""

import warnings

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_qdrant import Qdrant

from langchain_ollama import ChatOllama

from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph

from rich import print
from rich.console import Console
from rich.prompt import Prompt

from utilities import embed_str

import config

# import langchain
# langchain.debug = True

if __name__ == "__main__":
    warnings.filterwarnings("ignore")

    console = Console()
    console.clear()

    questions = []
    model_local = ChatOllama(model=config.llm_asking_model, base_url=config.llm_url)

    # Convert documents to Embeddings and store them
    vectorstore = Qdrant.from_existing_collection(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
        collection_name=config.project_name,
        embedding=embed_str,  # embed_str from utilities.py
    )

    # graph = Neo4jGraph(
    #     url=config.neo4j_url,
    #     username=config.neo4j_login,
    #     password=config.neo4j_pw,
    # )

    llm = ChatOllama(model=config.llm_model, base_url=config.llm_url)
    llm_cypher = ChatOllama(model=config.llm_cypher_model, base_url=config.llm_url)

    # prompt_template = """
    # Adhere to these instructions:
    # - Answer as if you are an expert in {context} {graph_data} (no hinting at context, please!)
    # - Assume expertise on {your_name}.
    # - Provide concise and direct answers.
    # - Be consise in your answers.
    # - Do not make up facts about {your_name}.
    # Question: {question}
    # Answer:
    # """

    prompt_template = """
Context: {context}
Question: {question}
Answer:
*  Keep the answer concise and to the point.
*  Only use information provided in the context.  Do not make assumptions.
*  If the context does not contain the answer, say "I don't know."

    """

    prompt_template2 = """
    Adhere to these instructions:
        - Give only one quesiton.
        - Use their name, {your_name} in the question.
        - Phrase the question in third person voice.
        - Base the idea on the information
        - Be creative in your question.
        - Do not make up facts about {your_name}.
        - No commentary or explainations
    {previous}
    Questions: {questions}
    Answer:
    """

    prompt = ChatPromptTemplate.from_template(prompt_template)
    prompt2 = ChatPromptTemplate.from_template(prompt_template2)

    documents_returned = (
        50  # THe lower the number the faster, but less accurate/interesting...
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": documents_returned})

    # graph_data = GraphCypherQAChain.from_llm(
    #     graph=graph,
    #     cypher_llm=llm_cypher,
    #     qa_llm=llm,
    #     validate_cypher=True,
    #     return_intermediate_steps=True,
    #     verbose=False,
    # )

    chain1 = (
        {
            "context": retriever,
            #  "graph_data": graph_data, # Switch comments on these two lines to use graphdb
            "graph_data": lambda x: "",
            "question": RunnablePassthrough(),
            "your_name": lambda x: config.your_name,
        }
        | prompt
        | model_local
        | StrOutputParser()
    )
    chain2 = (
        {
            "previous": RunnablePassthrough(),
            "questions": lambda x: questions,
            "your_name": lambda x: config.your_name,
        }
        | prompt2
        | model_local
        | StrOutputParser()
    )

    random_question = ""
    followup = ""
    while True:
        print(
            "[deep_sky_blue1]Enter 'exit', 'quit' or 'q' to quit. Enter 'random' if you would like the AI to generate a question, 'introspective' for introspective.\n"
        )
        user_input = Prompt.ask(
            "[dodger_blue2]What would you like to know? => [orange1]"
        )

        if user_input.lower().strip() in ["exit", "q", "quit"]:
            print("Exiting...")
            break  # Breaks out of the loop when 'exit' or equivalent is entered

        elif user_input.lower().strip() in ["random", "rand", "r"]:
            with console.status(
                "[deep_sky_blue4]Generating random question. Please wait.\n"
            ):
                questions = []
                user_input = chain2.invoke(f"Give a question about {config.your_name}.")
            console.print(
                f"[dodger_blue2]Okay. Asking random question: \n\n [orange1]{user_input}"
            )

        elif user_input.lower().strip() in ["introspective", "intro", "i"]:
            with console.status(
                "[deep_sky_blue4]Generating light hearted introspective question. Please wait.\n"
            ):
                questions = []
                user_input = chain2.invoke(
                    "Give an introspective question Matt should ask himself."
                )
            console.print(
                f"[dodger_blue2]Okay. Asking random question: \n\n [orange1]{user_input}"
            )

        elif user_input == "":
            console.print(f"[dodger_blue2]Asking: [orange1]{followup}")
            user_input = followup
            questions.append(followup)

        else:
            questions.append(user_input)

        with console.status("[deep_sky_blue4]Thinking about your question..."):
            answer = chain1.invoke(user_input)

        console.print(f"\n[turquoise2]{answer}\n")

        with console.status("[deep_sky_blue4]Thinking up new question..."):
            followup = chain2.invoke(
                "Based on the following questions I have already asked, what should I ask next?"
            )

        console.print(f"[dodger_blue2]Hit 'Enter' to ask question: [orange1]{followup}")
