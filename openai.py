from operator import itemgetter
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAI
from langchain_core.messages import HumanMessage, AIMessage
from bson import ObjectId
import json
import os
import sys
from pymongo import MongoClient

# MongoDB Atlas connection URI
MONGO_URI = os.environ.get('MONGO_URI')
client = MongoClient(MONGO_URI)

# Access the database and collection
db = client['tpc_survey_f1']
collection = db['cyclic_server']

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

llm = OpenAI(openai_api_key=OPENAI_API_KEY)
chat_model = ChatOpenAI(openai_api_key=OPENAI_API_KEY,
                        model="gpt-3.5-turbo-0125")


def process_openai(insert_id, data):
    # Convert insert_id to ObjectId
    try:
        insert_id = ObjectId(insert_id)
    except Exception as e:
        print(f"Error converting insert_id to ObjectId: {e}")
        sys.exit(1)

    data_from_db = collection.find_one({"_id": insert_id})

    if not data_from_db:
        print(f"Document with _id {insert_id} not found.")
        sys.exit(1)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("ai", "you are a helpful chatbot"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )

    prompt2 = ChatPromptTemplate.from_messages(
        [
            ("ai", "you analyze sentiment and return only a numerical value"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )

    memory = ConversationBufferMemory(return_messages=True)

    memory.load_memory_variables({})

    chain = (
        RunnablePassthrough.assign(
            history=RunnableLambda(
                memory.load_memory_variables) | itemgetter("history")
        )
        | prompt
        | llm
    )

    chain2 = (
        RunnablePassthrough.assign(
            history=RunnableLambda(
                memory.load_memory_variables) | itemgetter("history")
        )
        | prompt2
        | llm
    )

    inputs = {"input": ("Please review this survey data: " f"{data}")}
    response = chain.invoke(inputs)

    memory.save_context(inputs, {"output": response})

    history = memory.load_memory_variables({})

    inputs = {
        "input": "Gauge the sentiment and normalize. The response to (enter your email), (how many employees), and (please add additional feedback) are all user input. However all other survey questions are rated from very difficult to very easy, dissatisfied to very satisfied, and unlikely to very likely. Please refer to the survey responses and estimate a normalized sentiment value. Return the numerical value you've determined and no other context."}
    response = chain2.invoke(inputs)

    sentiment_temperature = response

    memory.save_context(inputs, {"output": response})

    memory.load_memory_variables({})

    inputs = {
        "input": "Write a testimonial from the perspective of the person who completed the survey. The testimonial should be 30-50 words long. Include the wording from the final survey question (please provide any additional feedback) to retain authenticity of the review."}
    response = chain.invoke(inputs)

    memory.save_context(inputs, {"output": response})

    memory.load_memory_variables({})

    inputs = {
        "input": "Write a testimonial from the perspective of the person who completed the survey. This testimonial should be 60-80 words long. Include the wording from the final survey question (please provide any additional feedback) to retain authenticity of the review."}
    response = chain.invoke(inputs)

    memory.save_context(inputs, {"output": response})

    memory.load_memory_variables({})

    inputs = {
        "input": "Write a testimonial from the perspective of the person who completed the survey. The testimonial should be 100 words or longer. Include the wording from the final survey question (please provide any additional feedback) to retain authenticity of the review. Be professional and detailed."}
    response = chain.invoke(inputs)

    memory.save_context(inputs, {"output": response})
    history = memory.load_memory_variables({})

    conversationHistory = []

    # Extract content from each message in the history and add it to conversationHistory
    for i, message in enumerate(history['history'], start=1):
        content_key = f"content{i}"
        if isinstance(message, HumanMessage):
            content = message.content
            conversationHistory.append({content_key: content})
        elif isinstance(message, AIMessage):
            content = message.content
            conversationHistory.append({content_key: content})

    conversationHistory_json = json.dumps(conversationHistory, indent=2)

    try:
        # Update the original document with conversation history
        collection.update_one({"_id": insert_id}, {
                              "$set": {"conversationHistory": conversationHistory}})
        print(f"Conversation history updated for document with _id {
              insert_id}")
    except Exception as e:
        print(f"Error updating conversation history: {e}")

    print(conversationHistory_json)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python openai.py <insert_id>")
        sys.exit(1)
    insert_id = sys.argv[1]
    process_openai(insert_id, data)