from flask import Flask, render_template, redirect, url_for, request, jsonify, session
import uuid
import os
import json
import time
import threading
import traceback
import random
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason
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

def get_gemini_response(prompt, max_tokens=500):
    """
    Get response from Gemini with error handling
    """
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[ERROR] Gemini API call failed: {str(e)}")
        traceback.print_exc()
        return "I apologize, but I'm having trouble generating a response right now. Please try again."

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
            - Focus on problem-solving and practical application
            """
        elif 'company' in config and config['company']:
            company = config.get('company', '')
            role = config.get('role', 'Software Engineer')
            prompt = f"""Generate {num_questions} interview questions for a {role} position at {company}
            
            Requirements:
            - Questions should reflect {company}'s culture and values
            - Appropriate for {level} level candidates
            - Mix of technical and behavioral questions
            - Provide only the questions, numbered 1-{num_questions}
            - Each question on a new line
            """
        else:
            prompt = f"""Generate {num_questions} general interview questions for a {level} level candidate
            
            Requirements:
            - Mix of behavioral and problem-solving questions
            - Questions should assess communication and thinking skills
            - Provide only the questions, numbered 1-{num_questions}
            - Each question on a new line
            """
        
        print(f"[DEBUG] Sending prompt to Gemini...")
        questions_response = get_gemini_response(prompt, max_tokens=800)
        questions_list = [q.strip() for q in questions_response.strip().split('\n') if q.strip()]
        
        # Generate questions with answers and audio
        for i, question_text in enumerate(questions_list[:num_questions], 1):
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

@app.route('/setup/skill')
def setup_skill():
    """Renders the skill-based setup page."""
    return render_template('setup_skill.html')

@app.route('/setup/company')
def setup_company():
    """Renders the company-based setup page."""
    return render_template('setup_company.html')

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

@app.route('/interview_session/<session_id>/submit_answer', methods=['POST'])
def submit_answer(session_id):
    """Handle user answer submission"""
    try:
        if session_id not in sessions:
            return jsonify({'error': 'Invalid session ID'}), 404
        
        q_index = int(request.form.get('question_index'))
        audio_file = request.files.get('audio')
        
        if audio_file:
            filename = f"user_answer_{session_id}_q_{q_index}.webm"
            filepath = os.path.join('static', 'user_answers', filename)
            audio_file.save(filepath)
            
            if 'user_answers' not in sessions[session_id]:
                sessions[session_id]['user_answers'] = {}
            sessions[session_id]['user_answers'][q_index] = {'audio_path': filepath}
            
            print(f"[DEBUG] Saved user answer for question {q_index} in session {session_id}")
        
        return jsonify({'status': 'received'})
        
    except Exception as e:
        print(f"[ERROR] Failed to submit answer: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/report/<session_id>')
def generate_report(session_id):
    """Generate evaluation report using Gemini"""
    try:
        if session_id not in sessions:
            return redirect(url_for('home'))
        
        session_data = sessions[session_id]
        config = session_data['config']
        
        total_questions = len(session_data.get('questions', []))
        answered_count = len([k for k in session_data.get('user_answers', {}).keys() if k > 0])
        
        # Create context for feedback
        if 'skills' in config and config['skills']:
            topic_str = f"the skills: {', '.join(config['skills'])}"
        elif 'company' in config and config['company']:
            topic_str = f"a {config.get('role', 'Software Engineer')} role at {config['company']}"
        else:
            topic_str = "general interview skills"
        
        # Generate feedback using Gemini
        feedback_prompt = f"""Generate constructive interview feedback for a practice session on {topic_str}.
        
        Session Details:
        - Experience Level: {config.get('level', 'mid')}
        - Questions Attempted: {answered_count} out of {total_questions}
        - Session Type: {'Skills-based' if 'skills' in config else 'Company-based' if 'company' in config else 'General'}
        
        Please provide:
        1. Overall performance assessment
        2. Strengths observed
        3. Areas for improvement
        4. Specific recommendations
        5. Encouraging closing remarks
        
        Keep the feedback constructive, specific, and motivating. Write in a professional but encouraging tone.
        """
        
        feedback = get_gemini_response(feedback_prompt, max_tokens=600)
        accuracy = (answered_count / total_questions) * 100 if total_questions > 0 else 0
        
        return render_template('report.html', 
            session=session_data,
            accuracy=accuracy,
            feedback=feedback,
            answered=answered_count,
            total_questions=total_questions
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
    app.run(debug=True, port=5000, threaded=True)