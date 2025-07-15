from flask import Flask, render_template, redirect, url_for, request, jsonify, session
import uuid
import os
import json
import time
import threading
import traceback
import random
from azure.cognitiveservices.speech import (
    SpeechConfig, SpeechSynthesizer, SpeechRecognizer, AudioConfig, ResultReason, CancellationReason
)
from azure.cognitiveservices.speech.audio import AudioOutputConfig
from dotenv import load_dotenv
import requests
from pydub import AudioSegment
import io
import google.generativeai as genai

# Load environment variables
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-2.0-flash')

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For session management

# Initialize Azure Speech
speech_key = os.getenv("AZURE_SPEECH_KEY")
speech_region = os.getenv("AZURE_SPEECH_REGION")

# In-memory session storage (replace with DB in production)
sessions = {}

# Ensure static directories exist
for directory in ['static/audio', 'static/user_answers', 'static/audio/introductions']:
    if not os.path.exists(directory):
        os.makedirs(directory)

# --- IMPROVED TTS FUNCTION ---
def generate_tts(text, output_file):
    """
    Generate TTS audio using Azure Speech Services REST API with better error handling
    """
    print(f"[DEBUG] Generating TTS for: {text[:50]}... -> {output_file}")
    
    try:
        # Construct the REST API URL
        url = f"https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        
        # Prepare headers
        headers = {
            'Ocp-Apim-Subscription-Key': speech_key,
            'Content-Type': 'application/ssml+xml',
            'X-Microsoft-OutputFormat': 'riff-24khz-16bit-mono-pcm',
            'User-Agent': 'ReconAI-TTS'
        }
        
        # Create SSML content
        ssml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="en-US-AriaNeural">
        <prosody rate="0.9" pitch="0%">
            {text}
        </prosody>
    </voice>
</speak>"""
        
        # Make the request
        response = requests.post(url, headers=headers, data=ssml_content, timeout=30)
        
        if response.status_code == 200:
            # Convert WAV to MP3 if needed
            if output_file.endswith('.mp3'):
                # Save as WAV first
                temp_wav = output_file.replace('.mp3', '.wav')
                with open(temp_wav, 'wb') as f:
                    f.write(response.content)
                
                try:
                    # Convert to MP3
                    audio = AudioSegment.from_wav(temp_wav)
                    audio.export(output_file, format="mp3")
                    os.remove(temp_wav)  # Clean up temp file
                except Exception as e:
                    print(f"[WARNING] Could not convert to MP3: {e}. Saving as WAV.")
                    os.rename(temp_wav, output_file.replace('.mp3', '.wav'))
                    return output_file.replace('.mp3', '.wav')
            else:
                with open(output_file, 'wb') as f:
                    f.write(response.content)
            
            print(f"[SUCCESS] TTS generated successfully: {output_file}")
            return True
        else:
            print(f"[ERROR] TTS request failed with status {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception in generate_tts: {str(e)}")
        traceback.print_exc()
        return False

def generate_tts_fallback(text, output_file):
    """
    Fallback TTS generation using Azure SDK
    """
    print(f"[DEBUG] Using fallback TTS for: {text[:50]}...")
    
    try:
        # Configure speech synthesis
        speech_config = SpeechConfig(subscription=speech_key, region=speech_region)
        speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
        
        # Configure audio output to file
        audio_config = AudioConfig(filename=output_file)
        
        # Create synthesizer
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        # Generate speech synchronously
        result = synthesizer.speak_text(text)
        
        # Check result
        if result.reason == ResultReason.SynthesizingAudioCompleted:
            print(f"[SUCCESS] Fallback TTS generated successfully: {output_file}")
            return True
        else:
            print(f"[ERROR] Fallback TTS failed with reason: {result.reason}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception in fallback TTS: {str(e)}")
        return False

def get_gemini_response(prompt, max_tokens=500, is_json=False):
    """
    Get response from Gemini with error handling and JSON parsing.
    """
    try:
        # For JSON output, add specific instructions to the prompt
        if is_json:
            full_prompt = f"{prompt}\n\nPlease provide the output in JSON format."
        else:
            full_prompt = prompt

        response = gemini_model.generate_content(full_prompt)
        
        if is_json:
            # Clean the response to extract the JSON part
            text_response = response.text.strip()
            json_str = text_response[text_response.find('{'):text_response.rfind('}')+1]
            return json.loads(json_str)
        else:
            return response.text
            
    except Exception as e:
        print(f"[ERROR] Gemini API call failed: {str(e)}")
        traceback.print_exc()
        if is_json:
            return {"error": "Failed to get a valid JSON response from the AI model."}
        return "I apologize, but I'm having trouble generating a response right now. Please try again."

# --- SPEECH-TO-TEXT AND ANALYSIS ---
def transcribe_audio_file(audio_path):
    """
    Transcribe audio file using Azure Speech-to-Text.
    """
    print(f"[DEBUG] Transcribing audio file: {audio_path}")
    try:
        # Azure Speech configuration
        speech_config = SpeechConfig(subscription=speech_key, region=speech_region)
        audio_config = AudioConfig(filename=audio_path)
        
        # Create a speech recognizer
        recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        # Perform recognition
        result = recognizer.recognize_once()
        
        # Process result
        if result.reason == ResultReason.RecognizedSpeech:
            print(f"[SUCCESS] Transcription successful: {result.text}")
            return result.text
        elif result.reason == ResultReason.NoMatch:
            print("[WARNING] No speech could be recognized.")
            return ""
        elif result.reason == ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"[ERROR] Speech Recognition canceled: {cancellation_details.reason}")
            if cancellation_details.reason == CancellationReason.Error:
                print(f"[ERROR] Error details: {cancellation_details.error_details}")
            return None
        
    except Exception as e:
        print(f"[ERROR] Exception in transcribe_audio_file: {str(e)}")
        traceback.print_exc()
        return None

def analyze_answer_with_gemini(question, model_answer, user_answer):
    """
    Analyze user's answer against the model answer using Gemini and get structured feedback.
    """
    print("[DEBUG] Analyzing answer with Gemini...")
    
    prompt = f"""
    As an expert interview coach, please analyze the following interview response.

    **Interview Question:**
    "{question}"

    **A Model Answer:**
    "{model_answer}"

    **The User's Answer:**
    "{user_answer}"

    **Analysis Task:**
    Provide a detailed analysis of the user's answer. I need a JSON object with the following structure:
    - "relevance_score": An integer score from 0 to 100, rating how relevant the user's answer was to the question.
    - "clarity_score": An integer score from 0 to 100, rating the clarity and conciseness of the answer.
    - "confidence_score": An integer score from 0 to 100, estimating the user's confidence based on their response.
    - "feedback": A string providing constructive feedback. Identify strengths and weaknesses.
    - "suggestion": A string with specific, actionable advice on how to improve the answer.
    """
    
    # Use the updated get_gemini_response to get a JSON object
    analysis = get_gemini_response(prompt, max_tokens=800, is_json=True)
    return analysis

# --- INTRODUCTION AUDIO GENERATION ---
def ensure_introduction_audios():
    """
    Generate introduction audios for both Recon AI and user introductions
    """
    print("[DEBUG] Checking introduction audios...")
    
    # Recon AI introductions
    recon_introductions = [
        "Welcome to Recon AI, your personal coach for interview success. Think of me as your practice partner, here to boost your confidence, sharpen your skills, and help you shine in every answer. This is your time to take the spotlight.",
        "Hello and welcome to Recon AI. You're not alone in this, I'm here to support you every step of the way. This is your space to practice, grow, and prepare with confidence. Let's begin on a strong note.",
        "Welcome to Recon AI, where preparation meets progress. Whether you're just starting out or polishing your skills, I'm here to help you bring out your best. Let's ease into this experience together.",
        "Hi there, and welcome aboard Recon AI, your smart partner in nailing every interview. Today is about growth, self-belief, and getting one step closer to your goals. You're in the perfect place to begin.",
        "Hey, and welcome to Recon AI, your space to prepare, practice, and gain confidence. No pressure, no rush, just a relaxed environment focused on you and your journey."
    ]
    
    # User introduction prompts
    user_introductions = [
        "To begin, please tell me a little about yourself and what interests you about this opportunity.",
        "Let's start with you introducing yourself. What's your background and what draws you to this field?",
        "I'd love to hear about you first. Could you share your background and what excites you about this role?",
        "Let's kick off with introductions. Tell me about yourself and what motivates you in your career.",
        "To get us started, please introduce yourself and share what passionate you about this industry."
    ]
    
    # Generate Recon AI introduction audios
    for i, text in enumerate(recon_introductions, 1):
        filepath = f"static/audio/introductions/recon_intro_{i}.mp3"
        if not os.path.exists(filepath):
            print(f"Generating Recon AI introduction {i}/5...")
            success = generate_tts(text, filepath)
            if not success:
                print(f"[WARNING] Primary TTS failed for Recon intro {i}, trying fallback...")
                success = generate_tts_fallback(text, filepath)
                if not success:
                    print(f"[ERROR] Both TTS methods failed for Recon intro {i}")
    
    # Generate user introduction audios
    for i, text in enumerate(user_introductions, 1):
        filepath = f"static/audio/introductions/user_intro_{i}.mp3"
        if not os.path.exists(filepath):
            print(f"Generating user introduction {i}/5...")
            success = generate_tts(text, filepath)
            if not success:
                print(f"[WARNING] Primary TTS failed for user intro {i}, trying fallback...")
                success = generate_tts_fallback(text, filepath)
                if not success:
                    print(f"[ERROR] Both TTS methods failed for user intro {i}")
    
    print("[SUCCESS] Introduction audio generation complete!")

# --- BACKGROUND QUESTION GENERATION ---
def prepare_remaining_questions(session_id, config):
    """
    Generate remaining questions after the introduction
    """
    print(f"[DEBUG] Preparing remaining questions for session {session_id}")
    
    try:
        session_data = sessions[session_id]
        num_questions = int(config.get('num_questions', '5'))
        level = config.get('level', 'mid')
        
        # Create appropriate prompt based on config
        if 'skills' in config and config['skills']:
            skills_str = ", ".join(config['skills'])
            prompt = f"""Generate {num_questions} technical interview questions focusing on: {skills_str}
            
            Requirements:
            - Questions should be appropriate for {level} level candidates
            - Each question should be practical and relevant
            - Provide only the questions, numbered 1-{num_questions}
            - Each question on a new line
            - Make questions conceptual and open ended 
            - The goal is not to see how well the candidate can remember things but rather test their knowledge
            - Focus on problem-solving and practical application
            - Try not to ask coding questions
            """

        elif 'company' in config and config['company']:
            company = config.get('company', '')
            role = config.get('role', 'Software Engineer')
            prompt = f"""Generate {num_questions} interview questions for a {role} position at {company}
            
            Requirements:
            - Understand the buissness that the company does
            - For eg uber is a ride sharing buissness
            - Discord is primarily a messaging service
            - Questions should reflect the companies buissness
            - Appropriate for {level} level candidates
            - Technial questions only 
            - Provide only the questions, numbered 1-{num_questions}
            - Each question on a new line
            - For eg software engineer must be asked about system design or some optimization problem
            """
        else:
            prompt = f"""Generate {num_questions} general interview questions for a {level} level candidate
            
            Requirements:
            - Technical open ended question to check knowledge and logic
            - Avoid coding questions 
            - Questions should assess communication and thinking skills
            - Provide only the questions, numbered 1-{num_questions}
            - Each question on a new line
            """
        
        print(f"[DEBUG] Sending prompt to Gemini...")
        questions_response = get_gemini_response(prompt, max_tokens=800)
        print("[DEBUG] questions_response : ", questions_response)
        questions_list = [q.strip() for q in questions_response.strip().split('\n') if q.strip()]
        
        # Generate questions with answers and audio
        for i, question_text in enumerate(questions_list[:num_questions], 1):
            # Check if the session has been cancelled
            if sessions.get(session_id, {}).get('status') == 'cancelled':
                print(f"[DEBUG] Session {session_id} was cancelled. Halting question generation.")
                return

            # Clean up question text (remove numbering if present)
            clean_question = question_text.split('. ', 1)[-1] if '. ' in question_text else question_text
            
            # Generate model answer
            answer_prompt = f"""Provide a concise model answer for this interview question: "{clean_question}"
            
            Requirements:
            - Answer should be appropriate for a {level} level candidate
            - Keep it structured and professional
            - Include key points that interviewers look for
            - Maximum 3-4 sentences
            """
            
            model_answer = get_gemini_response(answer_prompt, max_tokens=300)
            
            # Generate audio file
            audio_file = f"static/audio/session_{session_id}_q_{i}.mp3"
            print(f"[DEBUG] Generating audio for question {i}: {clean_question[:50]}...")
            
            tts_success = generate_tts(clean_question, audio_file)
            if not tts_success:
                print(f"[WARNING] Primary TTS failed for question {i}, trying fallback...")
                tts_success = generate_tts_fallback(clean_question, audio_file)
            
            if tts_success:
                audio_url = f"/{audio_file}"
            else:
                audio_url = None
                print(f"[ERROR] Both TTS methods failed for question {i}")
            
            # Add to session
            session_data['questions'].append({
                'text': clean_question,
                'answer': model_answer,
                'audio_url': audio_url,
                'index': i
            })
        
        session_data['status'] = 'all_questions_ready'
        print(f"[SUCCESS] Generated {len(session_data['questions'])} questions for session {session_id}")
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare questions: {str(e)}")
        traceback.print_exc()
        if session_id in sessions:
            sessions[session_id]['status'] = 'error'

def prepare_introduction_question(session_id, config):
    """
    Prepare the introduction question and start background generation
    """
    print(f"[DEBUG] Preparing introduction question for session {session_id}")
    
    try:
        session_data = sessions[session_id]
        
        # Select random introduction texts
        recon_intro_num = random.randint(1, 5)
        user_intro_num = random.randint(1, 5)
        
        recon_audio_path = f"static/audio/introductions/recon_intro_{recon_intro_num}.mp3"
        user_audio_path = f"static/audio/introductions/user_intro_{user_intro_num}.mp3"
        
        # Check if files exist, fallback to first one if not
        if not os.path.exists(recon_audio_path):
            print(f"[WARNING] Recon intro audio not found: {recon_audio_path}")
            recon_audio_path = "static/audio/introductions/recon_intro_1.mp3"
        
        if not os.path.exists(user_audio_path):
            print(f"[WARNING] User intro audio not found: {user_audio_path}")
            user_audio_path = "static/audio/introductions/user_intro_1.mp3"
        
        # Get the corresponding text for user introduction
        user_intro_texts = [
            "To begin, please tell me a little about yourself and what interests you about this opportunity.",
            "Let's start with you introducing yourself. What's your background and what draws you to this field?",
            "I'd love to hear about you first. Could you share your background and what excites you about this role?",
            "Let's kick off with introductions. Tell me about yourself and what motivates you in your career.",
            "To get us started, please introduce yourself and share what passionate you about this industry."
        ]
        
        # Set up the introduction question
        session_data['recon_intro_audio'] = f"/{recon_audio_path}"
        session_data['intro_question'] = {
            'text': user_intro_texts[user_intro_num - 1],
            'audio_url': f"/{user_audio_path}",
            'index': 0
        }
        
        session_data['status'] = 'intro_ready'
        
        # Start background generation of remaining questions
        threading.Thread(target=prepare_remaining_questions, args=(session_id, config), daemon=True).start()
        
        print(f"[SUCCESS] Introduction ready for session {session_id}")
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare introduction: {str(e)}")
        traceback.print_exc()
        if session_id in sessions:
            sessions[session_id]['status'] = 'error'

# --- ROUTES ---
@app.route('/')
def home():
    """Renders the main choice page."""
    return render_template('index.html')

@app.route('/skill_selection')
def skill_selection():
    """Renders the skill selection page."""
    return render_template('skill_selection.html')

@app.route('/company_selection')
def company_selection():
    """Renders the company selection page."""
    return render_template('company_selection.html')

@app.route('/interview_preparation')
def interview_preparation():
    """Renders the interview preparation page for skills or companies."""
    skill = request.args.get('skill')
    company = request.args.get('company')
    role = request.args.get('role')
    return render_template('interview_preparation.html', skill=skill, company=company, role=role)

@app.route('/setup_skill')
def setup_skill():
    """Renders the skill-based setup page."""
    skill = request.args.get('skill')
    return render_template('setup_skill.html', skill=skill)

# A dictionary to hold roles for each company
COMPANY_ROLES = {
    'Google': ['Software Engineer', 'Product Manager', 'Data Scientist', 'UX Designer', 'Site Reliability Engineer'],
    'Amazon': ['Software Development Engineer', 'Cloud Support Associate', 'Solutions Architect', 'Data Engineer', 'Product Manager'],
    'Microsoft': ['Software Engineer', 'Program Manager', 'Cloud Engineer', 'Security Analyst', 'Data Scientist'],
    'Meta': ['Software Engineer', 'Data Scientist', 'Product Designer', 'Marketing Science', 'Product Manager'],
    'Apple': ['Software Engineer', 'Hardware Engineer', 'Product Designer', 'Product Manager', 'Data Scientist'],
    'Netflix': ['Software Engineer', 'Data Scientist', 'Product Manager', 'Content Strategist', 'Machine Learning Engineer'],
    'Uber': ['Software Engineer', 'Data Scientist', 'Product Manager', 'Operations Manager', 'Machine Learning Engineer'],
    'Airbnb': ['Software Engineer', 'Data Scientist', 'Product Manager', 'UX Designer', 'Trust & Safety Specialist'],
    'Spotify': ['Software Engineer', 'Data Scientist', 'Product Manager', 'UX Designer', 'Content Strategist'],
    'Slack': ['Software Engineer', 'Product Manager', 'UX Designer', 'Customer Success Manager', 'Developer Relations'],
    'Dropbox': ['Software Engineer', 'Product Manager', 'UX Designer', 'Security Engineer', 'Data Scientist'],
    'Stripe': ['Software Engineer', 'Product Manager', 'Data Scientist', 'Risk Analyst', 'Developer Relations'],
    'Discord': ['Software Engineer', 'Product Manager', 'UX Designer', 'Community Manager', 'Data Scientist'],
    'Figma': ['Software Engineer', 'Product Manager', 'Product Designer', 'Developer Relations', 'Customer Success Manager'],
    'Notion': ['Software Engineer', 'Product Manager', 'UX Designer', 'Content Strategist', 'Customer Success Manager'],
    'Canva': ['Software Engineer', 'Product Manager', 'UX Designer', 'Graphic Designer', 'Data Scientist']
}

@app.route('/setup_company/<company>')
def setup_company(company):
    """Renders the role selection page for a specific company."""
    roles = COMPANY_ROLES.get(company, [])
    return render_template('role_selection.html', company_name=company, roles=roles)

@app.route('/prepare_session', methods=['POST'])
def prepare_session():
    """
    Prepares an interview session with improved flow
    """
    try:
        config = request.json
        print(f"[DEBUG] Received config: {config}")
        
        session_id = str(uuid.uuid4())
        total_questions = int(config.get('num_questions', 5)) + 1  # +1 for introduction
        
        sessions[session_id] = {
            'config': config,
            'status': 'initializing',
            'questions': [],
            'user_answers': {},
            'total_questions': total_questions,
            'created_at': time.time()
        }
        
        # Start preparation of introduction question
        threading.Thread(target=prepare_introduction_question, args=(session_id, config), daemon=True).start()
        
        return jsonify({
            'session_id': session_id,
            'num_questions': total_questions,
            'status': 'preparing',
            'message': 'Session is being prepared with introduction'
        })
        
    except Exception as e:
        print(f"[ERROR] Failed to prepare session: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/session_status/<session_id>')
def session_status(session_id):
    """Enhanced session status with introduction info"""
    if session_id not in sessions:
        return jsonify({'status': 'not_found'}), 404
    
    session_data = sessions[session_id]
    
    if session_data['status'] == 'intro_ready':
        return jsonify({
            'status': 'intro_ready',
            'recon_intro_audio': session_data.get('recon_intro_audio'),
            'intro_question': session_data.get('intro_question'),
            'questions_ready': len(session_data.get('questions', []))
        })
    
    return jsonify({
        'status': session_data['status'],
        'questions_ready': len(session_data.get('questions', []))
    })

@app.route('/get_question/<session_id>/<int:index>')
def get_question(session_id, index):
    """Get specific question by index"""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session_data = sessions[session_id]
    
    if index == 0:
        # Return introduction question
        intro_question = session_data.get('intro_question')
        if intro_question:
            return jsonify(intro_question)
        else:
            return jsonify({'status': 'not_ready'}), 202
    
    # Adjust index for regular questions (since intro is index 0)
    actual_index = index - 1
    if actual_index >= len(session_data['questions']):
        if session_data['status'] == 'all_questions_ready':
            return jsonify({'end_of_interview': True})
        return jsonify({'status': 'generating_questions'}), 202
    
    return jsonify(session_data['questions'][actual_index])

@app.route('/interview/<session_id>')
def interview_session(session_id):
    """Render interview session page"""
    if session_id not in sessions:
        return redirect(url_for('home'))
    return render_template('interview.html', session_id=session_id)

@app.route('/cancel_session/<session_id>', methods=['POST'])
def cancel_session(session_id):
    """Cancels a session, stopping background tasks."""
    if session_id in sessions:
        sessions[session_id]['status'] = 'cancelled'
        print(f"[DEBUG] Session {session_id} has been cancelled by the user.")
        return jsonify({'status': 'cancelled'}), 200
    return jsonify({'status': 'not_found'}), 404

@app.route('/interview_session/<session_id>/submit_answer', methods=['POST'])
def submit_answer(session_id):
    """Handle user answer submission, transcription, and analysis."""
    try:
        if session_id not in sessions:
            return jsonify({'error': 'Invalid session ID'}), 404
        
        q_index = int(request.form.get('question_index'))
        audio_file = request.files.get('audio')
        
        if not audio_file:
            return jsonify({'error': 'No audio file provided'}), 400

        # --- 1. Save Audio File ---
        filename = f"user_answer_{session_id}_q_{q_index}.webm"
        filepath = os.path.join('static', 'user_answers', filename)
        audio_file.save(filepath)
        print(f"[DEBUG] Saved user answer for question {q_index} at {filepath}")

        # --- 2. Convert WebM to WAV for transcription ---
        try:
            wav_path = filepath.replace('.webm', '.wav')
            audio = AudioSegment.from_file(filepath, format="webm")
            audio.export(wav_path, format="wav")
            print(f"[DEBUG] Converted {filepath} to {wav_path}")
        except Exception as e:
            print(f"[ERROR] Failed to convert WebM to WAV: {e}")
            return jsonify({'error': 'Failed to process audio file.'}), 500

        # --- 3. Transcribe Audio ---
        transcribed_text = transcribe_audio_file(wav_path)
        if transcribed_text is None:
            return jsonify({'error': 'Failed to transcribe audio.'}), 500

        # --- 4. Store Data and Start Analysis ---
        session_data = sessions[session_id]
        if 'user_answers' not in session_data:
            session_data['user_answers'] = {}
        
        session_data['user_answers'][q_index] = {
            'audio_path': filepath,
            'transcript': transcribed_text,
            'analysis_status': 'pending'
        }

        # --- 5. Run Analysis in Background ---
        def run_analysis():
            print(f"[DEBUG] Starting background analysis for Q{q_index}...")
            try:
                # Find the corresponding question and model answer
                question_data = {}
                if q_index == 0: # Introduction question
                    question_data = session_data.get('intro_question', {})
                    # For intro, model answer can be generic
                    model_answer = "A good introduction should be concise, cover key experiences, and express enthusiasm for the role."
                else:
                    question_data = next((q for q in session_data['questions'] if q['index'] == q_index), None)
                    model_answer = question_data.get('answer', 'No model answer available.')

                if not question_data:
                    print(f"[ERROR] Could not find question data for index {q_index}. Aborting analysis.")
                    session_data['user_answers'][q_index]['analysis_status'] = 'failed'
                    session_data['user_answers'][q_index]['analysis'] = {'error': 'Question data not found.'}
                    return

                # Get analysis from Gemini
                analysis_result = analyze_answer_with_gemini(
                    question_data['text'],
                    model_answer,
                    transcribed_text
                )
                
                # Update session with analysis
                session_data['user_answers'][q_index]['analysis'] = analysis_result
                session_data['user_answers'][q_index]['analysis_status'] = 'complete'
                print(f"[SUCCESS] Analysis complete for Q{q_index}")

            except Exception as e:
                print(f"[ERROR] Background analysis failed for Q{q_index}: {e}")
                traceback.print_exc()
                session_data['user_answers'][q_index]['analysis_status'] = 'failed'

        threading.Thread(target=run_analysis, daemon=True).start()
        
        return jsonify({'status': 'received', 'transcript': transcribed_text})
        
    except Exception as e:
        print(f"[ERROR] Failed to submit answer: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': 'An unexpected error occurred.'}), 500

@app.route('/report/<session_id>')
def generate_report(session_id):
    """Generate a detailed, interactive evaluation report."""
    try:
        if session_id not in sessions:
            return redirect(url_for('home'))
        
        session_data = sessions[session_id]
        
        # --- Wait for any pending analysis to complete ---
        # In a real app, you might use a more robust system like Celery
        # For this demo, a simple loop with a timeout is sufficient.
        timeout = 30  # seconds
        start_time = time.time()
        while any(v.get('analysis_status') == 'pending' for v in session_data.get('user_answers', {}).values()):
            if time.time() - start_time > timeout:
                print("[WARNING] Report generation timed out waiting for analysis.")
                break
            time.sleep(1)

        # --- Prepare data for the report ---
        report_data = {
            "config": session_data.get('config', {}),
            "questions": []
        }
        
        all_questions = [session_data.get('intro_question')] + session_data.get('questions', [])
        
        for q in all_questions:
            try:
                if not q: continue
                q_index = q['index']
                user_answer_data = session_data.get('user_answers', {}).get(q_index)

                # If user did not answer this question, create a placeholder
                if not user_answer_data:
                    user_answer_data = {
                        'transcript': 'Not answered',
                        'analysis': {'error': 'This question was not answered.'},
                        'audio_path': ''
                    }
                
                # Get model answer
                if q_index == 0:
                    model_answer = "A good introduction is concise, covers key experiences, and shows enthusiasm."
                else:
                    model_answer = q.get('answer', 'No model answer available.')

                report_data["questions"].append({
                    "text": q.get('text', 'Question text not found.'),
                    "index": q_index,
                    "model_answer": model_answer,
                    "user_transcript": user_answer_data.get('transcript', 'No answer recorded.'),
                    "analysis": user_answer_data.get('analysis', {}),
                    "audio_url": user_answer_data.get('audio_path', '').replace('static\\', '/static/')
                })
            except Exception as e:
                print(f"[ERROR] Failed to process question {q.get('index', 'N/A')} for report: {e}")
                # Optionally, add a placeholder to the report to indicate an error
                report_data["questions"].append({
                    "text": f"Error processing question.",
                    "index": q.get('index', 'N/A'),
                    "model_answer": "",
                    "user_transcript": "",
                    "analysis": {"error": "A server error occurred while processing this question."}
                })
            
        # --- Calculate overall scores for charts ---
        overall_scores = {
            "relevance": 0,
            "clarity": 0,
            "confidence": 0
        }
        analyzed_count = 0
        for q_data in report_data["questions"]:
            analysis = q_data.get("analysis")
            if analysis and "relevance_score" in analysis:
                overall_scores["relevance"] += analysis.get("relevance_score", 0)
                overall_scores["clarity"] += analysis.get("clarity_score", 0)
                overall_scores["confidence"] += analysis.get("confidence_score", 0)
                analyzed_count += 1
        
        if analyzed_count > 0:
            overall_scores["relevance"] = round(overall_scores["relevance"] / analyzed_count)
            overall_scores["clarity"] = round(overall_scores["clarity"] / analyzed_count)
            overall_scores["confidence"] = round(overall_scores["confidence"] / analyzed_count)

        return render_template('report.html', 
            report_data=report_data,
            overall_scores=overall_scores,
            session_id=session_id
        )
        
    except Exception as e:
        print(f"[ERROR] Failed to generate report: {str(e)}")
        traceback.print_exc()
        return redirect(url_for('home'))

# --- CLEANUP FUNCTION ---
def cleanup_old_sessions():
    """Remove old sessions to prevent memory bloat"""
    current_time = time.time()
    old_sessions = [sid for sid, data in sessions.items() 
                   if current_time - data.get('created_at', 0) > 3600]  # 1 hour
    
    for session_id in old_sessions:
        # Clean up audio files
        try:
            import glob
            audio_files = glob.glob(f"static/audio/session_{session_id}_*.mp3")
            for file in audio_files:
                os.remove(file)
        except:
            pass
        
        del sessions[session_id]
        print(f"[DEBUG] Cleaned up old session: {session_id}")

# Run cleanup every hour
def schedule_cleanup():
    cleanup_old_sessions()
    threading.Timer(3600, schedule_cleanup).start()

# --- STARTUP ---
if __name__ == '__main__':
    print("[DEBUG] Starting Recon AI Flask application...")
    print(f"[DEBUG] Azure OpenAI Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"[DEBUG] Azure Speech Region: {os.getenv('AZURE_SPEECH_REGION')}")
    
    # Check if pydub is available for audio conversion
    try:
        import pydub
        print("[DEBUG] Pydub available for audio conversion")
    except ImportError:
        print("[WARNING] Pydub not available. Install with: pip install pydub")
    
    print("[DEBUG] Initializing introduction audios...")
    
    # Ensure introduction audios are generated
    ensure_introduction_audios()
    
    # Start cleanup scheduler
    schedule_cleanup()
    
    print("[DEBUG] Flask app starting on port 5000...")
    # Using 'watchdog' as the reloader type is more stable on Windows
    app.run(debug=True, port=5000, threaded=True, reloader_type='watchdog')
