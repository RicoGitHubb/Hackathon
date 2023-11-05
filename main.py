from dotenv import load_dotenv
load_dotenv()
import os
import openai
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
import tempfile
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from flask_session import Session  # You need to install this: pip install Flask-Session

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)  # This is for demonstration only
app.config['SESSION_TYPE'] = 'filesystem'  # Configure session to use the file system

Session(app)  # Initialize the session service

# Set the OpenAI API key from the environment variable
openai.api_key = os.getenv('OPENAI_API_KEY')

# Define the route to serve the index.html file
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Define the route to handle file uploads
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify(error="No file part"), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify(error="No selected file"), 400

    if file:
        filename = secure_filename(file.filename)
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file.name)
            extracted_text = extract_text(temp_file.name)
            session['extracted_text'] = extracted_text  # Store the extracted text in session

        return jsonify(text=extracted_text)

# Function to extract text from the uploaded file
def extract_text(file_path):
    text = ""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ''
    except Exception as e:
        print("An error occurred with PyPDF2:", e)

    if not text:
        try:
            images = convert_from_path(file_path, dpi=300)
            for image in images:
                text += pytesseract.image_to_string(image)
        except Exception as e:
            print("An error occurred with OCR:", e)

    return text

# Define the route to handle conversation with the AI
@app.route('/converse', methods=['POST'])
def converse_with_ai():
    data = request.json
    user_message = data.get('message')

    if not user_message:
        return jsonify(error="No message provided"), 400

    # Retrieve the conversation history from the session, or initialize it if it doesn't exist
    conversation_history = session.get('conversation_history', [])
    
    # Try to retrieve the extracted text from the session, it might be empty if no PDF was uploaded
    extracted_text = session.get('extracted_text', "")

    try:
        # Check if the user has uploaded a PDF and if the AI needs to be informed
        if extracted_text and 'pdf_informed' not in session:
            conversation_history.append({"role": "system", "content": f"This is a PDF document text: {extracted_text}"})
            session['pdf_informed'] = True  # Set a flag to indicate that the AI has been informed about the PDF

        # Introduce the AI with its name and role if not already introduced
        if 'airy_introduced' not in session:
            intro_message = "Welcome to Airy, your adaptive educational assistant brought to you by Aired. I'm not just programmed to answer questions but to foster a profound understanding through a Socratic dialogue that adapts to your individual learning level. As we explore your queries, I'll tailor our conversations to your pace, ensuring that we build on what you know and address where you might need more clarity. With Airy, your educational materials are more than static text—they're a springboard for discovery. I'll analyze your uploads and our discussions to personalize your learning experience, guiding you through complex topics with a focus on the nuances that challenge you. Consider me your companion in learning, attuned to your unique educational journey. I'm here to help you not only find answers but to cultivate insight and understanding, paving the way for long-term success. Let's embark on this dynamic path of learning together!"
            conversation_history.append({"role": "system", "content": intro_message})
            session['airy_introduced'] = True

        # Append the user's message to the conversation history
        conversation_history.append({"role": "user", "content": user_message})

        # Guiding Principle for Adaptive Socratic Engagement
        socratic_prompt = "Employ Socratic questioning as a dynamic tool, adapting your inquiries to the user's level of comprehension and learning style. Your questions should be a compass, guiding users through the landscape of their knowledge, pinpointing areas of uncertainty, and leading them towards deeper self-awareness and understanding. Strive to create a dialogue that not only enlightens but also evolves with the user's academic journey."


        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=conversation_history + [{"role": "system", "content": socratic_prompt}],
            max_tokens=500,
            temperature=0.7,
            stop=["user:"], # Encourage the AI to expect a response after its message
        )
        
        # The AI's response, following Socratic questioning, is also added to the conversation history
        ai_response = response.choices[0].message.content
        conversation_history.append({"role": "assistant", "content": ai_response})

        # Save the updated conversation history back to the session
        session['conversation_history'] = conversation_history

        return jsonify(response=ai_response)
    except openai.error.OpenAIError as e:
        return jsonify(error=str(e)), 500

# Start the Flask app
if __name__ == '__main__':
    app.run(debug=True)
