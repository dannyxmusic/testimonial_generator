import asyncio
import json
import logging
import os
import sys

from operator import itemgetter
from flask import jsonify
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the OpenAI API key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Initialize OpenAI instance
model = ChatOpenAI(model='gpt-3.5-turbo', temperature=0,
                   api_key=OPENAI_API_KEY)

# Initialize output parser
output_parser = StrOutputParser()


async def send_post_request(summary, history, insert_id):
    """
    Send HTTP POST request with summary and history data.
    """
    try:
        history = history

        # Assuming 'history' is a dictionary containing a 'history' key with a list of messages
        history_serializable = []

        # Iterate over each message in the history
        for message in history['history']:
            # Convert HumanMessage objects to dictionaries
            if isinstance(message, HumanMessage):
                message_dict = {'Human': message.content}
                history_serializable.append(message_dict)
            # Convert AIMessage objects to dictionaries
            elif isinstance(message, AIMessage):
                message_dict = {'Ai': message.content}
                history_serializable.append(message_dict)
            # Handle unrecognized message types
            else:
                logger.warning(f"Unrecognized message type: {type(message)}")

        # Create the payload dictionary
        payload = {'history': history_serializable}

        # Convert the payload to JSON format
        payload_json = json.dumps(payload)

        url = 'https://easy-plum-stingray-toga.cyclic.app/process_openai2'
        payload = {
            'summary': summary,
            'history': payload_json,
            'insert_id': insert_id
        }

        response = requests.post(url, json=payload)
        if response.status == 200:
            logger.info(
                'Internal HTTP request to process_openai endpoint successful')
        else:
            logger.error(
                'Internal HTTP request to process_openai endpoint failed')

    except Exception as e:
        logger.error(f'An error occurred: {str(e)}')


async def process_openai(insert_id, survey_data):
    """
    Process data using OpenAI.
    """
    survey_responses = survey_data

    prompt1 = ChatPromptTemplate.from_messages([
        ("system", "You are an AI designed to assist in testimonial generation. I provide you survey results and you do 2 things; 1. analyze sentiment. 2. Detect recurring wordage or phrasing from previous testimonials."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    prompt2 = ChatPromptTemplate.from_messages([
        ("system", "You are an AI tool designed to assist in testimonial generation. I provide you survey results and you do 3 things; 1. List all the survey responses from the original object id #. 2. extract any recurring wordage or phrasing from previous testimonials or listed by ai in the conversation history. 3. Briefly summarize the conversation between human and AI for contextual prompt generation."),
        ("human", "{input}"),
    ])

    memory = ConversationBufferMemory(return_messages=True)
    memory.load_memory_variables({})

    chain = (RunnablePassthrough.assign(
        history=RunnableLambda(memory.load_memory_variables) | itemgetter("history"))
        | prompt1 | model | output_parser)

    chain2 = prompt2 | model | output_parser

    inputs = {
        "input": f"Here is a survey with the '_id': {insert_id}. Please review the survey and confirm that you processed the data: Survey response = {survey_responses}"
    }

    response = chain.invoke(inputs)
    memory.save_context(inputs, {"output": response})

    inputs = {
        "input": f"Review these historical testimonial responses for recurring language and phrasing. Document them and we will avoid using repeat language in our future testimonial generations. Historical Documents = {contents}"
    }
    response = chain.invoke(inputs)
    memory.save_context(inputs, {"output": response})

    history = memory.load_memory_variables({})

    inputs = {
        "input": f"Please review the conversation history. conversation_history = {history}, 1. Give me a summary of the original survey questions and responses. 2. List repeating words or phrases from the Historical Documents. 3. Summarize the human to ai conversation."
    }
    summary = chain2.invoke(inputs)

    # Asynchronously process the openai.py script
    asyncio.create_task(send_post_request(summary, history, insert_id))

    logger.info('Task Created')

if __name__ == "__main__":
    try:
        if len(sys.argv) < 4:
            logger.error("Usage: python openai_test.py <insert_id> <data>")
            sys.exit(1)

        insert_id = sys.argv[1]
        survey_data = sys.argv[2]
        contents = sys.argv[3]

        # Run process_openai asynchronously
        asyncio.run(process_openai(
            insert_id=insert_id, survey_data=survey_data))

        # Return a success message
        print(
            jsonify({'message': 'OpenAI subprocess completed successfully'}), 200)

    except Exception as e:
        # Log the exception
        logger.exception(f'An error occurred: {str(e)}')
        # Return an error message
        print(jsonify({'error': str(e)}), 500)
