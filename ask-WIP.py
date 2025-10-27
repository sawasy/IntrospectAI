#!/usr/bin/env python3


import warnings

from langchain_ollama import OllamaEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from langchain.chains import GraphCypherQAChain
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import Qdrant
from rich import print
from rich.console import Console
from rich.prompt import Prompt

import config

from utilities import embed_str

# import langchain
# langchain.debug = True


def ask_question(task: str, llm: ChatOllama, retriever: VectorStoreRetriever) -> str:
    question_for_vector = f"""
        Task: You have been asked '{task}'
        Adhere to these instructions:
        - Return a question, to gather information you need to complete the task.
        - Only return the question.
        - No commentatry
    """

    messages = [
        (
            "system",
            "You are a helpful assistant.",
        ),
        ("human", question_for_vector),
    ]

    vector_query = llm.invoke(messages)
    print(f"Vector Question: {vector_query.content}")
    context = retriever.invoke(vector_query)

    graph_data = ""

    prompt = [
        HumanMessage(
            content=f"""
            Adhere to these instructions:
            - Answer as if you are an expert in {context} {graph_data} (no hinting at context, please!)
            - Assume expertise on {config.your_name}.
            - Provide concise and direct answers.
            - Be consise in your answers.
            - Do not make up facts about {config.your_name}.
            Question: {task}
            Answer:
            """
        )
    ]

    return llm.invoke(prompt).content


def ask_llm_random_question(task: str, previous_questions: str, llm: ChatOllama) -> str:
    random_question_prompt = [
        HumanMessage(
            content=f"""
                Adhere to these instructions:
                - Give only one quesiton.
                - Use their name, {config.your_name} in the question.
                - Phrase the question in third person voice.
                - Base the idea on the information
                - Be creative in your question.
                - Do not make up facts about {config.your_name}.
                - No commentary or explainations
                {previous_questions}
                Questions: {task}
                Answer:
            """
        )
    ]
    return llm.invoke(random_question_prompt).content


if __name__ == "__main__":
    warnings.filterwarnings("ignore")

    console = Console()
    console.clear()

    questions = []

    llm = ChatOllama(model=config.llm_asking_model, base_url=config.llm_url)

    llm_cypher = ChatOllama(model=config.llm_cypher_model, base_url=config.llm_url)

    # Convert documents to Embeddings and store them
    vectorstore = Qdrant.from_existing_collection(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
        collection_name=config.project_name,
        embedding=embed_str,
    )

    documents_returned = (
        50  # THe lower the number the faster, but less accurate/interesting...
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": documents_returned})

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
                user_input = ask_llm_random_question(
                    task=f"Give a question about {config.your_name}.",
                    llm=llm,
                    previous_questions=questions,
                )
            console.print(
                f"[dodger_blue2]Okay. Asking random question: \n\n [orange1]{user_input}"
            )

        elif user_input.lower().strip() in ["introspective", "intro", "i"]:
            with console.status(
                "[deep_sky_blue4]Generating light hearted introspective question. Please wait.\n"
            ):
                questions = []
                user_input = ask_llm_random_question(
                    task="Give an introspective question Matt should ask himself.",
                    llm=llm,
                    previous_questions=questions,
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
            answer = ask_question(task=user_input, llm=llm, retriever=retriever)

        console.print(f"\n[turquoise2]{answer}\n")

        with console.status("[deep_sky_blue4]Thinking up new question..."):
            followup = ask_llm_random_question(
                task="Based on the following questions I have already asked, what should I ask next?",
                llm=llm,
                previous_questions=questions,
            )

        console.print(f"[dodger_blue2]Hit 'Enter' to ask question: [orange1]{followup}")
