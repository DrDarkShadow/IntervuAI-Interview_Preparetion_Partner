from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)

# Route for the homepage
@app.route('/')
def index():
    """Serves the homepage with the two choices."""
    return render_template('index.html')

# Route for the dedicated setup pages
@app.route('/setup/<mode>')
def setup_page(mode):
    """
    Serves the correct setup page based on the mode.
    e.g., /setup/topic or /setup/company
    """
    if mode == 'topic':
        return render_template('setup_skill.html')
    elif mode == 'company':
        return render_template('setup_company.html')
    else:
        # If the mode is invalid, redirect back to the homepage
        return redirect(url_for('index'))

# --- Future Endpoints to be built in the next versions ---
# @app.route('/prepare_session', methods=['POST'])
# def prepare_session():
#     # This will handle question/audio generation.
#     pass

# @app.route('/interview_session/<session_id>/submit_answer', methods=['POST'])
# def submit_answer():
#     # This will handle STT, evaluation, etc.
#     pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)