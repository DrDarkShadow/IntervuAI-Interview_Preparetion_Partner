// --- START OF MODIFIED FILE static/js/interview.js ---

document.addEventListener('DOMContentLoaded', function() {
    const interviewContainer = document.getElementById('interview-container');
    if (!interviewContainer) return;

    // --- State Management ---
    const state = {
        sessionId: interviewContainer.dataset.sessionId,
        currentQuestionIndex: -1, // Start at -1 to handle greeting first
        totalQuestions: 0,
        isRecording: false,
        mediaRecorder: null,
        audioChunks: [],
        timerInterval: null,
        userStream: null // To hold the user's media stream (cam/mic)
    };

    // --- UI Elements ---
    const ui = {
        questionNumber: document.getElementById('question-number'),
        questionText: document.getElementById('current-question-text'),
        statusMessage: document.getElementById('status-message'),
        timer: document.getElementById('timer'),
        recordBtn: document.getElementById('record-btn'),
        recordBtnIcon: document.getElementById('record-btn').querySelector('i'),
        recordBtnText: document.getElementById('record-btn').childNodes[2],
        repeatBtn: document.getElementById('repeat-btn'),
        skipBtn: document.getElementById('skip-btn'),
        progressDots: document.getElementById('progress-dots'),
        webcamVideo: document.getElementById('webcam-video'),
        proctoringOverlay: document.getElementById('proctoring-status-overlay')
    };

    // --- INITIALIZATION ---
    async function init() {
        setControlState('initializing');

        // CRITICAL FIX: Load session details from localStorage
        const sessionDetails = JSON.parse(localStorage.getItem('sessionDetails'));
        if (!sessionDetails || sessionDetails.sessionId !== state.sessionId) {
            updateStatus("Error: Session data not found. Please start over.");
            return;
        }
        state.totalQuestions = sessionDetails.totalQuestions;
        renderProgressDots();

        await setupWebcamAndMic();
        await pollForSessionReady();
    }

    async function pollForSessionReady() {
        updateStatus("AI is preparing your session...");
        const poll = setInterval(async () => {
            const response = await fetch(`/session_status/${state.sessionId}`);
            const data = await response.json();

            if (data.status === 'ready') {
                clearInterval(poll);
                startInterview();
            } else if (data.status === 'error') {
                clearInterval(poll);
                updateStatus("Error preparing session. Please try again.");
                setControlState('error');
            }
        }, 3000);
    }

    async function startInterview() {
        setControlState('ai_speaking');
        updateStatus("Welcome! The interview will begin shortly.");
        await playAudio(`/static/audio/session_${state.sessionId}_greeting.mp3`);
        await askNextQuestion();
    }

    async function askNextQuestion() {
        state.currentQuestionIndex++;
        if (state.currentQuestionIndex >= state.totalQuestions) {
            endInterview();
            return;
        }

        setControlState('loading');
        updateStatus(`Loading question ${state.currentQuestionIndex + 1}...`);

        try {
            const response = await fetch(`/get_question/${state.sessionId}/${state.currentQuestionIndex}`);
            const question = await response.json();

            if (question.error) throw new Error(question.error);
            if (question.end_of_interview) {
                endInterview();
                return;
            }

            ui.questionNumber.textContent = `Question ${state.currentQuestionIndex + 1} of ${state.totalQuestions}`;
            ui.questionText.textContent = question.text;
            updateProgressDots();

            setControlState('ai_speaking');
            await playAudio(question.audio_url);

            setControlState('user_turn');
            startTimer(120); // 120 seconds to answer
        } catch (error) {
            console.error("Error fetching question:", error);
            updateStatus("Error loading question. Please refresh.");
            setControlState('error');
        }
    }

    // --- EVENT HANDLERS ---
    ui.recordBtn.addEventListener('click', () => {
        if (!state.userStream) {
            alert("Microphone access is required to record. Please allow access and refresh.");
            return;
        }
        if (!state.isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    });

    ui.skipBtn.addEventListener('click', () => {
        if (state.timerInterval) clearInterval(state.timerInterval);
        ui.timer.textContent = "00:00";
        // Mark as skipped in progress dots
        const dot = ui.progressDots.children[state.currentQuestionIndex];
        if(dot) dot.classList.add('skipped');
        askNextQuestion();
    });

    ui.repeatBtn.addEventListener('click', async () => {
        if(state.currentQuestionIndex < 0) return; // no question to repeat yet
        const questionResponse = await fetch(`/get_question/${state.sessionId}/${state.currentQuestionIndex}`);
        const question = await questionResponse.json();
        if(question.audio_url) {
            setControlState('ai_speaking');
            await playAudio(question.audio_url);
            setControlState('user_turn');
        }
    });

    // --- MEDIA & RECORDING ---
    async function setupWebcamAndMic() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Your browser does not support camera or microphone access.');
            setControlState('error');
            return;
        }
        try {
            ui.proctoringOverlay.textContent = 'Requesting permissions...';
            // Request both video and audio
            state.userStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            ui.webcamVideo.srcObject = state.userStream;
            ui.proctoringOverlay.textContent = 'Proctoring Active';
        } catch (err) {
            console.error("Media access error:", err);
            ui.proctoringOverlay.textContent = 'Permission Denied';
            alert('Camera and microphone access denied. You will not be able to record answers. Please grant permissions and refresh the page.');
            setControlState('error');
        }
    }

    function startRecording() {
        if (!state.userStream) return;
        state.isRecording = true;
        setControlState('recording');
        
        state.audioChunks = [];
        // Use the existing stream for the recorder
        state.mediaRecorder = new MediaRecorder(state.userStream);
        
        state.mediaRecorder.ondataavailable = event => {
            state.audioChunks.push(event.data);
        };
        state.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
            state.isRecording = false;
            setControlState('loading'); // Now processing
            await submitAnswer(audioBlob);
        };
        
        state.mediaRecorder.start();
    }

    function stopRecording() {
        if (state.mediaRecorder && state.isRecording) {
            state.mediaRecorder.stop();
            if (state.timerInterval) clearInterval(state.timerInterval);
        }
    }

    async function submitAnswer(audioBlob) {
        updateStatus('Processing your answer...');
        const formData = new FormData();
        formData.append('audio', audioBlob, `answer.webm`);
        formData.append('question_index', state.currentQuestionIndex);
        
        try {
            const response = await fetch(`/interview_session/${state.sessionId}/submit_answer`, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) throw new Error('Failed to submit answer.');

            // Mark as completed in progress dots
            const dot = ui.progressDots.children[state.currentQuestionIndex];
            if(dot) dot.classList.add('completed');
            
            await askNextQuestion();
        } catch (error) {
            console.error(error);
            updateStatus('Error submitting answer. Moving to next question.');
            setControlState('user_turn');
            setTimeout(askNextQuestion, 2000);
        }
    }

    function endInterview() {
        setControlState('finished');
        updateStatus("Congratulations! Session complete. Generating your report...");
        
        // Stop all media tracks
        if (state.userStream) {
            state.userStream.getTracks().forEach(track => track.stop());
        }
        
        setTimeout(() => {
            window.location.href = `/report/${state.sessionId}`;
        }, 3000);
    }

    // --- HELPER FUNCTIONS ---
    function playAudio(url) {
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
            audio.play().catch(e => {
                 console.warn("Audio play failed, likely due to browser policy. User interaction needed.");
                 resolve(); // Resolve anyway so flow continues
            });
            audio.onended = resolve;
            audio.onerror = reject;
        });
    }

    function startTimer(duration) {
        let remaining = duration;
        if (state.timerInterval) clearInterval(state.timerInterval);
        
        state.timerInterval = setInterval(() => {
            const minutes = Math.floor(remaining / 60).toString().padStart(2, '0');
            const seconds = (remaining % 60).toString().padStart(2, '0');
            ui.timer.textContent = `${minutes}:${seconds}`;

            if (--remaining < 0) {
                clearInterval(state.timerInterval);
                ui.timer.textContent = "Time's Up!";
                if (state.isRecording) {
                    stopRecording();
                }
            }
        }, 1000);
    }
    
    function setControlState(mode) {
        // modes: 'initializing', 'loading', 'ai_speaking', 'user_turn', 'recording', 'finished', 'error'
        const buttons = [ui.recordBtn, ui.skipBtn, ui.repeatBtn];
        buttons.forEach(btn => btn.disabled = true);
        ui.recordBtnIcon.className = 'fas fa-microphone';
        ui.recordBtnText.textContent = ' Record Answer';

        switch (mode) {
            case 'user_turn':
                updateStatus('Your turn to answer.');
                buttons.forEach(btn => btn.disabled = false);
                break;
            case 'recording':
                updateStatus('Recording...');
                ui.recordBtn.disabled = false;
                ui.recordBtnIcon.className = 'fas fa-stop-circle';
                ui.recordBtnText.textContent = ' Stop Recording';
                break;
            case 'ai_speaking':
                updateStatus('AI is speaking...');
                ui.repeatBtn.disabled = false; // can repeat while AI is speaking or after
                break;
            case 'finished':
                updateStatus("Session finished.");
                break;
            case 'loading':
                updateStatus("Loading...");
                break;
            case 'error':
                updateStatus("An error occurred.");
                // All buttons remain disabled
                break;
            case 'initializing':
            default:
                updateStatus("Initializing...");
                break;
        }
    }
    
    function updateStatus(message) {
        ui.statusMessage.textContent = message;
    }

    function renderProgressDots() {
        ui.progressDots.innerHTML = '';
        for (let i = 0; i < state.totalQuestions; i++) {
            const dot = document.createElement('span');
            dot.className = 'progress-dot';
            dot.title = `Question ${i + 1}`;
            ui.progressDots.appendChild(dot);
        }
    }

    function updateProgressDots() {
        const dots = ui.progressDots.children;
        for (let i = 0; i < dots.length; i++) {
            dots[i].classList.remove('active');
            if (i === state.currentQuestionIndex) {
                dots[i].classList.add('active');
            }
        }
    }
    
    init(); // Start the interview process
});
// --- END OF MODIFIED FILE static/js/interview.js ---