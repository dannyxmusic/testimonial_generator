import asyncio
import logging
import os
import subprocess
import requests

from bson import ObjectId
from flask import Flask, request, jsonify
from pymongo import MongoClient

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Atlas connection URI
MONGO_URI = os.environ.get('MONGO_URI')
client = MongoClient(MONGO_URI)

# Access the database and collection
db = client['tpc_survey_f1']
collection = db['cyclic_server']

# Path to the openai.py script
OPENAI_SCRIPT_PATH = 'openai_tg.py'


def parse_pretty_data(pretty_data):
    """
    Parse the pretty data received from the form submission.

    Args:
        pretty_data (str): The pretty-formatted data received from the form.

    Returns:
        dict: A dictionary containing the parsed data.
    """
    questions = [
        "Please Enter your Email Address",
        "How would you rate the ease of transitioning and implementation to TPC's services from your previous payroll provider?",
        "How user-friendly do you find iSolved, TPC's HR and payroll software?",
        "Who was your previous Payroll Provider?",
        "What field or industry does your company specialize in?",
        "How would you rate your satisfaction for TPC over your previous payroll provider?",
        "How would you rate your experience with TPC's customer service in addressing your inquiries and concerns?",
        "How many employees does your company currently process payroll for?",
        "How inclined are you to recommend Grant Stuart and TPC's services to another business?",
        "Please share your experience or any additional feedback you have regarding your experience with Grant Stuart and TPC."
    ]

    extracted_data = {}
    survey_responses = {}

    for i, question in enumerate(questions):
        if "Please Enter your Email Address" in question:
            email = pretty_data.split(":")[1].strip().split(",")[0]
            continue

        next_question_index = pretty_data.find(
            questions[i + 1]) if i < len(questions) - 1 else len(pretty_data)
        answer = pretty_data[pretty_data.find(
            question) + len(question):next_question_index]
        answer = answer.replace(":", "").replace(",", "").strip()

        # Exclude email from survey responses
        if "Please Enter your Email Address" not in question:
            survey_responses[question] = answer

    extracted_data['email'] = email
    extracted_data['survey_responses'] = survey_responses

    return extracted_data


async def process_openai_script(inserted_id):
    """
    Asynchronously process the openai.py script.
    """
    try:
        # Assuming your Flask server is hosted at https://easy-plum-stingray-toga.cyclic.app/
        url = 'https://easy-plum-stingray-toga.cyclic.app/process_openai'
        # Assuming you want to pass inserted_id as a payload
        insert_id = ObjectId(inserted_id)
        payload = {'_id': insert_id}
        response = requests.post(url, json=payload)

        if response.status_code == 200:
            print('Internal HTTP request to process_openai endpoint successful')
        else:
            print('Internal HTTP request to process_openai endpoint failed')
    except Exception as e:
        print(f'An error occurred: {str(e)}')


@app.route('/submit-form', methods=['POST'])
async def submit_form():
    """
    Endpoint to handle form submissions.
    """
    try:
        form_id = request.form.get('formID')
        submission_id = request.form.get('submissionID')
        webhook_url = request.form.get('webhookURL')
        pretty_data = request.form.get('pretty')

        if not all([form_id, submission_id, webhook_url, pretty_data]):
            return 'One or more required fields are missing.', 400

        parsed_data = parse_pretty_data(pretty_data)

        document = {
            'formID': form_id,
            'submissionID': submission_id,
            'webhookURL': webhook_url,
            **parsed_data
        }

        result = collection.insert_one(document)

        # Asynchronously process the openai.py script
        asyncio.create_task(process_openai_script(result.inserted_id))

        return jsonify({
            'message': 'Document inserted successfully',
            'inserted_id': str(result.inserted_id),
        }), 200

    except Exception as e:
        logger.exception(f'An error occurred: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/process_openai', methods=['POST'])
async def process_openai():
    """
    Endpoint to handle openai testimonial generation.
    """
    # Parse the JSON payload from the request
    data = request.json

    # Retrieve the inserted ID from the payload
    inserted_id = data.get('_id')  # Change key to match the payload

    if inserted_id is None:
        return jsonify({'error': 'Inserted ID not found in request payload'}), 400

    try:
        test_process = subprocess.Popen(['python', OPENAI_SCRIPT_PATH, str(inserted_id)],
                                        stdout=subprocess.PIPE)
        test_output, _ = test_process.communicate()
        test_output = test_output.decode('utf-8').strip()
        # Handle output if needed
    except Exception as e:
        # Handle exceptions
        pass

if __name__ == '__main__':
    app.run(debug=True)
