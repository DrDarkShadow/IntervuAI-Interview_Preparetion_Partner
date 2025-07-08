# --- START OF MODIFIED FILE app.py ---

from flask import Flask, render_template, redirect, url_for, request, jsonify, session
import uuid
import os
import google.generativeai as genai
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig
import json
import time
import threading

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For session management

# Initialize Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

# Initialize Azure Speech
speech_key = os.getenv("AZURE_SPEECH_KEY")
speech_region = os.getenv("AZURE_SPEECH_REGION")

# In-memory session storage (replace with DB in production)
sessions = {}

# Ensure static directories exist
if not os.path.exists('static/audio'):
    os.makedirs('static/audio')
if not os.path.exists('static/user_answers'):
    os.makedirs('static/user_answers')

# --- NEW HOMEPAGE AND SETUP ROUTES ---
@app.route('/')
def home():
    """Renders the main choice page."""
    return render_template('index.html')

@app.route('/setup/skill')
def setup_skill():
    """Renders the skill-based setup page."""
    return render_template('setup_skill.html')

@app.route('/setup/company')
def setup_company():
    """Renders the company-based setup page."""
    return render_template('setup_company.html')

# --- CORE API ENDPOINTS ---
@app.route('/prepare_session', methods=['POST'])
def prepare_session():
    """
    Prepares an interview session in the background.
    Accepts config for both skill-based and company-based interviews.
    """
    config = request.json
    session_id = str(uuid.uuid4())
    
    # Store session configuration
    sessions[session_id] = {
        'config': config,
        'status': 'preparing',
        'questions': [],
        'created_at': time.time()
    }
    
    # Start background processing
    threading.Thread(target=generate_session_content, args=(session_id, config)).start()
    
    # Return session_id and num_questions for the frontend to store
    return jsonify({
        'session_id': session_id,
        'num_questions': config.get('num_questions'),
        'status': 'preparing',
        'message': 'Session is being prepared'
    })

def generate_session_content(session_id, config):
    """
    Generates questions, answers, and audio in the background.
    Handles different prompt types based on the config.
    """
    try:
        num_questions = config.get('num_questions', '5')
        level = config.get('level', 'intermediate')

        # --- MODIFIED: Dynamic Prompt Generation ---
        if 'skills' in config: # Skill-based interview
            skills_str = ", ".join(config['skills'])
            prompt = f"Generate {num_questions} interview questions about the following skills: {skills_str} for a {level} level candidate. Please provide only the questions, each on a new line, starting with a number and a period (e.g., '1. ')."
        elif 'company' in config: # Company-based interview
            company = config['company']
            role = config['role']
            prompt = f"Generate {num_questions} interview questions for a {level} level {role} candidate interviewing at {company}. The questions should reflect the company's culture and typical interview style. Please provide only the questions, each on a new line, starting with a number and a period (e.g., '1. ')."
        else: # Fallback for old form type
            topic = config.get('topic', 'general knowledge')
            prompt = f"Generate {num_questions} interview questions about {topic} for a {level} level candidate. Please provide only the questions, each on a new line, starting with a number and a period (e.g., '1. ')."

        response = model.generate_content(prompt)
        # Clean up the response to get a clean list of questions
        questions = [q.strip() for q in response.text.strip().split('\n') if q.strip()]

        session_data = {'questions': []}
        for i, question_text in enumerate(questions[:int(num_questions)]):
            # Generate sketch answer
            answer_prompt = f"Provide a concise, expert-level model answer for the interview question: '{question_text}' for a {level} candidate."
            answer_response = model.generate_content(answer_prompt)
            
            # Generate TTS audio for the question
            audio_file = f"static/audio/session_{session_id}_q_{i}.mp3"
            generate_tts(question_text, audio_file)
            
            session_data['questions'].append({
                'text': question_text,
                'answer': answer_response.text,
                'audio_url': f"/{audio_file}",
                'index': i
            })
        
        # Update session status
        sessions[session_id].update({
            'status': 'ready',
            'questions': session_data['questions']
        })
        
        # Generate greeting audio
        greeting_file = f"static/audio/session_{session_id}_greeting.mp3"
        greeting_text = "Welcome to your interview practice session. Let's begin."
        generate_tts(greeting_text, greeting_file)
        
    except Exception as e:
        print(f"Error in generate_session_content for {session_id}: {e}")
        sessions[session_id]['status'] = 'error'
        sessions[session_id]['error'] = str(e)

def generate_tts(text, output_file):
    """Generate TTS audio using Azure Cognitive Services"""
    try:
        speech_config = SpeechConfig(subscription=speech_key, region=speech_region)
        speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
        audio_config = AudioConfig(filename=output_file)
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_text_async(text).get()
        if result.reason != 1: # 1 is SynthesizingAudioCompleted
             print(f"TTS generation failed: {result.reason}")
    except Exception as e:
        print(f"Error in generate_tts: {e}")

@app.route('/session_status/<session_id>')
def session_status(session_id):
    """Checks the status of the session preparation."""
    return jsonify(sessions.get(session_id, {'status': 'not_found'}))

@app.route('/get_question/<session_id>/<int:index>')
def get_question(session_id, index):
    """Get specific question by index"""
    if session_id not in sessions or sessions[session_id]['status'] != 'ready':
        return jsonify({'error': 'Session not ready or found'}), 404
    
    questions = sessions[session_id]['questions']
    if index < 0 or index >= len(questions):
        # If it's the end of the interview, send a specific signal
        if index == len(questions):
            return jsonify({'end_of_interview': True})
        return jsonify({'error': 'Invalid question index'}), 404
    
    return jsonify(questions[index])

@app.route('/interview/<session_id>')
def interview_session(session_id):
    """Render interview session page"""
    if session_id not in sessions:
        return redirect(url_for('home'))
    return render_template('interview.html', session_id=session_id)

@app.route('/interview_session/<session_id>/submit_answer', methods=['POST'])
def submit_answer(session_id):
    """
    Receives user's audio answer.
    FIXED: Returns a mock transcript to allow the frontend flow to continue.
    """
    if session_id not in sessions:
        return jsonify({'error': 'Invalid session ID'}), 404
    
    question_index = int(request.form.get('question_index'))
    audio_file = request.files.get('audio')

    if audio_file:
        # Save the user's answer for later review
        filename = f"user_answer_{session_id}_q_{question_index}.webm"
        filepath = os.path.join('static', 'user_answers', filename)
        audio_file.save(filepath)
        # Mark that the user has answered this question
        if 'user_answers' not in sessions[session_id]:
            sessions[session_id]['user_answers'] = {}
        sessions[session_id]['user_answers'][question_index] = {'audio_path': filepath}
        
    # In a real implementation, you would transcribe the audio here.
    # For now, we return a placeholder to make the UI work.
    return jsonify({
        'status': 'received',
        'transcript': '[Your transcribed answer would appear here. This is a placeholder.]'
    })


@app.route('/report/<session_id>')
def generate_report(session_id):
    """Generate evaluation report"""
    if session_id not in sessions:
        return redirect(url_for('home'))
    session_data = sessions[session_id]
    total_questions = len(session_data.get('questions', []))
    answered_count = len(session_data.get('user_answers', {}))
    accuracy = (answered_count / total_questions) * 100 if total_questions > 0 else 0
    
    feedback_prompt = f"Generate overall feedback for an interview practice session on {session_data['config'].get('topic', 'a specific role')}. The candidate attempted {answered_count} out of {total_questions} questions. Provide constructive, encouraging feedback and suggest areas for improvement."
    feedback = model.generate_content(feedback_prompt).text
    
    return render_template('report.html', 
        session=session_data,
        accuracy=accuracy,
        feedback=feedback,
        answered=answered_count,
        total_questions=total_questions
    )

if __name__ == '__main__':
    # Note: For camera/mic access on a network, you'll need to run with SSL.
    # For local development, `localhost` or `127.0.0.1` is usually fine.
    app.run(debug=True, port=5000)

# --- END OF MODIFIED FILE app.py ---